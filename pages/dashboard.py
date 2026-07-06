import streamlit as st
import lightgbm as lgb
import logging
import pandas as pd
import soccerdata as sd
import time
import traceback

from app import footer
from config.langs import translator
from config.settings import Settings, GET_PATH, GET_WHOSCORED
from pathlib import Path
from typing import Any
from utils import ws_patch as wsp
from utils import helpers, logger, models
from utils import display as dp
from mplsoccer import Pitch


# =============================================================================== #
# -- INITIALIZATION & SOCCERDATA PATCHING --------------------------------------- #
# =============================================================================== #

st.json(st.session_state,expanded=False)
TITLE = "Veritasq"
st.set_page_config(
    page_title=TITLE,
    layout="wide"
)

set = Settings()
hlp = helpers
_ = translator.translate

# Apply WhoScored monkey-patch
sd.WhoScored.read_seasons = wsp.read_seasons_patch
sd.WhoScored.read_season_stages = wsp.read_season_stages_patch
sd.WhoScored.read_schedule = wsp.read_schedule_patch


# =============================================================================== #
# -- DATA ACCESS LAYER ---------------------------------------------------------- #
# =============================================================================== #

# @st.cache_data
def load_regional_data(filepath: str | Path) -> pd.DataFrame:
    """Loads and caches the regional configurations."""
    return pd.read_csv(filepath)


# =============================================================================== #
# -- UI LAYOUT MODULES ---------------------------------------------------------- #
# =============================================================================== #

def render_cascading_config(
    df: pd.DataFrame, 
    prev_settings: dict[str, Any],
    containers: dict[str, Any]
) -> tuple[str, str, str, str]:
    """Builds interactive config workflows for Region -> Tournament -> Season mappings."""
    
    # --- case 01: [ui.layout.module] Region Selection -------------------------- #
    available_regions = {
        "France",
        "Germany",
        "England",
        "Italy",
        "Spain"
    }
    regions = df[df['region'].isin(available_regions)]['region'].drop_duplicates().tolist()
    cfg_region = containers["select_region"].selectbox(
        _("app.dashboard.cfg_region.label"), regions, index=get_default_index(regions, prev_settings.get('region'))
    )
    if cfg_region:
        set.logMsg(f"{_("app.dashboard.cfg_region.caption")} :green[{cfg_region}]", level=2, container=containers["caption_region"])
    else:
        footer()
        st.stop()

    # --- case 02: [ui.layout.module] Tournament Selection ---------------------- #
    tournaments = df[df['region'] == cfg_region]['tournament'].unique().tolist()
    cfg_tournament = containers["select_tournament"].selectbox(
        _("app.dashboard.cfg_tournament.label"), tournaments, index=get_default_index(tournaments, prev_settings.get('tournament')) # Config Region
    )
    if cfg_tournament:
        set.logMsg(f"{_("app.dashboard.cfg_tournament.caption")}: :green[{cfg_tournament}]", level=2, container=containers["caption_tournament"]) # Selected Tournament
    else:
        footer()
        st.stop()

    # --- case 03: [ui.layout.module] Season Selection -------------------------- #
    seasons_df = df[(df['region'] == cfg_region) & (df['tournament'] == cfg_tournament)]
    seasons = seasons_df['wh_season_name'].unique().tolist()
    cfg_season = containers["select_season"].selectbox(
        _("app.dashboard.cfg_season.label"), seasons, index=get_default_index(seasons, prev_settings.get('season')) # Config Season
    )
    if cfg_season:
        set.logMsg(f"{_("app.dashboard.cfg_season.caption")}: :green[{cfg_season}]", level=2, container=containers["caption_season"]) # Selected Season
    else:
        footer()
        st.stop()

    # --- case 04: [ui.layout.module] Working Directory Config ------------------ #
    directory = containers["select_directory"].text_input(_("app.dashboard.cfg_directory.placeholder"), value=prev_settings.get("directory", '')) # Browser Directory
    dir_label = directory if directory else _("app.dashboard.cfg_directory.custom") # system defined
    set.logMsg(f"{_("app.dashboard.cfg_directory.caption")} :green[{dir_label}]", level=2, container=containers["caption_directory"]) # Browser Location

    # --- case 05: [ui.layout.module] Print Layout ------------------------------ #
    return cfg_region, cfg_tournament, cfg_season, directory

