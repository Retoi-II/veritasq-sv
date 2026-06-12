import json
import logging
import pandas as pd
import polars
import streamlit as st
import soccerdata as sd
import sys, time
import traceback

from app import footer
from config.settings import GET_PATH, GET_WHOSCORED, GET_FBREF, Settings
from config.langs import translator
from pathlib import Path
from rich import print
from typing import Any
from utils import display as dp
from utils import ws_patch as wsp
from utils.logger import StreamlitLogHandler


# ------------------------------------------------------------------------------- #
# -- PAGE LAYOUT ---------------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

col1, col2, col3 = st.columns([2,5,2])

with col1:
    with st.container(border=True, horizontal_alignment="center"):
        st.text("Configuration")

        antek1 = st.container()
        antek2 = st.container()
        
        with antek1:
            region_ui = st.container()
            tour_ui = st.container()
            season_ui = st.container()
            with region_ui:
                select_region = st.empty()
                caption_region = st.empty()
            with tour_ui:
                select_tournament = st.empty()
                caption_tournament = st.empty()
            with season_ui:
                select_season = st.empty()
                caption_season = st.empty()
        with antek2:
            directory_ui = st.container()
            with directory_ui:
                select_directory = st.empty()
                caption_directory = st.empty()
                st.caption("")
        
# ------------------------------------------------------------------------------- #

with col2:
    team_badge = st.container(border=True)
    with team_badge:
        logos = st.container()
        team1, team2, save = st.columns([2,2,1])
        with team1:
            team_1_selection = st.empty()
            caption_team1 = st.empty()
        with team2:
            team_2_selection = st.empty()
            caption_team2 = st.empty()
        with save:
            with st.container(vertical_alignment="bottom", height="stretch", horizontal=True, horizontal_alignment="center"):
                cfg_save = st.empty()
    team_df = st.container()
    status_message = st.empty()
    

# ------------------------------------------------------------------------------- #

with col3:
    with st.container(border=True):
        cfg_show = st.empty()

        if "cfg_scraper" in st.session_state:
            cfg_show.table(
                dp.display_config(st.session_state.cfg_scraper),
                border="horizontal", width="stretch"
            )
        else:
            cfg_show.info("No configurations.")
        
with st.container(height=100, border=False):
    log_ui_placeholder = st.empty()


# ------------------------------------------------------------------------------- #
# -- LOGGER ACCESS LAYER -------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

if "session_logs" in st.session_state and st.session_state.session_logs:
    initial_text = "\n".join(st.session_state.session_logs)
    log_ui_placeholder.code(initial_text, language="log")

# 1. Target the system-wide root logger instead of a named one
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 2. Completely strip away any pre-packaged handlers (like rich)
# This forces libraries to stop bypassing your Streamlit handler
root_logger.handlers.clear()

# 3. Connect your custom Streamlit UI handler to the root stream
ui_handler = StreamlitLogHandler(log_ui_placeholder)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S")
ui_handler.setFormatter(formatter)
root_logger.addHandler(ui_handler)

# 4. Optional: Add a standard console backup stream so you can still see output in terminal
console_backup = logging.StreamHandler(sys.stdout)
console_backup.setFormatter(formatter)
root_logger.addHandler(console_backup)


# ------------------------------------------------------------------------------- #
# -- VARIABLE DEFINITION -------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

sys.stdout.write("\033[H\033[2J")
sys.stdout.flush()

set = Settings()
_ = translator.translate

def call_soccerdata_whoscored(leagues, season):
    ws = sd.WhoScored(leagues, season, no_cache=False, no_store=False)
    return ws

sd.WhoScored.read_seasons = wsp.read_seasons_patch
sd.WhoScored.read_season_stages = wsp.read_season_stages_patch
sd.WhoScored.read_schedule = wsp.read_schedule_patch

def call_read_player_season_stats(df_file, config_file) -> tuple[pd.DataFrame, pd.DataFrame]:
    if Path(df_file).exists() and Path(config_file).exists():
        df = pd.read_csv(df_file, index_col=[0,1,2,3])
        with open(config_file, 'r') as f:
            config = json.load(f)
        return df, dp.unflatten_with_config(df, config)
    

