import streamlit as st
import json
import glob
import os, time
import soccerdata as sd
import pandas as pd

from collections.abc import Iterable
from config.settings import GET_PATH
from soccerdata._config import TEAMNAME_REPLACEMENTS
from soccerdata.whoscored import WHOSCORED_DATADIR
from utils import ws_patch as wsp
from pathlib import Path

from pages.dashboard import load_regional_data, render_cascading_config, parse_season_string
from config.settings import GET_WHOSCORED, Settings
from config.langs import translator
from utils.models import calculate_exact_minutes, get_final_rating, analyze_rating_periods
from utils import helpers as hlp

# ------------------------------------------------------------------------------- #

TITLE = "Preprocessing"
st.set_page_config(
    page_title=TITLE,
    layout="centered"
)

set = Settings()
config, conf, is_loaded = hlp.initialize_state()
_ = translator.translate


# ------------------------------------------------------------------------------- #
# -- UI STRUCTURE AND LOG HANDLER ----------------------------------------------- #
# ------------------------------------------------------------------------------- #

menu = st.empty()
col1, col2 = st.columns([1, 2])
with col1:
    config_ui = st.container()
    cfg_save = st.empty()
with col2:
    status_message = st.empty()
    idselect = st.empty()
    content_ui = st.container()
    with content_ui:
        content = st.empty()
        json_wrapper = st.container()

with config_ui:
    config_elements = {
        "select_region": st.empty(), "caption_region": st.empty(),
        "select_tournament": st.empty(), "caption_tournament": st.empty(),
        "select_season": st.empty(), "caption_season": st.empty(),
        "select_directory": st.empty(), "caption_directory": st.empty()
    }

# -- ---------------------------------------------------------------------------- #

def main():
    # -- 1ST SECTION - DATA CONTROL --------------------------------------------- #

    opt_menus = []
    option_map = {
        1: "Events",
        2: "soon"
    }
    selection = menu.segmented_control(
        "Menu",
        options=option_map.keys(),
        format_func=lambda option: option_map[option],
        selection_mode="single",
        width="stretch"
    )

    if selection == 1:
        # --- case 04-0: Load Layout Requirements ----------------------------------- #
        df_regional = load_regional_data(GET_WHOSCORED['regional'])
        prev_settings = {
            'region': conf['cfg_region_prev'], 'tournament': conf['cfg_tournament_prev'],
            'season': conf['cfg_season_prev'], 'directory': conf['directory_value']
        }
        
        # --- case 04-1: Render Layout ---------------------------------------------- #
        cfg_region, cfg_tournament, cfg_season, directory = render_cascading_config(df_regional, prev_settings, config_elements)
        
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
                    'directory': directory,
                }
                st.session_state['team_badge'] = {'team_a': st.session_state.team_a, 'team_b': st.session_state.team_b}
                set.logMsg(f"{_("app.dashboard.cfg_save.custom")}!", level=5, container=status_message) # Configuration saved
                time.sleep(1)
                st.rerun()
            else:
                st.warning(_("app.dashboard.cfg_save.warning")) # Please fill region, tournament, and season

        file_path = WHOSCORED_DATADIR / "events" / f"{league_str}_{season_int}"
        
        ids = [file.stem for file in file_path.glob("*.json")]
        game_id = idselect.multiselect(
            "Select Game ID: ",
            options=ids
        )

        if not ids:
            content.text("No Option")

        elif game_id:
            with json_wrapper:
                for id in game_id:
                    with open(file_path / f"{id}.json", 'r') as file:
                        data = json.load(file)

                    st.caption(f"{id} Raw Events Data")
                    with st.container(height=150, border=False):
                        with st.expander(f"{id} raw events data", expanded=True):
                            st.json(data, expanded=False)
                    
                    st.caption(f"{id} Parsed Data")
                    with st.container(border=False):
                        with st.expander(f"{id} parsed data"):
                            all_players_data = []

                            match_id = id
                            match_date = data.get('startDate', match_id)
                            st.caption(f"{id} | {match_date}")
                            
                            for side in ['home', 'away']:
                                if side not in data: continue

                                team_id = data[side].get('teamId', "Unknown")
                                team_name = data[side].get('name', "Unknown")
                                st.subheader(f"{team_id}_{team_name} Section")
                                team_formations = data[side].get('formations', [])
                                with st.expander("Team Formation"):
                                    st.json(team_formations, expanded=False)
                                exact_minutes_dict = calculate_exact_minutes(team_formations)
                                with st.expander("Feature Engineering"):
                                    st.dataframe(exact_minutes_dict)

                                players = data[side].get('players', [])
                                with st.expander("Players List"):
                                    st.dataframe(players)
                                
                                    for p in players:
                                        player_id = p.get('playerId')

                                        with st.expander(f"{player_id} - {p.get('name', 'Unknown')}"):
                                            st.text(f"Player id: {id}")
                                            is_starter = 1 if p.get('isFirstEleven') else 0
                                            st.text(f"Is starter: {is_starter}")
                                            mins_played = exact_minutes_dict.get(player_id, 0)
                                            st.text(f"Mins played: {mins_played}")
                                            position = p.get('position', 'Sub')
                                            st.text(f"Position: {position}")

                                            ratings_data = p.get('stats', {}).get('ratings', {})
                                            final_rating = get_final_rating(ratings_data)
                                            st.text(f"Final Rating: {final_rating}")

                                            period_analysis = analyze_rating_periods(ratings_data)
                                            if period_analysis:
                                                st.write("**30-Minute Rating Analysis:**")
                                                st.json(period_analysis, expanded=False)
                                            
                                            all_players_data.append({
                                                'match_id': match_id,
                                                'date': match_date,
                                                'team_id': team_id,
                                                'team_name': team_name,
                                                'player_id': player_id,
                                                'player_name': p.get('name', f"Player_{player_id}"),
                                                'is_starter': is_starter,
                                                'minutes_played': mins_played,
                                                'rating': final_rating,
                                                'position': position,
                                                'rating_analysis': period_analysis
                                            })
                                            
                                with st.expander("Compiled data as pd.Dataframe"):
                                    st.dataframe(all_players_data)


if __name__ == "__main__":
    main()