def render_team_selectors(flat_df: pd.DataFrame, selectors: dict[str, Any]) -> None:
    """Updates team UI options ensuring cross-selection exclusivity rules."""
    PLACEHOLDER = _("app.dashboard.any_team.placeholder") # Select a team...:
    
    if flat_df.index.get_level_values != 1:
        flat_df = flat_df.sort_values(by="home_team", ascending=True)
        option_map = list(flat_df['home_team'].unique())
    else:
        option_map = list(flat_df.index.get_level_values(2).unique())

    team_1_options = [PLACEHOLDER] + [opt for opt in option_map if opt != st.session_state.team_b]
    team_2_options = [PLACEHOLDER] + [opt for opt in option_map if opt != st.session_state.team_a]

    if st.session_state.team_a not in team_1_options: st.session_state.team_a = PLACEHOLDER
    if st.session_state.team_b not in team_2_options: st.session_state.team_b = PLACEHOLDER
    
    selectors["team_1"].selectbox(
        _("app.dashboard.team_1.label"), options=team_1_options, key="team_a",
        on_change=dp.update_team_in_config, kwargs={'team_key': "team_a", 'placeholder': PLACEHOLDER}
    ) # Team 1:
    selectors["team_2"].selectbox(
        _("app.dashboard.team_1.label"), options=team_2_options, key="team_b",
        on_change=dp.update_team_in_config, kwargs={'team_key': "team_b", 'placeholder': PLACEHOLDER}
    ) # Team 2:


# =============================================================================== #
# -- HELPER UTILITIES------------------------------------------------------------ #
# =============================================================================== #

def get_default_index(options_list: list[Any], prev_value: Any) -> int | None:
    """Safely searches list records to avoid indexing exceptions inside inputs."""
    return options_list.index(prev_value) if prev_value in options_list else None

def parse_season_string(season_str: str) -> int | str:
    """Safely converts standard season strings (e.g. '23/24') into internal integers."""
    if len(season_str) == 9:
        return int(season_str[2:4] + season_str[7:9])
    return ""


# =============================================================================== #
# -- MAIN CONTROLLER ------------------------------------------------------------ #
# =============================================================================== #

