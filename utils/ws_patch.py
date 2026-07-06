import re, itertools
import json
import os, logging
import pandas as pd
from io import BytesIO
from lxml import html
from typing import Optional, Literal, Union
from soccerdata._config import TEAMNAME_REPLACEMENTS
from soccerdata.whoscored import WhoScored, WHOSCORED_URL, _parse_url
from soccerdata._common import make_game_id, standardize_colnames
import soccerdata as sd
from pathlib import Path
from selenium.webdriver.common.by import By
import socceraction

logger = logging.getLogger("root")
logger.setLevel(logging.ERROR)

def apply_whoscored_patch(selection):
    """
    Applies a monkey patch to soccerdata's WhoScored class 
    to fix malformed JSON responses wrapped in HTML tags.
    """
    # 1. Save the TRUE original method permanently to the class
    # This ensures we never accidentally wrap a patch inside another patch.
    if not hasattr(WhoScored, "_original_get"):
        WhoScored._original_get = WhoScored.get
        
    # ALWAYS reference the true original, never the currently active patch
    original_get = WhoScored._original_get

    # 2. Define the wrapper methods
    def patched_1(self, url, filepath, *args, **kwargs):
        # Fetch data using the true original method
        reader = original_get(self, url, filepath, *args, **kwargs)
        
        if "/data/?d=" in url:
            to_fix_1 = reader.read().decode('utf-8')
            to_fix_2 = re.sub(r'^<.*>{', r'{', to_fix_1, re.S)
            reader_fixed = re.sub(r'}<.*$', r'}', to_fix_2, re.S)
            
            return BytesIO(reader_fixed.encode('utf-8'))
        return reader
    
    def patched_2(self, url, filepath, *args, **kwargs):
        reader = original_get(self, url, filepath, *args, **kwargs)
        
        retries = kwargs.pop('retries', 0)
        
        raw_content = reader.read()
        reader.close()

        is_html_page = any(x in url.lower() for x in ["/seasons/", "/regions/", "/leagues/"])
        is_data_url = not is_html_page or "/data/?d=" in url or url.endswith(".json")

        if "/data/?d=" in url:
            try:
                text = raw_content.decode('utf-8')
                text = re.sub(r'^<.*>{', r'{', text, re.S)
                text = re.sub(r'}<.*$', r'}', text, re.S)
                raw_content = text.encode('utf-8')
            except UnicodeDecodeError:
                pass
        
        if is_data_url:
            try:
                json.loads(raw_content)
            except (json.JSONDecodeError, TypeError, ValueError):
                if retries < 3:
                    if filepath and os.path.exists(filepath):
                        print(f"Detected corruption at {url}. Deleting cache and retrying (Attempt {retries + 1}/3)...")
                        os.remove(filepath)
                    
                    kwargs['retries'] = retries + 1
                    return patched_2(self, url, filepath, *args, **kwargs)
                else:
                    print(f"Max retries (3) reached for {url}. Aborting.")
                    raise ValueError(f"Failed to fetch valid data for {url}")
            
        return BytesIO(raw_content)

    if selection == 1 or selection == 3 or selection == 4:
        WhoScored.get = patched_1
        print("Patch 1 applied successfully.")
    elif selection == 2:
        WhoScored.get = patched_2
        print("Patch 2 applied successfully.")
    else:
        WhoScored.get = original_get
        print("Restored original method (no patch).")


def sanitize_ofl_team_match_stats_fbref(df):
    """Prevents ArrowTypeError by ensuring object/mixed columns are clean"""
    if df is None or df.empty:
        return df
    
    df = df.copy()
    # Force 'GF' column to be numeric, forcing errors to NaN
    if 'GF' in df.columns:
        df['GF'] = pd.to_numeric(df['GF'], errors='coerce')
        
    # Alternate catch-all: Convert any lingering 'object' columns completely to strings
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str)
        
    return df

def read_seasons_patch(self) -> pd.DataFrame:
    df_leagues = self.read_leagues()
    seasons = []
    for lkey, league in df_leagues.iterrows():
        url = (
            sd.whoscored.WHOSCORED_URL # Note: ensure your imports match where WHOSCORED_URL lives
            + f"/Regions/{league['region_id']}"
            + f"/Tournaments/{league['league_id']}"
        )
        filemask = "seasons/{}.html"
        filepath = self.data_dir / filemask.format(lkey)
        reader = self.get(url, filepath, var=None)

        from lxml import html
        tree = html.parse(reader)
        for node in tree.xpath("//select[contains(@id,'seasons')]/option"):
            season_url = node.get("value")
            season_id = sd.whoscored._parse_url(season_url)["season_id"]
            seasons.append({
                "league": lkey,
                "season": self._season_code.parse(node.text),
                "region_id": league.region_id,
                "league_id": league.league_id,
                "season_id": season_id,
            })

    target_index = pd.MultiIndex.from_product(
        [self.leagues, self.seasons], 
        names=["league", "season"]
    )
    return pd.DataFrame(seasons).set_index(["league", "season"]).sort_index().reindex(target_index)

