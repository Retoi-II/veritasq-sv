import streamlit as st
import logging
import soccerdata as sd
import pandas as pd
<<<<<<< HEAD
import time
import socceraction

from collections.abc import Iterable
from config.settings import Settings, GET_WHOSCORED
from config.langs import translator
from utils.wyscout import Wyscout
from utils import ws_patch as wsp, helpers as hlp
=======

from collections.abc import Iterable
from config.settings import GET_WHOSCORED, GET_PATH
from utils.wyscout import Wyscout
from utils import ws_patch as wsp
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
from utils.logger import StreamlitLogHandler
from soccerdata._config import BASE_DIR
from soccerdata.whoscored import WHOSCORED_DATADIR
from soccerdata.fbref import FBREF_DATADIR
from pathlib import Path
<<<<<<< HEAD
from pages.dashboard import render_cascading_config, load_regional_data, parse_season_string

# ------------------------------------------------------------------------------- #

TITLE = "Data Exploration"
st.set_page_config(
    page_title=TITLE,
    layout="centered"
)

set = Settings()
_ = translator.translate

config, conf, is_loaded = hlp.initialize_state()


# =============================================================================== #
# -- UI STRUCTURE AND LOG HANDLER ----------------------------------------------- #
# =============================================================================== #

menu = st.empty()
col1, col2 = st.columns([1,2])
instruction_menus = st.empty()
instruction = st.empty()
with col1:
    left = st.empty()
    cfg_save = st.empty()
with col2:
    status_message = st.empty()
    menus = st.empty()
    explore = st.container()
    with explore:
        form_ids = st.container()
        exploration = st.empty()
log_ui = st.container(height=200, border=False)
with log_ui:
=======


# ------------------------------------------------------------------------------- #
# -- UI STRUCTURE AND LOG HANDLER ----------------------------------------------- #
# ------------------------------------------------------------------------------- #

menu = st.empty()
col1, col2 = st.columns([1,2])
with col1:
    left = st.empty()
with col2:
    menus = st.empty()
    exploration = st.empty()
with st.container(height=200, border=False):
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
    log_ui_placeholder = st.empty()

# ------------------------------------------------------------------------------- #

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()

ui_handler = StreamlitLogHandler(log_ui_placeholder)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S")
ui_handler.setFormatter(formatter)
root_logger.addHandler(ui_handler)


# ------------------------------------------------------------------------------- #
# -- MAIN SECTION --------------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def main():
    # -- 1ST SECTION - DATA CONTROL --------------------------------------------- #

    opt_menus = []
    option_map = {
<<<<<<< HEAD
        3: "Domain Understanding",
        # 1: "FBref",
        2: "Data Understanding",
    }
    selection = menu.segmented_control(
        TITLE,
        options=option_map.keys(),
        format_func=lambda option: option_map[option],
        selection_mode="single",
        width="stretch",
        default=3
=======
        1: "FBref",
        2: "WhoScored",
        3: "Wyscout"
    }
    selection = menu.segmented_control(
        "Menu",
        options=option_map.keys(),
        format_func=lambda option: option_map[option],
        selection_mode="single",
        width="stretch"
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
    )

    # ---- 1st Column - Configuration ------------------------------------------- #

    scraper = ""

    with left.container():
<<<<<<< HEAD
        config_elements = {
            "select_region": st.empty(), "caption_region": st.empty(),
            "select_tournament": st.empty(), "caption_tournament": st.empty(),
            "select_season": st.empty(), "caption_season": st.empty(),
            "select_directory": st.empty(), "caption_directory": st.empty()
        }
        opt_data_dir = st.text_input("Scraping data location: ", value="")
        st.caption("Leave blank to use the system environment")
=======
        opt_data_dir = st.text_input("Scraping data location: ", value="")
        st.caption("Leave blank to use the system drive")
        opt_path_to_browser = st.text_input("Browser Directory: ", value="")
        st.caption("Leave blank to use os default browser")
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
        opt_no_cache = st.checkbox("No Cache", value=False)
        st.caption("Uncheck (recommended): use cached data.\n\nCheck (slower): keep the data update.")
        opt_no_store = st.checkbox("No Store", value=False)
        st.caption("Uncheck: keep cached data (fills up the disk).\n\nCheck: discard cached data (leaves no footprint).")
        
        if not opt_data_dir:
            opt_data_dir = None
        else:
            opt_data_dir = Path(opt_data_dir)