def main() -> None:
    Path(GET_PATH['cache_ws']).mkdir(parents=True, exist_ok=True)
    Path(GET_PATH['cache_fb']).mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------- #
    # --- case 01: [INITIALIZATION] session_state ------------------------------- #
    # --------------------------------------------------------------------------- #

    config, conf, is_loaded = hlp.initialize_state()


    # --------------------------------------------------------------------------- #
    # --- case 02: [INITIALIZATION] layout definitions ------------------------- #
    # --------------------------------------------------------------------------- #

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
        if not is_loaded:
            team_badge_container = st.container()
        else:
            team_badge_container = st.container(border=True)
        with team_badge_container:
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

    with st.container(height=200, border=False):
        log_ui_placeholder = st.empty()
    
    if "session_logs" in st.session_state and st.session_state.session_logs:
        log_ui_placeholder.code("\n".join(st.session_state.session_logs), language="log")


    # --------------------------------------------------------------------------- #
    # --- case 03: [INITIALIZATION] log layer setup ----------------------------- #
    # --------------------------------------------------------------------------- #

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    ui_handler = logger.StreamlitLogHandler(log_ui_placeholder)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S")
    ui_handler.setFormatter(formatter)
    root_logger.addHandler(ui_handler)


    # --------------------------------------------------------------------------- #
    # --- case 04: [LEFT COLUMN] ------------------------------------------------ #
    # --------------------------------------------------------------------------- #

    # --- case 04-0: Load Layout Requirements ----------------------------------- #
    df_regional = load_regional_data(GET_WHOSCORED['regional'])
    prev_settings = {
        'region': conf['cfg_region_prev'], 'tournament': conf['cfg_tournament_prev'],
        'season': conf['cfg_season_prev'], 'directory': conf['directory_value']
    }
    
    # --- case 04-1: Render Layout ---------------------------------------------- #
    cfg_region, cfg_tournament, cfg_season, directory = render_cascading_config(df_regional, prev_settings, config_elements)
    if cfg_season and is_loaded < 1:
        is_loaded += 1
        st.session_state['is_loaded'] = is_loaded
        st.rerun()
    
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


    # --------------------------------------------------------------------------- #
    # --- case 05: [MID COLUMN] ------------------------------------------------- #
    # --------------------------------------------------------------------------- #

    # --- case 05-0: Load Layout Requirements ----------------------------------- #
    schedule_df = pd.read_csv(GET_WHOSCORED['schedule'])
    loaded_flat_df = schedule_df[(schedule_df['season'] == season_int) & (schedule_df['league'] == league_str)]

    # --- case 05-1: Load Team Selectors ---------------------------------------- #
    try:
        render_team_selectors(loaded_flat_df, team_selectors)
    except Exception as e:
        st.warning(f"{_("app.dashboard.case_05-1.warning")}. {e}") # Cannot load team selection

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
                'directory': directory,
            }
            st.session_state['team_badge'] = {'team_a': st.session_state.team_a, 'team_b': st.session_state.team_b}
            set.logMsg(f"{_("app.dashboard.cfg_save.custom")}!", level=5, container=status_message) # Configuration saved
            time.sleep(1)
            st.rerun()
        else:
            st.warning(_("app.dashboard.cfg_save.warning")) # Please fill region, tournament, and season


    # --- case 05-3: Render Club Logos ------------------------------------------ #
    if st.session_state.get('team_badge', {}).get('team_a', "Select a team...") != "Select a team..." and \
        st.session_state.get('team_badge', {}).get('team_b', "Select a team...") != "Select a team...":

        with logos_area:
            if "team_a" in st.session_state and "team_b" in st.session_state:
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
                st.info(_("app.dashboard.logos_area.info")) # Please fill the configuration section
            else:
                st.info(_("app.dashboard.logos_area.info_2")) # Choose teams


    # --- case 05-4: Render Processing Routine ---------------------------------- #
        with team_df_container:
            if st.session_state.get('team_badge', {}).get('team_a', "Select a team...") != "Select a team..." and \
            st.session_state.get('team_badge', {}).get('team_b', "Select a team...") != "Select a team...":
                try:

                    with st.expander("Modelling"):
                        df0 = models.load_match_data(league_str, season_int)
                        st.caption(f"Load Match Data -> {len(df0['match_id'].unique())} Matches")
                        st.dataframe(df0)

                        df1 = models.create_lag_features(df0)
                        st.caption(f"Load Lag Features -> {len(df1['match_id'].unique())} Matches. {len(df1['player_id'].unique())}/{len(df0['player_id'].unique())} Players Loaded")

                        st.dataframe(df1)
                        model, df2 = models.train_model(df1)

                        st.write(df2)
                        st.caption("Lineups")

                        df3 = models.construct_lineups(df2)
                        st.dataframe(df3)

                    with st.expander("Visualization"):
                        df3 = dp.load_all_data(df3)
                        
                        # SAFELY create the display label handling NaNs
                        df3['Display_Label'] = df3.apply(
                            lambda row: f"{row['home_team']} vs {row['away_team']} ({row['Leg']} - {row['Date:']})" 
                            if pd.notna(row['home_team']) 
                            else f"Match ID: {row['match_id']} (No Fixture Data)", 
                            axis=1
                        )

                        display_options = df3['Display_Label'].unique().tolist()
        
                        target_match = df3[
                            ((df3['home_team'] == st.session_state.team_a) & (df3['away_team'] == st.session_state.team_b))
                        ]

                        if not target_match.empty:
                            target_label = target_match.iloc[0]['Display_Label']
                            default_index = display_options.index(target_label)
                        else:
                            # Fallback to the very first match if id_a and id_b aren't found
                            default_index = 0
                        
                        selected_label = st.selectbox("Select Match", display_options, index=default_index)
                        
                        # SAFELY filter and check if data exists before calling .iloc[0]
                        filtered_data = df3[df3['Display_Label'] == selected_label]
                        
                        if not filtered_data.empty:
                            match_data = filtered_data.iloc[0]
                            match_id = match_data['match_id']
                            raw_players = match_data['predicted_11']

                            # Check if it's already a list, or if it needs to be split from a string
                            if isinstance(raw_players, list):
                                predicted_players = [str(player).strip() for player in raw_players]
                            elif isinstance(raw_players, str):
                                predicted_players = [player.strip() for player in raw_players.split(',')]
                            else:
                                predicted_players = []
                                st.error("Data format error: 'predicted_11' is neither a string nor a list.")

                            formation_433_coords = [
                                (10, 40),   # Goalkeeper
                                (30, 70),   # Left Back
                                (25, 50),   # Center Back 1
                                (25, 30),   # Center Back 2
                                (30, 10),   # Right Back
                                (50, 60),   # Left Mid
                                (45, 40),   # Center Mid
                                (50, 20),   # Right Mid
                                (75, 70),   # Left Winger
                                (85, 40),   # Striker
                                (75, 10)    # Right Winger
                            ]

                            if len(predicted_players) == 11:
                                st.subheader(f"Predicted Starting XI for Match {match_id}")

                                pitch = Pitch(pitch_type='statsbomb', pitch_color='#22312b', line_color='#c7d5cc')
                                fig, ax = pitch.draw(figsize=(10, 7))

                                for i, player_name in enumerate(predicted_players):
                                    x, y = formation_433_coords[i]
                                    
                                    # Draw player node (circle)
                                    pitch.scatter(x, y, ax=ax, s=600, color='#ea6969', edgecolors='white', zorder=2)
                                    
                                    # Add player name label
                                    pitch.annotate(player_name, xy=(x, y - 4), ax=ax, 
                                                ha='center', va='center', color='white', 
                                                fontsize=10, fontweight='bold', zorder=3)
                                
                                st.pyplot(fig)
                                
                                with st.expander("View Raw Player List"):
                                    st.write(predicted_players)
                            else:
                                st.error(f"Data error: Found {len(predicted_players)} players instead of 11.")
                                
                        else:
                            st.warning("Could not locate data for the selected match.")

                except Exception as e:
                    st.error(f"{_("app.dashboard.team_df_container.error")}: {e}") # Processing routine halted unexpected
                    traceback.print_exc()
            else:
                st.info(_("app.dashboard.team_df_container.info")) # The scraping initialization pipeline requires selection validations across both targeting groups.

if __name__ == "__main__":
    main()