def read_season_stages_patch(self, force_cache: bool = False, debugging: bool = False) -> pd.DataFrame:
    df_seasons = self.read_seasons()
    filemask = "seasons/{}_{}.html"

    season_stages = []
    for (lkey, skey), season in df_seasons.iterrows():
        current_season = not self._is_complete(lkey, skey)

        # FIX 1: Skip rows with missing IDs
        if pd.isna(season['region_id']) or pd.isna(season['league_id']) or pd.isna(season['season_id']):
            if debugging:
                print(f"Skipping {lkey} {skey} due to missing IDs in WhoScored config.")
            continue

        # FIX 2: Ensure IDs are passed as integers, not floats
        url = (
            WHOSCORED_URL
            + f"/Regions/{int(season['region_id'])}"
            + f"/Tournaments/{int(season['league_id'])}"
            + f"/Seasons/{int(season['season_id'])}"
        )
        
        filepath = self.data_dir / filemask.format(lkey, skey)
        reader = self.get(url, filepath, var=None, no_cache=current_season and not force_cache)
        tree = html.parse(reader)

        # get default season stage
        fixtures_elements = tree.xpath("//a[text()='Fixtures']/@href")
        
        # FIX 3: Safeguard against empty 404 pages
        if not fixtures_elements:
            if debugging:
                print(f"Could not find 'Fixtures' link for {lkey} {skey}. Page might be invalid.")
            continue
            
        fixtures_url = fixtures_elements[0]
        stage_id = _parse_url(fixtures_url)["stage_id"]
        
        season_stages.append({
            "league": lkey,
            "season": skey,
            "region_id": season.region_id,
            "league_id": season.league_id,
            "season_id": season.season_id,
            "stage_id": stage_id,
            "stage": None,
        })

        # extract additional stages
        for node in tree.xpath("//select[contains(@id,'stages')]/option"):
            stage_url = node.get("value")
            stage_id = _parse_url(stage_url)["stage_id"]
            season_stages.append({
                "league": lkey,
                "season": skey,
                "region_id": season.region_id,
                "league_id": season.league_id,
                "season_id": season.season_id,
                "stage_id": stage_id,
                "stage": node.text,
            })

    # FIX 4: Safely filter the final dataframe using intersection
    df = (
        pd.DataFrame(season_stages)
        .drop_duplicates(subset=["league", "season", "stage_id"], keep="last")
        .set_index(["league", "season"])
        .sort_index()
    )

    requested_keys = list(itertools.product(self.leagues, self.seasons))
    valid_keys = df.index.intersection(requested_keys)

    return df.loc[valid_keys]