<<<<<<< HEAD
=======
        if not opt_path_to_browser:
            opt_path_to_browser = None
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
    
    # ---- 2nd Column - Menu Selection ------------------------------------------ #
    # ------ case 1: Menu Selection for FBref ----------------------------------- #

    if selection == 1:
        opt_menus = menus.multiselect(
            "Select data to explore: ",
            options=[
                "Read Leagues (FBref)",
                "Read Seasons (FBref)", "etc"
            ]
        )
        scraper = "fb"

    # ------- case 2: Menu Selection for WhoScored ------------------------------ #

    if selection == 2:
        opt_menus = menus.multiselect(
            "Select data to explore: ",
            options=[
                "Read Seasons (WhoScored)",
                "Read Seasons Stages (WhoScored)",
                "Read Missing Players (WhoScored)",
<<<<<<< HEAD
                "Read Events (WhoScored)",
                "Read Events (Raw JSON)"
=======
                "Read Schedule and Events (WhoScored)",
                "etc"
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
            ]
        )
        scraper = "ws"

<<<<<<< HEAD
        # --- case 04-0: Load Layout Requirements ----------------------------------- #
        df_regional = load_regional_data(GET_WHOSCORED['regional'])
        prev_settings = {
            'region': conf['cfg_region_prev'], 'tournament': conf['cfg_tournament_prev'],
            'season': conf['cfg_season_prev'], 'directory': conf['directory_value']
        }
        
        # --- case 04-1: Render Layout ---------------------------------------------- #
        cfg_region, cfg_tournament, cfg_season, opt_path_to_browser = render_cascading_config(df_regional, prev_settings, config_elements)
        
        if not opt_path_to_browser:
            opt_path_to_browser = None
        
        # --- case 04-2: session_state Values Assignment ---------------------------- #
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
            st.warning(f"{_("app.dashboard.case_04-2.warning")}: {e}") # Error determining league strings
            season_int, league_str = "", ""


        # --- case 05-2: Load Save Configuration Button ----------------------------- #
        if cfg_save.button(_("app.dashboard.cfg_save.label"), width="stretch"): # Save
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
                    'directory': opt_path_to_browser,
                }
                st.session_state['team_badge'] = {'team_a': st.session_state.team_a, 'team_b': st.session_state.team_b}
                set.logMsg(f"{_("app.dashboard.cfg_save.custom")}!", level=5, container=status_message) # Configuration saved
                time.sleep(1)
                st.rerun()
            else:
                st.warning(_("app.dashboard.cfg_save.warning")) # Please fill region, tournament, and season


    # ------- case 2: Menu Selection for WhoScored ------------------------------ #

    if selection == 3:
        opt_menus = instruction_menus.multiselect(
            "Select explanation about: ",
            options=[
                "Domain Understanding",
                "Data Understanding",
                "Configuration"
            ]
        )
        left.empty()
        cfg_save.empty()
        with instruction.container():
            if "Domain Understanding" in opt_menus:
                with st.expander("Domain Understanding"):
                    pass
            if "Data Understanding" in opt_menus:
                with st.expander("Data Understanding"):
                    pass
            if "Configuration" in opt_menus:
                with st.expander("Configuration"):
                    pass
=======
    # ------- case 3: Menu Selection for Wyscout -------------------------------- #

    if selection == 3:
        opt_menus = menus.multiselect(
            "Select data to explore: ",
            options=[
                "Read Player Data (Wyscout)",
                "Read Teams Data (Wyscout)", "etc"
            ]
        )
        scraper = "wy"
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431


    # ---- 2nd Column - Scraper Initialization ---------------------------------- #
    # ------ case 1: Scraper initialization for FBref --------------------------- #
        
    if scraper == "fb":
        fb = sd.FBref(
            path_to_browser=opt_path_to_browser,
            data_dir=FBREF_DATADIR,
            headless=True,
            no_cache=opt_no_cache,
            no_store=opt_no_store
        )

    # ------ case 2: Scraper Initialization for WhoScored ----------------------- #
        
    elif scraper == "ws":
        sd.WhoScored.read_seasons = wsp.read_seasons_patch
        sd.WhoScored.read_season_stages = wsp.read_season_stages_patch
        sd.WhoScored.read_schedule = wsp.read_schedule_patch

        def init_whoscored(
            leagues: str | list[str] | None = None,
            seasons: str | int | Iterable[str | int] | None = None
        ):
            ws = sd.WhoScored(
                path_to_browser=opt_path_to_browser,
                data_dir=WHOSCORED_DATADIR,
                headless=True,
                no_cache=opt_no_cache,
                no_store=opt_no_store,
                seasons=seasons,
                leagues=leagues
            )
            return ws
        