config = st.session_state.get('cfg_scraper', {})
team_badge = st.session_state.get('team_badge', {})
conf = {
    'cfg_region_prev': config.get('region'),
    'cfg_tournament_prev': config.get('tournament'),
    'cfg_season_prev': config.get('season'),
    'directory_value': config.get('directory', ""),
    'team_a_prev': team_badge.get('team_a', ''),
    'team_b_prev': team_badge.get('team_b', ''),
}


# ------------------------------------------------------------------------------- #
# -- DATA ACCESS LAYER ---------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def load_regional_data(filepath: str | Path) -> pd.DataFrame:
    """Loads and caches the regional configurations."""
    return pd.read_csv(filepath)

def load_team_data(
    team_season_path: str | Path, 
    map_path: str | Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Loads and unflatten team data. Caches to prevent redundant disk I/O."""
    if Path(team_season_path).exists() and Path(map_path).exists():
        flat_df = pd.read_csv(team_season_path, index_col=[0, 1, 2])
        with open(map_path, 'r') as f:
            config = json.load(f)
        return dp.unflatten_with_config(flat_df, config), flat_df
    return pd.DataFrame(), pd.DataFrame()


# ------------------------------------------------------------------------------- #
# -- STATE MANAGEMENT LAYER ----------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def initialize_state() -> None:
    """Ensure all required session state variables exist."""
    PLACEHOLDER = "Select a team..."
    if "team_a" not in st.session_state: st.session_state.team_a = PLACEHOLDER
    if "team_b" not in st.session_state: st.session_state.team_b = PLACEHOLDER
    if "cfg_scraper" not in st.session_state: st.session_state.cfg_scraper = {}

def get_default_index(
    options_list: list[Any], 
    prev_value: Any
) -> int:
    """Helper to safely get dropdown indexes."""
    return options_list.index(prev_value) if prev_value in options_list else None


# ------------------------------------------------------------------------------- #
# -- UI COMPONENTS LAYER -------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def render_cascading_config(
    df: pd.DataFrame,
    config: dict[str, Any],
    prev_settings: dict[str, Any]
) -> tuple[str, str, str, str]:
    """Renders the Region -> Tournament -> Season cascading dropdowns."""
    regions: list[str] = df['region'].drop_duplicates().tolist()
    cfg_region = select_region.selectbox(
        "Config Region:",
        regions,
        index=get_default_index(regions, prev_settings.get('region'))
    )
    if cfg_region:
        set.logMsg(f"Selected Region: :green[{cfg_region}]", level=2, container=caption_region)
    else:
        footer()
        st.stop()

    # --------------------------------------------------------------------------- #

    tournaments: list[str] = (
        df[df['region'] == cfg_region]['tournament'].unique().tolist()
    )
    cfg_tournament = select_tournament.selectbox(
        "Config Tournamrnt:",
        tournaments,
        index=get_default_index(tournaments, prev_settings.get('tournament'))
    )
    if cfg_tournament:
        set.logMsg(f"Selected Tournament: :green[{cfg_tournament}]", level=2, container=caption_tournament)
    else:
        footer()
        st.stop()


    # --------------------------------------------------------------------------- #

    seasons: pd.DataFrame = (
        df[(df['region'] == cfg_region) & (df['tournament'] == cfg_tournament)]
    )
    seasons: list[str] = seasons['wh_season_name'].unique().tolist()
    cfg_season = select_season.selectbox(
        "Config Season:",
        seasons,
        index=get_default_index(seasons, prev_settings.get('season'))
    )
    if cfg_season:
        set.logMsg(f"Selected Season: :green[{cfg_season}]", level=2, container=caption_season)
    else:
        footer()
        st.stop()


    # --------------------------------------------------------------------------- #

    directory = select_directory.text_input(
        "Browser Directory",
        value=prev_settings.get('directory', '')
    )
    if not directory:
        set.logMsg(f"Directory Location: :green[system defined]", level=2, container=caption_directory)
    else:
        set.logMsg(f"Directory Location: :green[{directory}]", level=2, container=caption_directory)

    return cfg_region, cfg_tournament, cfg_season, directory

# ------------------------------------------------------------------------------- #

def render_team_selectors(
    flat_df: pd.DataFrame,
    dp_module: Any
) -> None:
    """Renders mutually exclusive team selectors."""
    PLACEHOLDER = "Select a team..."
    if flat_df.index.get_level_values != 1:
        flat_df = flat_df.sort_values(by='home_team', ascending=True)
        option_map: list[str] = (list(flat_df['home_team'].unique()))
    else:
        option_map: list[str] = (list(flat_df.index.get_level_values(2).unique()))

    team_1_options: list[str] = (
        [PLACEHOLDER] + [opt for opt in option_map if opt != st.session_state.team_b]
    )
    team_2_options: list[str] = (
        [PLACEHOLDER] + [opt for opt in option_map if opt != st.session_state.team_a]
    )

    if st.session_state.team_a not in team_1_options:
        st.session_state.team_a = PLACEHOLDER
    if st.session_state.team_b not in team_2_options:
        st.session_state.team_b = PLACEHOLDER
    
    team_1_selection.selectbox(
        "Team 1:",
        options=team_1_options,
        key="team_a",
        on_change=dp_module.update_team_in_config,
        kwargs={
            'team_key': "team_a",
            'placeholder': PLACEHOLDER
        }
    )
    team_2_selection.selectbox(
        "Team 2:",
        options=team_2_options,
        key="team_b",
        on_change=dp_module.update_team_in_config,
        kwargs={
            'team_key': "team_b",
            'placeholder': PLACEHOLDER
        }
    )


# ------------------------------------------------------------------------------- #
# -- MAIN APP CONTROLLER -------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def main() -> None:
    

    Path(GET_PATH['cache_ws']).mkdir(parents=True, exist_ok=True)
    Path(GET_PATH['cache_fb']).mkdir(parents=True, exist_ok=True)

    initialize_state()

    df = load_regional_data(GET_WHOSCORED['regional'])

    prev_settings = {
        'region': conf['cfg_region_prev'],
        'tournament': conf['cfg_tournament_prev'],
        'season': conf['cfg_season_prev'],
        'directory': conf['directory_value']
    }
    cfg_region, cfg_tournament, cfg_season, directory = (
        render_cascading_config(df, config, prev_settings)
    )

    # --------------------------------------------------------------------------- #

    try:
        if "flg" not in config and "season" not in config:
            flg = df[df['region'] == cfg_region]['flg']
            flg = flg.dropna().unique()
            flg_str = ", ".join(str(x) for x in flg)
            league_str = f"{flg_str}-{cfg_tournament}"
            season_str = cfg_season.split('/')[0]
            season_int = int(cfg_season[2:4] + cfg_season[7:9]) if len(cfg_season) == 9 else ""
        else:
            league_str = f"{config['flg']}-{config['tournament']}"
            season_str = config['season'].split('/')[0]
            season_int = int(config['season'][2:4] + config['season'][7:9]) if len(config['season']) == 9 else ""
    except Exception as e:
        st.warning(f"Error determining league strings: {e}")

    # --------------------------------------------------------------------------- #

    # team_season_path = (GET_FBREF['team_season'](league_str, season_str))
    # team_season_map_path = (GET_FBREF['team_season_map'](league_str, season_str))
    # org_df, loaded_flat_df = load_team_data(team_season_path, team_season_map_path)
    schedule_df = pd.read_csv(GET_WHOSCORED['schedule'])
    loaded_flat_df = schedule_df[(schedule_df['season'] == season_int) & (schedule_df['league'] == league_str)]

    try:
        render_team_selectors(loaded_flat_df, dp)
    except Exception as e:
        st.warning(f"Cannot load team selection. {e}")

    

    # --------------------------------------------------------------------------- #

    if cfg_save.button("Save", width="stretch"):
        if all([cfg_region, cfg_tournament, cfg_season]):
            # Filter and format configuration strings
            match = df[(df['region'] == cfg_region) & (df['tournament'] == cfg_tournament) & (df['wh_season_name'] == cfg_season)]
            
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
            st.session_state['team_badge'] = {
                'team_a': st.session_state.team_a,
                'team_b': st.session_state.team_b
            }
            set.logMsg("Configuration saved!", level=5, container=status_message)
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Please fill region, tournament, and season")


    # --------------------------------------------------------------------------- #

    with logos:
        if "team_a" in st.session_state and "team_b" in st.session_state:
            if "team_badge" in st.session_state:
                tb_df = pd.read_csv(GET_PATH['cache_ws'] / "_team_id.csv")
                id_a = tb_df[tb_df['team_name'] == st.session_state.team_a]['team_id'].item()
                id_b = tb_df[tb_df['team_name'] == st.session_state.team_b]['team_id'].item()
                col1, col2 = st.columns(2)
                with col1:
                    with st.container(border=True, horizontal=True, horizontal_alignment="center"): st.image(GET_WHOSCORED['badge'](int(id_a)))
                with col2:
                    with st.container(border=True, horizontal=True, horizontal_alignment="center"): st.image(GET_WHOSCORED['badge'](int(id_b)))
            else:
                st.text("Process 2 (else)")

        elif not conf['team_a_prev'] and not conf['team_b_prev']:
            st.info("Please fill the configuration section")
        else:
            st.info("Choose teams")

    # --------------------------------------------------------------------------- #

    with team_df:
        league_player_stats = pd.DataFrame()

        if "team_badge" not in st.session_state:
            st.session_state.team_badge = {"team_a": "Select a team...", "team_b": "Select a team..."}

        if st.session_state.team_badge['team_a'] != "Select a team..." and st.session_state.team_badge['team_b'] != "Select a team...":
            try:
                season_int = int(config['season'][2:4] + config['season'][7:9]) if len(config['season']) == 9 else ""
                team_a = st.session_state.team_badge['team_a']
                team_b = st.session_state.team_badge['team_b']

                # --------------------------------------------------------------- #

                with st.expander("Player Metadata"):
                    # 1. Fetch players list from FBref
                    psstats_flat, org_psstats = call_read_player_season_stats(
                        GET_FBREF['player_season']("standard"), GET_FBREF['player_season_map']("standard"))
                    df0 = psstats_flat.reset_index() # Players dataset from 2021 to 2526 -> df0
                    df1 = df0[
                        (df0['season'].isin([season_int])) & 
                        (df0['league'] == f"{config['flg']}-{config['tournament']}")
                    ].reset_index(drop=True) # filter by season and tournament -> df1
                    df2 = df1[(df1['team'] == team_a) | (df1['team'] == team_b)] # filter by team_a or team_b -> df2
                    # st.dataframe(df2)

                    # ----------------------------------------------------------- #

                    # 2. Fetch players id from WhoScored
                    game_info = pd.read_json(GET_WHOSCORED['game_info'], lines=True)
                    if GET_WHOSCORED['game_info'].exists():
                        df = game_info # Game Info (schedule) from 2021 to 2526 -> df
                        df1 = df[
                            (df['season'] == season_int) & 
                            ((df['home_team'] == team_a) | (df['home_team'] == team_b))
                        ] # filter by season and home_team (team_a or team_b) -> df1
                        df2 = df1[['home_team', 'game_id']] # home_team and game_id column from filtered df -> df2
                        # st.write(df2)

                        # ------------------------------------------------------- #
                        # ---------  EVENTS RETRIEVAL - Fetch game_id ----------- #

                        set.logMsg(_("app.ui.element.void"))
                        set.logMsg(f"Retrieve Events for **:green[{team_a}]** and **:green[{team_b}]**\n", level=4, container=status_message)
                        ws = call_soccerdata_whoscored(league_str, season_int)

                        def call_read_events(match_id):
                            events = ws.read_events(match_id)
                            return events
                        
                        def fetch_events_df(path: Path, events_df: pd.DataFrame) -> pd.DataFrame:
                            """
                            Attributes:
                                path (csv file location)
                                df (concatenation target DataFrame)
                                events_df (per id fetch DataFrame)
                            """
                            events_df.to_csv(path, mode='w') # Convert fetched DataFrame -> CSV
                            set.logMsg(f":green[SUCCESS]&emsp;:green[Save events DataFrame to path.]\n&emsp;**:green[{path}]**", level=5, container=status_message)
                            return events_df
                        
                        events_summary = pd.DataFrame()
                        total_clubs = len(df2['home_team'].unique())
                        for i, club in enumerate(df2['home_team'].unique(), start=1):
                            file_path = GET_PATH['events_path'](league_str, season_int, club)

                            try:
                                file_path.mkdir(parents=True, exist_ok=True)
                                club_games = df2[df2['home_team'] == club]['game_id']
                                total_games = len(club_games)

                                for j, id in enumerate(club_games, start=1):
                                    file_name = GET_WHOSCORED['events'](season=season_int, league=league_str, game_id=id, team=club)

                                    # -- CASE 1: File doesn't exist locally ----- #
                                    # ---------- ( FETCH MODE ) ----------------- #
                                    if not file_name.exists():
                                        set.logMsg(f"\n:blue[INFO]&emsp;:blue[Fetch events from WhoScored... Club ({i}/{total_clubs})) | Game ({j}/{total_games})]\n&emsp;to **:green[{file_name}]**", level=4, container=status_message)
                                        events = call_read_events(id)

                                        if not events.empty:
                                            events_df = fetch_events_df(file_name, events)
                                            events_summary = pd.concat([events_summary, events_df], ignore_index=True)
                                            st.toast(f"Successfully fetch events data to {file_name.name} from WhoScored", duration="short")
                                            
                                    # -- CASE 2: File does exist locally -------- #
                                    # ---------- ( OFFLINE LOAD MODE ) ---------- #
                                    else:
                                        try:
                                            set.logMsg(f"\n:blue[INFO]&emsp;Load events from local path...\n&emsp;**:blue[{file_name}]**", level=4, container=status_message)
                                            df = pd.read_csv(file_name) # Offline DataFrame
                                            if isinstance(df, pd.DataFrame) and not df.empty:
                                                set.logMsg(f":green[SUCCESS]&emsp;Events loaded from local path: {file_name.name}", level=5, container=status_message)
                                                events_summary = pd.concat([events_summary, df], ignore_index=True)
                                                st.toast(f"Successfully load events data for :green[{file_name.name}] from local path", duration="short")
                                            else:
                                                set.logMsg(f":red[ERROR]&emsp;:red[{file_name.name} exists but is empty.]", level=404, container=status_message)

                                        # -- CASE 3: File is corrupted ---------- #
                                        # ---------- ( RECOVERY MODE ) ---------- #
                                        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
                                            set.logMsg(f"\n:red[ERROR]&emsp;:red[File corrupted: {file_name.name}.]\n&emsp;**:red[({e}).]**", level=404, container=status_message)
                                            set.logMsg(f":blue[INFO]&emsp;Attempting automatic redownload...", level=4, container=status_message)
                                            events_fix = call_read_events(id)
                                            if not events_fix.empty:
                                                fetch_events_df(file_name, events_fix)
                                                events_df = pd.read_csv(file_name)
                                                events_summary = pd.concat([events_summary, events_df], ignore_index=True)
                                                set.logMsg(f":green[SUCCESS]&emsp;Corrupted file replaced successfully.", level=5, container=status_message)

                                        except Exception as e:
                                            print(f":red[ERROR]&emsp;:red[An unexpected error occurred while reading the file:] \n&emsp;{e}")
                                            st.error(e)
                                            
                            except Exception as e:
                                print(f"[red]ERROR\tProblem manipulating directory path for {club}: {e}[/red]")
                                st.error(e)
                        
                        if ws._driver:
                            ws._driver.quit()
                            ws._driver = None
                            set.logMsg("\n:green[SUCCESS]&emsp;Events loaded, driver is closed.", level=1, container=status_message)

                        if not ws._driver:
                            print("\n[blue]INFO[/blue]\t[bold blue]Browser is properly closed.[/bold blue]")
                            
                        events = events_summary
                        if not events.empty and (len(events['game_id'].unique()) == len(df2['game_id'].unique())):
                            if "qualifiers" in events.columns:
                                events["qualifiers"] = events["qualifiers"].apply(
                                    lambda x: ", ".join(map(str, x)) if isinstance(x, list) else str(x)
                                )
                            st.write(events)
                        else:
                            st.error("Fetched DataFrame is not complete.")
                                
                        # ------------------------------------------------------- #
                        # ---------  EVENTS RETRIEVAL - Fetch game_id ----------- #
                
            except Exception as e:
                print(f"[red]ERROR[/red]\tSome elements doesn't loaded: {e}")
                # print(f"[yellow]WARNING[/yellow]\t[bold yellow]Also make sure to save configuration before starting the process.[/bold yellow]")
                # st.info(f"[INFO] Always save the configuration before proceeding to the process.")
                st.error(f"[ERROR]\t{e}")
                traceback.print_exc()
        else:
            st.info("The process need both teams configurations.")
        
        if not league_player_stats.empty:
            st.dataframe(league_player_stats)

# ------------------------------------------------------------------------------- #

if __name__ == "__main__":
    main()
