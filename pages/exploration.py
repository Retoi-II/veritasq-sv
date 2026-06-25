import streamlit as st
import logging
import soccerdata as sd
import pandas as pd

from collections.abc import Iterable
from config.settings import GET_WHOSCORED, GET_PATH
from utils.wyscout import Wyscout
from utils import ws_patch as wsp
from utils.logger import StreamlitLogHandler
from soccerdata._config import BASE_DIR
from soccerdata.whoscored import WHOSCORED_DATADIR
from soccerdata.fbref import FBREF_DATADIR
from pathlib import Path


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
    )

    # ---- 1st Column - Configuration ------------------------------------------- #

    scraper = ""

    with left.container():
        opt_data_dir = st.text_input("Scraping data location: ", value="")
        st.caption("Leave blank to use the system drive")
        opt_path_to_browser = st.text_input("Browser Directory: ", value="")
        st.caption("Leave blank to use os default browser")
        opt_no_cache = st.checkbox("No Cache", value=False)
        st.caption("Uncheck (recommended): use cached data.\n\nCheck (slower): keep the data update.")
        opt_no_store = st.checkbox("No Store", value=False)
        st.caption("Uncheck: keep cached data (fills up the disk).\n\nCheck: discard cached data (leaves no footprint).")
        
        if not opt_data_dir:
            opt_data_dir = None
        else:
            opt_data_dir = Path(opt_data_dir)
        if not opt_path_to_browser:
            opt_path_to_browser = None
    
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
                "Read Schedule and Events (WhoScored)",
                "etc"
            ]
        )
        scraper = "ws"

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
        
    # ------ case 3: Scraper Initialization for Wyscout ------------------------- #
        
    elif scraper == "wy":
        @st.cache_resource
        def init_wyscout():
            return Wyscout()
        
        wy = init_wyscout()


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
            ws = init_whoscored()
            try:
                with st.expander("Read Seasons"):
                    seasons = ws.read_seasons()
                    st.dataframe(seasons)
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
                    
        if "Read Seasons Stages (WhoScored)" in opt_menus:
            ws = init_whoscored()
            try:
                with st.expander("Read Seasons Stages"):
                    seasons_stages = ws.read_season_stages()
                    st.dataframe(seasons_stages)
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
                    
        if "Read Missing Players (WhoScored)" in opt_menus:
            ws = init_whoscored(leagues="ENG-Premier League", seasons=2526)
            try:
                with st.expander("Read Missing Players (WhoScored)"):
                    missing_players = ws.read_missing_players(match_id=1903153, force_cache=True)
                    st.dataframe(missing_players)
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
                    
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
                    def save_atomic_spadl(league=league, season=season) -> pd.DataFrame:
                        aspadl = ws.read_events(output_fmt="atomic-spadl")
                        aspadl.to_parquet(GET_WHOSCORED['spadl'](league, season, "atomic-spadl"))
                        return aspadl

                    # api  = OptaLoader(
                    #     root=GET_PATH['base_dir'] / "cached_data" / "soccerdata",
                    #     parser="whoscored"
                    # )
                    
                    # st.text(api.competitions())
                    # st.text(api.games(2, 10743))
                    # st.text(api.teams(1903117))
                    # st.text(api.players(1903117))
                    # st.text(api.events(1903117))
            finally:
                if ws._driver: ws._driver.quit()

        # ----------------------------------------------------------------------- #
        
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

        
if __name__ == "__main__":
    main()