<<<<<<< HEAD
        league = league_str
        season = season_int
        ws = init_whoscored(leagues=league, seasons=season)

        try:
            with form_ids:
                with st.form(key='my_form', border=False):
                    schedule = ws.read_schedule()
                    with st.expander("Id selection"): 
                        ids = st.multiselect("Select IDS", options=schedule["game_id"])
                        ids_info = f"{len(ids)} records" if len(ids) >= 5 else ids
                        load_cache = st.toggle("Load Matches Cache")
                        form = st.form_submit_button(label='Run Analysis')
                        with st.expander("Game Info"):
                            st.dataframe(schedule.reset_index()[['game_id', 'game', 'league', 'season', 'home_team', 'away_team']], hide_index=True)
                        st.info(f"{league}_{season} ids: {ids_info}")
                    if form:
                        st.toast(f"Target ids has been set! Proceed to select the data explore option")
                    
                    if load_cache:
                        sd.WhoScored.read_events = wsp.read_events
                        with st.spinner(show_time=True):
                            if ids: events = ws.read_events(match_id=ids, output_fmt="raw_nested")
                            else: st.warning("Please select target id")
                
        finally:
            if ws._driver: ws._driver.quit()
=======
    # ------ case 3: Scraper Initialization for Wyscout ------------------------- #
        
    elif scraper == "wy":
        @st.cache_resource
        def init_wyscout():
            return Wyscout()
        
        wy = init_wyscout()
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431


    # ---- 2nd Column - Menu Content -------------------------------------------- #
        
    with exploration.container():

        # ---- case 1: Menu Content for FBref ----------------------------------- #

        if "Read Leagues (FBref)" in opt_menus:
            try:
                with st.expander("Read Leagues"):
                    leagues = fb.read_leagues()
                    st.dataframe(leagues)
            finally:
                if fb._driver: fb._driver.quit()

        # ----------------------------------------------------------------------- #

        if "Read Seasons (FBref)" in opt_menus:
            try:
                with st.expander("Read Seasons"):
                    seasons = fb.read_seasons()
                    st.dataframe(seasons)
            finally:
                if fb._driver: fb._driver.quit()


        # ---- case 2: Menu Content for WhoScored ------------------------------- #

        if "Read Seasons (WhoScored)" in opt_menus:
<<<<<<< HEAD
=======
            ws = init_whoscored()
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
            try:
                with st.expander("Read Seasons"):
                    seasons = ws.read_seasons()
                    st.dataframe(seasons)
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
                    
        if "Read Seasons Stages (WhoScored)" in opt_menus:
<<<<<<< HEAD
=======
            ws = init_whoscored()
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
            try:
                with st.expander("Read Seasons Stages"):
                    seasons_stages = ws.read_season_stages()
                    st.dataframe(seasons_stages)
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
                    
        if "Read Missing Players (WhoScored)" in opt_menus:
<<<<<<< HEAD
            try:
                with st.expander("Read Missing Players"):
                    if form:
                        missing_players = ws.read_missing_players(match_id=ids, force_cache=True)
                        st.dataframe(missing_players)
                    else:
                        st.warning("Please input the ids")
=======
            ws = init_whoscored(leagues="ENG-Premier League", seasons=2526)
            try:
                with st.expander("Read Missing Players (WhoScored)"):
                    missing_players = ws.read_missing_players(match_id=1903153, force_cache=True)
                    st.dataframe(missing_players)
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
                    
<<<<<<< HEAD
        if "Read Events (WhoScored)" in opt_menus:
            try:
                with st.expander(f"Read Events (Dataframe) from {ids_info}"):
                    file_path = GET_WHOSCORED['spadl'](league, season, "spadl")

                    st.caption("spadl")
                    def save_spadl(league=league, season=season) -> pd.DataFrame:
                        spadl = ws.read_events(output_fmt="spadl", match_id=ids)
                        spadl.to_parquet(GET_WHOSCORED['spadl'](league, season, "spadl"))
                        return spadl

                    if not file_path.exists():
                        save_spadl(league, season)

                    df = pd.read_parquet(file_path)

                    if ids:
                        df_spadl = df[df["game_id"].isin(ids)].reset_index(drop=True)
                        st.dataframe(df_spadl)
                    else:
                        st.warning("Please input the ids")

                    # st.caption("events")
                    # events = ws.read_events(match_id=1903117, output_fmt="events")
                    # st.dataframe(events.reset_index(), hide_index=False)
                    # events = ws.read_missing_players(match_id=ids, force_cache=True)
                    # st.write(events)

                    # ----------------------------------------------------------- #

                    st.caption("atomic-spadl")
                    file_path = GET_WHOSCORED['spadl'](league, season, "atomic-spadl")
                    