def read_schedule_patch(self, force_cache: bool = False, debugging: bool = False) -> pd.DataFrame:
    df_season_stages = self.read_season_stages(force_cache=force_cache)
    filemask_schedule = "matches/{}_{}_{}_{}.json"

    all_schedules = []
    for (lkey, skey), stage in df_season_stages.iterrows():
        current_season = not self._is_complete(lkey, skey)
        stage_id = stage["stage_id"]
        stage_name = stage["stage"]

        season_stage_url = (
            WHOSCORED_URL
            + f"/Regions/{stage['region_id']}"
            + f"/Tournaments/{stage['league_id']}"
            + f"/Seasons/{stage['season_id']}"
            + f"/Stages/{stage['stage_id']}"
        )
        
        if stage_name is not None:
            calendar_filepath = self.data_dir / f"matches/{lkey}_{skey}_{stage_id}.html"
            logger.info(
                "Retrieving calendar for %s %s (%s)",
                lkey,
                skey,
                stage_name,
            )
        else:
            calendar_filepath = self.data_dir / f"matches/{lkey}_{skey}.html"
            logger.info(
                "Retrieving calendar for %s %s",
                lkey,
                skey,
            )
        calendar = self.get(
            season_stage_url,
            calendar_filepath,
            var="wsCalendar",
            no_cache=current_season and not force_cache,
        )
        
        # ==========================================
        # THE ULTIMATE BYPASS: MANUALLY BUILD THE CALENDAR
        # ==========================================
        calendar_data = json.load(calendar)
        if calendar_data and "mask" in calendar_data:
            mask = calendar_data["mask"]
            it = [(year, month) for year in mask for month in mask[year]]
        else:
            if debugging:
                print(f"\n[BYPASS] WhoScored hid the calendar map for {lkey} {skey}. Forcing manual search...")
            
            # Just grab the starting year of the season
            if len(skey) == 4:
                p1 = skey[:2]
                start_year = "19" + p1 if int(p1) > 50 else "20" + p1
            else:
                start_year = "2023" # Safety fallback

            it = []
            # Loop from 0 to 23 (This safely covers 2 full years of continuous months)
            # e.g., 0 = Jan, 11 = Dec, 12 = Jan (Next Year), 23 = Dec (Next Year)
            for m in range(24):
                it.append((start_year, str(m)))
        # ==========================================

        # Ping the API for every generated month
        for i, (year, month) in enumerate(it):
            filepath = self.data_dir / filemask_schedule.format(lkey, skey, stage_id, month)
            url = WHOSCORED_URL + f"/tournaments/{stage_id}/data/?d={year}{(int(month) + 1):02d}"

            try:
                if stage_name is not None:
                    logger.info(
                        "[%s/%s] Retrieving fixtures for %s %s (%s)",
                        i + 1,
                        len(it),
                        lkey,
                        skey,
                        stage_name,
                    )
                else:
                    logger.info(
                        "[%s/%s] Retrieving fixtures for %s %s",
                        i + 1,
                        len(it),
                        lkey,
                        skey,
                    )
                    
                reader = self.get(
                    url, filepath, var=None, no_cache=current_season and not force_cache
                )
                
                # ---> FINAL BOSS FIX: Unwrap the HTML-wrapped JSON <---
                raw_text = reader.read()
                if isinstance(raw_text, bytes):
                    raw_text = raw_text.decode('utf-8', errors='ignore')
                    
                # Extract only the valid JSON between the curly braces
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}')
                
                if start_idx != -1 and end_idx != -1:
                    clean_text = raw_text[start_idx:end_idx+1]
                    data = json.loads(clean_text)
                else:
                    data = {}
                # ------------------------------------------------------
                
                # If the API returns matches for this month, save them!
                if "tournaments" in data and data["tournaments"]:
                    if debugging:
                        print(f"  -> Found match data for {year}-{int(month)+1:02d}!")
                    for tournament in data["tournaments"]:
                        df_schedule = pd.DataFrame(tournament["matches"])
                        df_schedule["league"] = lkey
                        df_schedule["season"] = skey
                        df_schedule["stage"] = stage_name
                        all_schedules.append(df_schedule)
                        
            except Exception as e:
                continue

    if len(all_schedules) == 0:
        return pd.DataFrame(index=["league", "season", "game"])

    return (
        pd.concat(all_schedules)
        .drop_duplicates(subset=["id"])
        .replace(
            {
                "homeTeamName": TEAMNAME_REPLACEMENTS,
                "awayTeamName": TEAMNAME_REPLACEMENTS,
            }
        )
        .rename(
            columns={
                "homeTeamName": "home_team",
                "awayTeamName": "away_team",
                "id": "game_id",
                "startTimeUtc": "date",
            }
        )
        .assign(date=lambda x: pd.to_datetime(x["date"]))
        .assign(game=lambda df: df.apply(make_game_id, axis=1))
        .pipe(standardize_colnames)
        .set_index(["league", "season", "game"])
        .sort_index()
    )

