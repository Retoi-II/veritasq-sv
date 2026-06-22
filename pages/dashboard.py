import json
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import soccerdata as sd
import streamlit as st
import unicodedata
import difflib

from app import footer
from config.langs import translator
from config.settings import GET_FBREF, GET_PATH, GET_WHOSCORED, Settings
from rapidfuzz import fuzz
from utils import display as dp
from utils import ws_patch as wsp
from utils.logger import StreamlitLogHandler

# --- INITIALIZATION & SOCCERDATA PATCHING ------------------------------------- #

set = Settings()
_ = translator.translate

# Apply WhoScored monkey-patches globally on execution
sd.WhoScored.read_seasons = wsp.read_seasons_patch
sd.WhoScored.read_season_stages = wsp.read_season_stages_patch
sd.WhoScored.read_schedule = wsp.read_schedule_patch


# --- DATA ACCESS LAYER (CACHED) ----------------------------------------------- #

# @st.cache_data
def load_regional_data(filepath: str | Path) -> pd.DataFrame:
    """Loads and caches the regional configurations."""
    return pd.read_csv(filepath)


# @st.cache_data
def load_team_data(
    team_season_path: str | Path, map_path: str | Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Loads and unflattens team data while caching dataframe structures."""
    if Path(team_season_path).exists() and Path(map_path).exists():
        flat_df = pd.read_csv(team_season_path, index_col=[0, 1, 2])
        with open(map_path, 'r') as f:
            config_data = json.load(f)
        return dp.unflatten_with_config(flat_df, config_data), flat_df
    return pd.DataFrame(), pd.DataFrame()


# @st.cache_data
def call_read_player_season_stats(df_file: str | Path, config_file: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reads and parses player structural metrics from disk."""
    if Path(df_file).exists() and Path(config_file).exists():
        dtype_spec = {"league": str, "season": str}
        df = pd.read_csv(df_file, index_col=[0, 1, 2, 3], dtype=dtype_spec)
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        return df, dp.unflatten_with_config(df, config_data)
    return pd.DataFrame(), pd.DataFrame()


# --- HELPER UTILITIES --------------------------------------------------------- #

def call_club_registry(data: str | pd.Series, from_source: str, to_source: str) -> str | pd.Series:
    """Maps team naming schemas cleanly across dynamic data source formats."""
    if isinstance(data, str):
        temp_series = pd.Series([data], dtype="string[python]")
        translated_series = set.load_club_registry(temp_series, from_source, to_source)
        return str(translated_series.iloc[0])
    elif isinstance(data, pd.Series):
        return set.load_club_registry(data, from_source, to_source)
    else:
        raise TypeError("Input must be either a string or a pandas Series.")


def parse_season_string(season_str: str) -> int | str:
    """Safely converts standard season strings (e.g. '23/24') into internal integers."""
    if len(season_str) == 9:
        return int(season_str[2:4] + season_str[7:9])
    return ""


def initialize_state() -> None:
    """Maintains atomic persistence layers for multi-page user interactions."""
    PLACEHOLDER = "Select a team..."
    if "team_a" not in st.session_state: 
        st.session_state.team_a = PLACEHOLDER
    if "team_b" not in st.session_state: 
        st.session_state.team_b = PLACEHOLDER
    if "cfg_scraper" not in st.session_state: 
        st.session_state.cfg_scraper = {}


def get_default_index(options_list: list[Any], prev_value: Any) -> int | None:
    """Safely searches list records to avoid indexing exceptions inside inputs."""
    return options_list.index(prev_value) if prev_value in options_list else None


# --- UI LAYOUT MODULES -------------------------------------------------------- #

def render_cascading_config(
    df: pd.DataFrame, 
    prev_settings: dict[str, Any],
    containers: dict[str, Any]
) -> tuple[str, str, str, str]:
    """Builds interactive config workflows for Region -> Tournament -> Season mappings."""
    
    # 1. Region Selection
    regions = df['region'].drop_duplicates().tolist()
    cfg_region = containers["select_region"].selectbox(
        "Config Region:", regions, index=get_default_index(regions, prev_settings.get('region'))
    )
    if cfg_region:
        set.logMsg(f"Selected Region: :green[{cfg_region}]", level=2, container=containers["caption_region"])
    else:
        footer()
        st.stop()

    # 2. Tournament Selection
    tournaments = df[df['region'] == cfg_region]['tournament'].unique().tolist()
    cfg_tournament = containers["select_tournament"].selectbox(
        "Config Tournament:", tournaments, index=get_default_index(tournaments, prev_settings.get('tournament'))
    )
    if cfg_tournament:
        set.logMsg(f"Selected Tournament: :green[{cfg_tournament}]", level=2, container=containers["caption_tournament"])
    else:
        footer()
        st.stop()

    # 3. Season Selection
    seasons_df = df[(df['region'] == cfg_region) & (df['tournament'] == cfg_tournament)]
    seasons = seasons_df['wh_season_name'].unique().tolist()
    cfg_season = containers["select_season"].selectbox(
        "Config Season:", seasons, index=get_default_index(seasons, prev_settings.get('season'))
    )
    if cfg_season:
        set.logMsg(f"Selected Season: :green[{cfg_season}]", level=2, container=containers["caption_season"])
    else:
        footer()
        st.stop()

    # 4. Working Directory Config
    directory = containers["select_directory"].text_input("Browser Directory", value=prev_settings.get("directory", ''))
    dir_label = directory if directory else "system defined"
    set.logMsg(f"Directory Location: :green[{dir_label}]", level=2, container=containers["caption_directory"])

    return cfg_region, cfg_tournament, cfg_season, directory


def render_team_selectors(flat_df: pd.DataFrame, selectors: dict[str, Any]) -> None:
    """Updates team UI options ensuring cross-selection exclusivity rules."""
    PLACEHOLDER = "Select a team..."
    
    if flat_df.index.get_level_values != 1:
        flat_df = flat_df.sort_values(by="home_team", ascending=True)
        option_map = list(flat_df['home_team'].unique())
    else:
        option_map = list(flat_df.index.get_level_values(2).unique())

    team_1_options = [PLACEHOLDER] + [opt for opt in option_map if opt != st.session_state.team_b]
    team_2_options = [PLACEHOLDER] + [opt for opt in option_map if opt != st.session_state.team_a]

    if st.session_state.team_a not in team_1_options:
        st.session_state.team_a = PLACEHOLDER
    if st.session_state.team_b not in team_2_options:
        st.session_state.team_b = PLACEHOLDER
    
    selectors["team_1"].selectbox(
        "Team 1:", options=team_1_options, key="team_a",
        on_change=dp.update_team_in_config, kwargs={'team_key': "team_a", 'placeholder': PLACEHOLDER}
    )
    selectors["team_2"].selectbox(
        "Team 2:", options=team_2_options, key="team_b",
        on_change=dp.update_team_in_config, kwargs={'team_key': "team_b", 'placeholder': PLACEHOLDER}
    )


# --- MAIN CONTROLLER ---------------------------------------------------------- #

def main() -> None:
    Path(GET_PATH['cache_ws']).mkdir(parents=True, exist_ok=True)
    Path(GET_PATH['cache_fb']).mkdir(parents=True, exist_ok=True)

    initialize_state()
    config = st.session_state.get('cfg_scraper', {})
    team_badge_state = st.session_state.get('team_badge', {})

    # Map state structures
    conf = {
        'cfg_region_prev': config.get("region"),
        'cfg_tournament_prev': config.get("tournament"),
        'cfg_season_prev': config.get("season"),
        'directory_value': config.get("directory", ''),
        'team_a_prev': team_badge_state.get("team_a", ''),
        'team_b_prev': team_badge_state.get("team_b", ''),
    }

    # Layout Definitions
    col1, col2, col3 = st.columns([2, 5, 2])

    with col1:
        with st.container(border=True, horizontal_alignment="center"):
            st.text("Configuration")
            config_elements = {
                "select_region": st.empty(), "caption_region": st.empty(),
                "select_tournament": st.empty(), "caption_tournament": st.empty(),
                "select_season": st.empty(), "caption_season": st.empty(),
                "select_directory": st.empty(), "caption_directory": st.empty()
            }

    with col2:
        with st.container(border=True) as team_badge_container:
            team1_col, team2_col, save_col = st.columns([2, 2, 1])
            team_selectors = {"team_1": team1_col.empty(), "team_2": team2_col.empty()}
            
            with save_col:
                with st.container(vertical_alignment="bottom", height="stretch", horizontal=True, horizontal_alignment="center"):
                    cfg_save = st.empty()
            logos_area = st.container()
        
        team_df_container = st.container()
        status_message = st.empty()

    with col3:
        with st.container(border=True):
            cfg_show = st.empty()
            if "cfg_scraper" in st.session_state and st.session_state.cfg_scraper:
                cfg_show.table(dp.display_config(st.session_state.cfg_scraper), border="horizontal", width="stretch")
            else:
                cfg_show.info("No configurations.")
            
    with st.container(height=100, border=False):
        log_ui_placeholder = st.empty()

    # Log Layer Setup
    if "session_logs" in st.session_state and st.session_state.session_logs:
        log_ui_placeholder.code("\n".join(st.session_state.session_logs), language="log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    ui_handler = StreamlitLogHandler(log_ui_placeholder)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S")
    ui_handler.setFormatter(formatter)
    root_logger.addHandler(ui_handler)

    df_regional = load_regional_data(GET_WHOSCORED['regional'])
    prev_settings = {
        'region': conf['cfg_region_prev'], 'tournament': conf['cfg_tournament_prev'],
        'season': conf['cfg_season_prev'], 'directory': conf['directory_value']
    }
    
    cfg_region, cfg_tournament, cfg_season, directory = render_cascading_config(df_regional, prev_settings, config_elements)

    # Resolve Context String Keys
    try:
        if "flg" not in config and "season" not in config:
            flags = df_regional[df_regional['region'] == cfg_region]['flg'].dropna().unique()
            league_str = f"{", ".join(str(x) for x in flags)}-{cfg_tournament}"
            season_str = cfg_season.split('/')[0]
            season_int = parse_season_string(cfg_season)
        else:
            league_str = f"{config['flg']}-{config['tournament']}"
            season_str = config['season'].split('/')[0]
            season_int = parse_season_string(config['season'])
    except Exception as e:
        st.warning(f"Error determining league strings: {e}")
        season_int, league_str = "", ""

    schedule_df = pd.read_csv(GET_WHOSCORED['schedule'])
    loaded_flat_df = schedule_df[(schedule_df['season'] == season_int) & (schedule_df['league'] == league_str)]

    try:
        render_team_selectors(loaded_flat_df, team_selectors)
    except Exception as e:
        st.warning(f"Cannot load team selection. {e}")

    # Config Mutation Execution
    if cfg_save.button("Save", width="stretch"):
        if all([cfg_region, cfg_tournament, cfg_season]):
            match = df_regional[
                (df_regional['region'] == cfg_region) & 
                (df_regional['tournament'] == cfg_tournament) & 
                (df_regional['wh_season_name'] == cfg_season)
            ]
            st.session_state['cfg_scraper'] = {
                'region': cfg_region,
                'wh_region_id': ", ".join(str(int(x)) for x in match['wh_id'].dropna().unique()),
                'tournament': cfg_tournament,
                'wh_tournament_id': ", ".join(str(int(x)) for x in match['wh_tour_id'].dropna().unique()),
                'season': cfg_season,
                'wh_season_id': ", ".join(str(int(x)) for x in match['wh_season_id'].dropna().unique()),
                'flg': ", ".join(str(x) for x in match['flg'].dropna().unique()),
                'directory': directory,
            }
            st.session_state['team_badge'] = {'team_a': st.session_state.team_a, 'team_b': st.session_state.team_b}
            set.logMsg("Configuration saved!", level=5, container=status_message)
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Please fill region, tournament, and season")

    # Image Processing Flow
    with logos_area:
        if "team_a" in st.session_state and "team_b" in st.session_state:
            if "team_badge" in st.session_state:
                tb_df = pd.read_csv(GET_PATH['cache_ws'] / "_team_id.csv")
                id_a = tb_df[tb_df['team_name'] == st.session_state.team_a]['team_id'].item()
                id_b = tb_df[tb_df['team_name'] == st.session_state.team_b]['team_id'].item()
                
                logo_col1, logo_col2 = st.columns(2)
                with logo_col1:
                    with st.container(border=True, horizontal=True, horizontal_alignment="center"):
                        st.image(GET_WHOSCORED['badge'](int(id_a)))
                with logo_col2:
                    with st.container(border=True, horizontal=True, horizontal_alignment="center"):
                        st.image(GET_WHOSCORED['badge'](int(id_b)))
        elif not conf['team_a_prev'] and not conf['team_b_prev']:
            st.info("Please fill the configuration section")
        else:
            st.info("Choose teams")

    # Scraper & Data Synthesis Loop Execution
    with team_df_container:
        if st.session_state.get('team_badge', {}).get('team_a', "Select a team...") != "Select a team..." and \
           st.session_state.get('team_badge', {}).get('team_b', "Select a team...") != "Select a team...":
            try:
                team_a_st = st.session_state.team_badge['team_a']
                team_b_st = st.session_state.team_badge['team_b']
                team_a_fb = call_club_registry(team_a_st, "whoscored", "fbref")
                team_b_fb = call_club_registry(team_b_st, "whoscored", "fbref")
                team_a_cn = call_club_registry(team_a_st, "whoscored", "fbref")

                # df = pl.scan_csv(GET_WHOSCORED['schedule'])
                # st.dataframe(df.collect())


                expander = 1
                if expander:
                    with st.expander("Player Metadata"):

                        # 1. FBRef Players List Dataset from ReadPlayerSeasonStats
                        fb_psstats_flat, _org_df = call_read_player_season_stats(
                            GET_FBREF['player_season']("standard"), GET_FBREF['player_season_map']("standard")
                        )
                        fb_psstats = fb_psstats_flat.reset_index()

                        # 2. Get Team ID (Wh_ID) from WhoScored ReadSchedule
                        fb_psstats_mg = fb_psstats.rename(columns={
                            'team': "fb_team",
                            'player': "fb_player"
                        })
                        fb_psstats_mg['wh_team'] = call_club_registry(
                            fb_psstats_mg['fb_team'],
                            from_source="fbref",
                            to_source="whoscored"
                        )
                        wh_schedule = pd.read_csv(GET_WHOSCORED['schedule'])
                        team_lookup = wh_schedule[['home_team', 'home_team_id']].drop_duplicates().rename(
                            columns={
                                'home_team': "wh_team",
                                'home_team_id': "wh_team_id"
                            }
                        )
                        fb_psstats_mg = fb_psstats_mg.merge(team_lookup, on="wh_team", how="left")
                        st.dataframe(fb_psstats_mg)

                        # 3. Get Player ID (Wh_ID) from WhoScored ReadEvents
                        if GET_WHOSCORED['game_info'].exists():
                            game_info = pd.read_json(GET_WHOSCORED['game_info'], lines=True)
                            filtered_games = game_info[
                                (game_info['season'] == season_int) & 
                                ((game_info['home_team'] == team_a_st) | (game_info['home_team'] == team_b_st))
                            ]
                            df_ids = filtered_games[['home_team', 'game_id']]
                            clubs = df_ids['home_team'].unique()

                            set.logMsg(_("app.ui.element.void"))
                            set.logMsg(f"Retrieve Events for **:green[{team_a_st}]** and **:green[{team_b_st}]**\n", level=4, container=status_message)
                            
                            ws_driver_instance = sd.WhoScored(league_str, season_int, no_cache=False, no_store=False)
                            events_accumulator = []

                            try:
                                total_clubs = len(clubs)
                                for i, club in enumerate(clubs, start=1):
                                    file_path = GET_PATH['events_path'](league_str, season_int, club)
                                    file_path.mkdir(parents=True, exist_ok=True)
                                    
                                    club_games = df_ids[df_ids['home_team'] == club]['game_id']
                                    total_games = len(club_games)

                                    for j, game_id in enumerate(club_games, start=1):
                                        file_name = GET_WHOSCORED['events'](season=season_int, league=league_str, game_id=game_id, team=club)

                                        if not file_name.exists():
                                            set.logMsg(f"\n:blue[INFO]&emsp;Fetch from WhoScored: Club ({i}/{total_clubs}) | Game ({j}/{total_games})\n&emsp;to **:green[{file_name}]**", level=4, container=status_message)
                                            fetched_events = ws_driver_instance.read_events(game_id)

                                            if not fetched_events.empty:
                                                fetched_events.to_csv(file_name, mode='w')
                                                set.logMsg(f":green[SUCCESS]&emsp;Saved dataset: **:green[{file_name}]**", level=5, container=status_message)
                                                events_accumulator.append(fetched_events)
                                                st.toast(f"Fetched events data to {file_name.name}", duration="short")
                                        else:
                                            try:
                                                set.logMsg(f"\n:blue[INFO]&emsp;Loading local file:\n&emsp;**:blue[{file_name}]**", level=4, container=status_message)
                                                local_df = pd.read_csv(file_name)
                                                if isinstance(local_df, pd.DataFrame) and not local_df.empty:
                                                    events_accumulator.append(local_df)
                                                    st.toast(f"Loaded local data for {file_name.name}", duration="short")
                                                else:
                                                    set.logMsg(f":red[ERROR]&emsp;Empty file encountered: {file_name.name}", level=404, container=status_message)
                                            except (pd.errors.EmptyDataError, pd.errors.ParserError) as err:
                                                set.logMsg(f"\n:red[ERROR]&emsp;Corrupted local file: {file_name.name}. Attempting fix...", level=404, container=status_message)
                                                recovered_events = ws_driver_instance.read_events(game_id)
                                                if not recovered_events.empty:
                                                    recovered_events.to_csv(file_name, mode='w')
                                                    events_accumulator.append(recovered_events)
                            finally:
                                # Safely clean up selenium browser drivers under all conditions
                                if ws_driver_instance._driver:
                                    ws_driver_instance._driver.quit()
                                    ws_driver_instance._driver = None
                                    set.logMsg("\n:green[SUCCESS]&emsp;Data loading routine complete. Browser driver closed cleanly.", level=1, container=status_message)

                    no_achor = 0
                    if no_achor:
                        def normalize_name(name):
                            if not isinstance(name, str):
                                return ""
                            
                            name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
                            return name.lower().replace("-", " ").strip() # .strip()
                        

                        df = fb_player = fb_psstats_mg
                        df_filtered = df[(df['league'] == "ENG-Premier League") & (df['season'].isin(['2223', '2324', '2425', '2526']))]
                        fb_player = df_filtered.drop_duplicates(subset=['fb_player']).copy()
                        st.text(fb_player.head)
                        fb_player['norm_name'] = fb_player['fb_player'].apply(normalize_name)
                        
                        wh_player = pd.read_csv('master_combined_player_playerid.csv')
                        st.caption("wh_player")
                        wh_player['norm_name'] = wh_player['player'].apply(normalize_name)

                        ws_names_list = wh_player['norm_name'].dropna().tolist()
                        mapping_dict = {}

                        for fb_orig, fb_norm in zip(fb_player['fb_player'], fb_player['norm_name']):
                            if not fb_norm:
                                continue
                            
                            # Check for an exact match first after normalization
                            if fb_norm in ws_names_list:
                                matched_ws_norm = fb_norm
                            else:
                                # Fallback to fuzzy string matching if exact normalization fails
                                # 'cutoff=0.80' implies an 80% similarity threshold
                                close_matches = difflib.get_close_matches(fb_norm, ws_names_list, n=1, cutoff=0.80)
                                matched_ws_norm = close_matches[0] if close_matches else None
                                
                            if matched_ws_norm:
                                # Get the original spelling from the WhoScored dataset
                                ws_orig = wh_player[wh_player['norm_name'] == matched_ws_norm]['player'].values[0]
                                mapping_dict[fb_orig] = ws_orig

                        # 4. Map the columns and merge cleanly
                        fb_player['WhoScored Match Name'] = fb_player['fb_player'].map(mapping_dict)
                        merged_df = pd.merge(fb_player, wh_player, left_on='WhoScored Match Name', right_on='player', how='left')

                        # Drop the helper columns before finalizing
                        merged_df = merged_df.drop(columns=['norm_name_x', 'norm_name_y', 'WhoScored Match Name'])
                        print(f"Successfully matched and merged {merged_df['player'].notna().sum()} rows automatically!")
                        st.caption("merged_df")
                        st.dataframe(merged_df)

                        wh_player = merged_df['player']
                        fb_player = merged_df['fb_player']

                        merged_df["name_match"] = merged_df["fb_player"] == merged_df["player"]
                        st.dataframe(merged_df[["fb_player", "player", "name_match"]])

                    
            except Exception as e:
                st.error(f"Processing routine halted unexpected: {e}")
                traceback.print_exc()
        else:
            st.info("The scraping initialization pipeline requires selection validations across both targeting groups.")


if __name__ == "__main__":
    main()