=======
        if "Read Schedule and Events (WhoScored)" in opt_menus:
            league = "ENG-Premier League"
            season = 2526
            ws = init_whoscored(leagues=league, seasons=season)
            try:
                with st.expander("Read Schedule"):
                    schedule = ws.read_schedule()
                    ids = schedule['game_id'][:2]
                    st.dataframe(schedule)
                
                with st.expander("Read Events"):
                    st.info(f"{league}_{season}")

                    st.caption("spadl")
                    df = pd.read_parquet(GET_WHOSCORED['spadl'](league, season, "spadl"))
                    st.dataframe(df[df['game_id'] == 1903117] ) # .reset_index(drop=True))
                    def save_spadl(league=league, season=season) -> pd.DataFrame:
                        spadl = ws.read_events(output_fmt="spadl")
                        spadl.to_parquet(GET_WHOSCORED['spadl'](league, season, "spadl"))
                        return spadl

                    st.caption("events")
                    events = ws.read_events(match_id=1903117, output_fmt="events")
                    st.dataframe(events.reset_index(), hide_index=False)
                    events = ws.read_missing_players(match_id=ids, force_cache=True)
                    st.write(events)

                    st.caption("atomic-spadl")
                    df = pd.read_parquet(GET_WHOSCORED['spadl'](league, season, "atomic-spadl"))
                    st.dataframe(df[df['game_id'] == 1903117])
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
                    def save_atomic_spadl(league=league, season=season) -> pd.DataFrame:
                        aspadl = ws.read_events(output_fmt="atomic-spadl")
                        aspadl.to_parquet(GET_WHOSCORED['spadl'](league, season, "atomic-spadl"))
                        return aspadl

<<<<<<< HEAD
                    if not file_path.exists():
                        save_atomic_spadl(league, season)
                    
                    df = pd.read_parquet(file_path)

                    if ids:
                        df_aspadl = df[df["game_id"].isin(ids)].reset_index(drop=True)
                        st.dataframe(df_aspadl)
                    else:
                        st.warning("Please input the ids")

=======
                    # api  = OptaLoader(
                    #     root=GET_PATH['base_dir'] / "cached_data" / "soccerdata",
                    #     parser="whoscored"
                    # )
                    
                    # st.text(api.competitions())
                    # st.text(api.games(2, 10743))
                    # st.text(api.teams(1903117))
                    # st.text(api.players(1903117))
                    # st.text(api.events(1903117))
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
<<<<<<< HEAD

        if "Read Events (Raw JSON)" in opt_menus:
            try:
                with st.container(height=600, border=False):
                    with st.expander(f"Read Events (Raw JSON) from {ids_info}"):
                        sd.WhoScored.read_events = wsp.read_events
                        st.caption("raw_nested")
                        if ids:
                            for i, id in enumerate(ids):
                                st.caption(f"{i}/{len(ids)} [{id}]")
                                events = ws.read_events(match_id=id, output_fmt="raw_nested")
                                st.json(events, expanded=False)
                        else:
                            st.warning("Please input the ids")
            finally:
                if ws._driver: ws._driver.quit()


        # ----------------------------------------------------------------------- #
=======
        
        if "Read Player Data (Wyscout)" in opt_menus:
            with st.expander("Read Player Data"):
                try:
                    # 1. Fetch data as structured Pandas DataFrame
                    df_players = wy.get_dataframe('players')

                    # 2. Search sub-feature
                    player_search = st.text_input("🔍 Quick search player name:", key="player_search")
                    if player_search:
                        name_col = next((col for col in ['shortName', 'name', 'lastName'] if col in df_players.columns), df_players.columns[0])
                        df_players = df_players[df_players[name_col].astype(str).str.contains(player_search, case=False, na=False)]
                    
                    # 3. Render DataFrame
                    st.dataframe(df_players, use_container_width=True, hide_index=True)

                except Exception as e:
                    st.error(f"Could not load player data: {e}")

        # ----------------------------------------------------------------------- #

        if "Read Teams Data (Wyscout)" in opt_menus:
            with st.expander("Read Teams Data"):
                try:
                    df_teams = wy.get_dataframe('teams')
                    team_search = st.text_input("🔍 Quick search team name:", key="team_search")

                    if team_search:
                        name_col = next((col for col in ['name', 'officialName', 'shortName'] if col in df_teams.columns), df_teams.columns[0])
                        df_teams = df_teams[df_teams[name_col].astype(str).str.contains(team_search, case=False, na=False)]
                    
                    st.dataframe(df_teams, use_container_width=True, hide_index=True)
                
                except Exception as e:
                    st.error(f"Could not load team data: {e}")

        # ----------------------------------------------------------------------- #
        
        # if "Read Events Data (Wyscout)" in opt_menus:
        #     with st.expander("Read Events Data"):
        #         try:
        #             df_events = wy.get_dataframe('1903496')
        #             st.dataframe(df_events, use_container_width=True, hide_index=True)
        #             df_actions = convert_to_actions(df_events)
        #             st.dataframe(df_actions)

        #         except Exception as e:
        #             st.error(f"Could not load events data: {e}")

>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431
        
if __name__ == "__main__":
    main()