def read_game_info_patch(self, game_id: int) -> dict:
    """Monkey patched version to handle extra hyphens in European Championships."""
    urlmask = "https://www.whoscored.com/Matches/{}"
    url = urlmask.format(game_id)
    data = {}
    self._driver.get(url)
    
    breadcrumb = self._driver.find_elements(
        By.XPATH,
        "//div[@id='breadcrumb-nav']/*[not(contains(@class, 'separator'))]",
    )
    country = breadcrumb[0].text
    
    breadcrumb_text = breadcrumb[1].text
    parts = breadcrumb_text.split(" - ")
    
    league_name = parts[0]
    league_key = f"{country} - {league_name}"
    reversed_leagues = {v: k for k, v in self._all_leagues().items()}
    
    if league_key in reversed_leagues:
        data["league"] = reversed_leagues[league_key]
    else:
        fuzzy_match = next((v for k, v in reversed_leagues.items() if k.startswith(country) and league_name in k), None)
        data["league"] = fuzzy_match if fuzzy_match else league_key
    
    parsed_season = None
    for part in reversed(parts):
        try:
            parsed_season = self._season_code.parse(part)
            break
        except ValueError:
            continue
            
    data["season"] = parsed_season if parsed_season else parts[-1]
    
    match_header = self._driver.find_element(By.XPATH, "//div[@id='match-header']")
    score_info = match_header.find_element(By.XPATH, ".//div[@class='teams-score-info']")
    data["home_team"] = score_info.find_element(
        By.XPATH, "./span[contains(@class,'home team')]"
    ).text
    data["result"] = score_info.find_element(
        By.XPATH, "./span[contains(@class,'result')]"
    ).text
    data["away_team"] = score_info.find_element(
        By.XPATH, "./span[contains(@class,'away team')]"
    ).text
    
    info_blocks = match_header.find_elements(By.XPATH, ".//div[@class='info-block cleared']")
    for block in info_blocks:
        for desc_list in block.find_elements(By.TAG_NAME, "dl"):
            for desc_def in desc_list.find_elements(By.TAG_NAME, "dt"):
                desc_val = desc_def.find_element(By.XPATH, "./following-sibling::dd")
                data[desc_def.text] = desc_val.text

    return data

def read_game_info_patch_serie_a(self, game_id: int) -> dict:
    urlmask = WHOSCORED_URL + "/Matches/{}"
    url = urlmask.format(game_id)
    data = {}
    self._driver.get(url)
    # league and season
    breadcrumb = self._driver.find_elements(
        By.XPATH,
        "//div[@id='breadcrumb-nav']/*[not(contains(@class, 'separator'))]",
    )
    country = breadcrumb[0].text
    bb = breadcrumb[1].text.split(" - ")
    if len(bb) == 2:
        league, season = bb
    else:
        league, season, league_2 = breadcrumb[1].text.split(" - ")
        if league_2 == "Serie A Relegation Playoff":
            league_2 = "Serie A"
    data["league"] = {v: k for k, v in self._all_leagues().items()}[f"{country} - {league}"]
    data["season"] = self._season_code.parse(season)
    # match header
    match_header = self._driver.find_element(By.XPATH, "//div[@id='match-header']")
    score_info = match_header.find_element(By.XPATH, ".//div[@class='teams-score-info']")
    data["home_team"] = score_info.find_element(
        By.XPATH, "./span[contains(@class,'home team')]"
    ).text
    data["result"] = score_info.find_element(
        By.XPATH, "./span[contains(@class,'result')]"
    ).text
    data["away_team"] = score_info.find_element(
        By.XPATH, "./span[contains(@class,'away team')]"
    ).text
    info_blocks = match_header.find_elements(By.XPATH, ".//div[@class='info-block cleared']")
    for block in info_blocks:
        for desc_list in block.find_elements(By.TAG_NAME, "dl"):
            for desc_def in desc_list.find_elements(By.TAG_NAME, "dt"):
                desc_val = desc_def.find_element(By.XPATH, "./following-sibling::dd")
                data[desc_def.text] = desc_val.text

    return data

