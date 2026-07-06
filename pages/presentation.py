import streamlit as st
import time
import json
import pandas as pd
import polars as pl

from config.settings import GET_WHOSCORED, Settings
from config.langs import translator
from pages.dashboard import load_regional_data, render_cascading_config, parse_season_string
from soccerdata.whoscored import WHOSCORED_DATADIR
from utils import helpers as hlp, models as mdl

# ------------------------------------------------------------------------------- #

TITLE = "Presentation"
st.set_page_config(
    page_title=TITLE,
    layout="centered"
)
set = Settings()
config, conf, is_loaded = hlp.initialize_state()
_ = translator.translate


# ------------------------------------------------------------------------------- #

col1, col2 = st.columns([1, 2])
config_ui = st.container()
cfg_save = st.empty()
status_message = st.empty()
idselect = st.empty()
content_ui = st.container()
with content_ui:
    content = st.empty()
    json_wrapper = st.empty()

with config_ui:
    config_elements = {
        "select_region": st.empty(), "caption_region": st.empty(),
        "select_tournament": st.empty(), "caption_tournament": st.empty(),
        "select_season": st.empty(), "caption_season": st.empty(),
        "select_directory": st.empty(), "caption_directory": st.empty()
    }


# ------------------------------------------------------------------------------- #

def main():
    # --- case 04-0: Load Layout Requirements --------------------------------------- #
    df_regional = load_regional_data(GET_WHOSCORED['regional'])
    prev_settings = {
        'region': conf['cfg_region_prev'], 'tournament': conf['cfg_tournament_prev'],
        'season': conf['cfg_season_prev'], 'directory': conf['directory_value']
    }
    
    # --- case 04-1: Render Layout -------------------------------------------------- #
    cfg_region, cfg_tournament, cfg_season, directory = render_cascading_config(df_regional, prev_settings, config_elements)
    
    # --- case 04-2: session_state Values Assignment -------------------------------- #
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

    # --- case 05-2: Load Save Configuration Button --------------------------------- #
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
    game_id = idselect.selectbox(
        "Select Game ID: ",
        options=ids
    )

    if not ids:
        content.text("No Option")

    elif game_id:
        id = game_id

        st.subheader("Membuka Raw Nested JSON")
        with open(file_path / f"{id}.json", 'r') as file:
            raw_data = json.load(file)

        with st.expander(f"{id} raw events data (nested JSON)", expanded=True):
            st.json(raw_data, expanded=False)
        
        st.subheader("Data Understanding")
        with st.expander(f"Top level keys (transposed)"):
            top_level_keys = pl.DataFrame(list(raw_data.keys()))
            st.caption("DataFrame: top_level_keys -> raw_data.keys()")
            st.dataframe(top_level_keys.transpose())
        
        with st.expander("Level 1 keys"):
            home_list = list(raw_data['home'].keys())
            away_list = list(raw_data['away'].keys())
            lv1_keys = pl.DataFrame([home_list, away_list])
            st.caption("DataFrame: lv1_keys | home -> raw_data['home'] & away -> raw_data['away']")
            st.dataframe(lv1_keys.rename({"column_0": "home", "column_1": "away"}))
        
        with st.expander("Team Formations (Home)"):
            st.caption("Level 1 -> dict: raw_data['home']")
            st.json(raw_data['home'], expanded=False)
            st.caption("Level 2 -> dict: raw_data['home]['formations']")
            st.json(raw_data['home']['formations'], expanded=False)

        st.subheader("Data Preparation")
        with st.expander("Position (Appending & Data Cleaning)"):
            st.caption("Level 3_nested_1 -> raw_data['home]['formations'][i]['formationsPositions']")
            st.caption("data cleaning -> mendefinisikan tuple float(horizontal), float(vertical) dari kolom formationPositions")
            st.caption("appending -> menambahkan formationPositions ke dalam variabel -> DataFrame")
            home_formations = raw_data['home']['formations']
            rows = []
            for i, formation in enumerate(home_formations):
                rows.append({
                    "formation_index": i,
                    "formationPositions": [
                        (float(item["horizontal"]), float(item["vertical"]))
                        for item in formation.get("formationPositions", [])
                    ] # tuple float(x), float(y)
                })
            formation_positions = pl.DataFrame(rows)
            st.dataframe(formation_positions)
            st.caption("Level 3_nested_2 -> raw_data['home]['formations'][i]['playerIds']")
            st.caption("appending -> menambahkan playerIds ke dalam variabel -> DataFrame")
            rows = []
            for i, formation in enumerate(home_formations):
                rows.append({
                    "formation_index": i,
                    "playerIds": formation.get("playerIds", [])
                })
            player_ids = pl.DataFrame(rows)
            st.dataframe(player_ids)

        with st.expander("Time Series Master Table"):
            st.caption("Time-series master table")
            all_players_data = []
            match_id = raw_data.get('matchId', game_id)
            match_date = raw_data.get('startDate', match_id)
            # st.caption(f"match_id = {match_id}. Mengambil dari nama file .json")
            # st.caption(f"match_date = {match_date}. Mengambil dari nested JSON, menangani missing_values dengan menetapkan nilai match_id.")
            # st.caption("mendefinisikan team_id, team_name untuk masing-masing tim")
            # st.caption("mendefinisikan player_id, is_starter, dan position untuk setiap pemain")
            # st.caption("menghitung menit bermain dan analisis rating")

            for side in ['home', 'away']:
                if side not in raw_data: continue

                team_formations = raw_data[side].get('formations', []) # menangani missing value
                exact_minutes_dict = mdl.calculate_exact_minutes(team_formations) # fungsi kalkulasi rincian menit

                team_id = raw_data[side].get('teamId', "Unknown") # menangani missing value
                team_name = raw_data[side].get('name', "Unknown") # menangani missing value
                players = raw_data[side].get('players', []) # menangani missing value

                for p in players:
                    player_id = p.get('playerId')
                    is_starter = 1 if p.get('isFirstEleven') else 0
                    mins_played = exact_minutes_dict.get(player_id, 0)
                    position = p.get('position', 'Sub')

                    ratings_data = p.get('stats', {}).get('ratings', {})
                    final_rating = mdl.get_final_rating(ratings_data)
                    period_analysis = mdl.analyze_rating_periods(ratings_data)
                    
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

            players_df = pl.DataFrame(all_players_data)
            st.dataframe(players_df)
            

            

            



# ------------------------------------------------------------------------------- #


if __name__ == "__main__":
    main()