def read_events(  # noqa: C901
    self,
    match_id: Optional[Union[int, list[int]]] = None,
    force_cache: bool = False,
    live: bool = False,
    output_fmt: Optional[str] = "events",
    retry_missing: bool = True,
    on_error: Literal["raise", "skip"] = "raise",
) -> Optional[Union[pd.DataFrame, dict[int, list], "OptaLoader"]]:   # type: ignore  # noqa: F821
    output_fmt = output_fmt.lower() if output_fmt is not None else None
    if output_fmt in ["loader", "spadl", "atomic-spadl"]:
        if self.no_store:
            raise ValueError(
                f"The '{output_fmt}' output format is not supported "
                "when using the 'no_store' option."
            )
        try:
            from socceraction.atomic.spadl import convert_to_atomic
            from socceraction.data.opta import OptaLoader
            from socceraction.data.opta.loader import _eventtypesdf
            from socceraction.data.opta.parsers import WhoScoredParser
            from socceraction.spadl.opta import convert_to_actions

            if output_fmt == "loader":
                import socceraction
                from packaging import version

                if version.parse(socceraction.__version__) < version.parse("1.2.3"):
                    raise ImportError(
                        "The 'loader' output format requires socceraction >= 1.2.3"
                    )
        except ImportError:
            raise ImportError(
                "The socceraction package is required to use the 'spadl' "
                "or 'atomic-spadl' output format. "
                "Please install it with `pip install socceraction`."
            )
    urlmask = WHOSCORED_URL + "/Matches/{}/Live"
    filemask = "events/{}_{}/{}.json"

    df_schedule = self.read_schedule(force_cache).reset_index()
    if match_id is not None:
        iterator = df_schedule[
            df_schedule.game_id.isin([match_id] if isinstance(match_id, int) else match_id)
        ]
        if len(iterator) == 0:
            raise ValueError("No games found with the given IDs in the selected seasons.")
    else:
        iterator = df_schedule.sample(frac=1)

    events = {}
    player_names = {}
    team_names = {}
    for i, (_, game) in enumerate(iterator.iterrows()):
        url = urlmask.format(game["game_id"])
        # get league and season
        logger.info(
            "[%s/%s] Retrieving game with id=%s",
            i + 1,
            len(iterator),
            game["game_id"],
        )
        filepath = self.data_dir / filemask.format(
            game["league"], game["season"], game["game_id"]
        )

        try:
            reader = self.get(
                url,
                filepath,
                var="require.config.params['args'].matchCentreData",
                no_cache=live,
            )
            reader_value = reader.read()
            if (retry_missing and reader_value == b"null") or reader_value == b"":
                reader = self.get(
                    url,
                    filepath,
                    var="require.config.params['args'].matchCentreData",
                    no_cache=True,
                )
        except ConnectionError as e:
            if on_error == "skip":
                logger.warning("Error while scraping game %s: %s", game["game_id"], e)
                continue
            raise
        reader.seek(0)
        json_data = json.load(reader)
        if json_data is not None:
            player_names.update(
                {int(k): v for k, v in json_data["playerIdNameDictionary"].items()}
            )
            team_names.update(
                {
                    int(json_data[side]["teamId"]): json_data[side]["name"]
                    for side in ["home", "away"]
                }
            )
            if "events" in json_data:
                game_events = json_data["events"]
                if output_fmt == "events":
                    df_events = pd.DataFrame(game_events)
                    df_events["game"] = game["game"]
                    df_events["league"] = game["league"]
                    df_events["season"] = game["season"]
                    df_events["game_id"] = game["game_id"]
                    events[game["game_id"]] = df_events
                elif output_fmt == "raw":
                    events[game["game_id"]] = game_events
                elif output_fmt in ["spadl", "atomic-spadl"]:
                    parser = WhoScoredParser(
                        str(filepath),
                        competition_id=game["league"],
                        season_id=game["season"],
                        game_id=game["game_id"],
                    )
                    df_events = (
                        pd.DataFrame.from_dict(parser.extract_events(), orient="index")
                        .merge(_eventtypesdf, on="type_id", how="left")
                        .reset_index(drop=True)
                    )
                    df_actions = convert_to_actions(
                        df_events, home_team_id=int(json_data["home"]["teamId"])
                    )
                    if output_fmt == "spadl":
                        events[game["game_id"]] = df_actions
                    else:
                        events[game["game_id"]] = convert_to_atomic(df_actions)

        else:
            logger.warning("No events found for game %s", game["game_id"])

    if output_fmt is None:
        return None

    if output_fmt == "raw":
        return events
    
    if output_fmt == "raw_nested":
        return json_data

    if output_fmt == "loader":
        return OptaLoader(
            root=self.data_dir,
            parser="whoscored",
            feeds={
                "whoscored": str(Path("events/{competition_id}_{season_id}/{game_id}.json"))
            },
        )

    if len(events) == 0:
        return pd.DataFrame(index=["league", "season", "game"])

    df = (
        pd.concat(events.values())
        .pipe(standardize_colnames)
        .assign(
            player=lambda x: x.player_id.replace(player_names),
            team=lambda x: x.team_id.replace(team_names).replace(TEAMNAME_REPLACEMENTS),
        )
    )

    if output_fmt == "events":
        df = df.set_index(["league", "season", "game"]).sort_index()
        # add missing columns
        for col, default in COLS_EVENTS.items():
            if col not in df.columns:
                df[col] = default
        df["outcome_type"] = df["outcome_type"].apply(
            lambda x: x.get("displayName") if pd.notnull(x) else x
        )
        df["card_type"] = df["card_type"].apply(
            lambda x: x.get("displayName") if pd.notnull(x) else x
        )
        df["type"] = df["type"].apply(lambda x: x.get("displayName") if pd.notnull(x) else x)
        df["period"] = df["period"].apply(
            lambda x: x.get("displayName") if pd.notnull(x) else x
        )
        df = df[list(COLS_EVENTS.keys())]

    return df
