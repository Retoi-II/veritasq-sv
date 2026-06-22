import json
import polars as pl
import pandas as pd
import soccerdata as sd
import streamlit as st

from utils import ws_patch as wsp
from config.settings import GET_PATH, GET_WHOSCORED, GET_FBREF
from pathlib import Path



# if "session_logs" in st.session_state and st.session_state.session_logs:
#     st.code("\n".join(st.session_state.session_logs), language="log")

# ws = sd.WhoScored("ENG-Premier League", 2526, no_cache=False, no_store=False)
# sd.WhoScored.read_seasons = wsp.read_seasons_patch
# sd.WhoScored.read_season_stages = wsp.read_season_stages_patch
# sd.WhoScored.read_schedule = wsp.read_schedule_patch

# csv = GET_WHOSCORED['schedule']
# df = pl.read_csv(csv) \
#     .filter(
#         (
#             (pl.col('home_team') == "Manchester United") |
#             (pl.col('away_team') == "Manchester United")
#         ) & (
#             (pl.col('league') == "ENG-Premier League") &
#             (pl.col('season') == 2526)
#         )
#     ).select(['game', 'game_id'])

# game_id = df.select(pl.col('game_id')).tail(5) # Memuat lima pertandingan terakhir
# game_id_list = game_id['game_id'].to_list() # Konversi Polars DataFrame -> Python List

# events_df = pd.DataFrame()

# for i, id in enumerate(game_id_list):
#     file_name = GET_WHOSCORED['events'](season=2526, league="ENG-Premier League", game_id=id, team="Manchester United")
#     print(f"[{i + 1}/{len(game_id_list)}]  Processing {id}")

#     if not file_name.exists():
#         fetch = ws.read_events(id)
#         fetch = pd.DataFrame(fetch)
#         fetch.to_csv(file_name, mode='w')
#         events_df = pd.concat([events_df, fetch], ignore_index=True)
#     else:
#         df = pd.read_csv(file_name)
#         events_df = pd.concat([events_df, df], ignore_index=True)

# events_df = pl.DataFrame(events_df)
# search_game_id = game_id_list[:-1]
# target_game_id = game_id_list[-1:]
# with st.container():
#     st.caption(game_id_list)
#     st.caption(f"{search_game_id} -> Search for Game ID")
#     st.caption(f"{target_game_id} -> Target Game ID")

# st.dataframe(
#     events_df.filter(
#         pl.col('game_id') == int(str(target_game_id[0]))
#     ), hide_index=False
# )

path = {
    'events': Path.cwd() / "cached_data" / "Wyscout" / "events",
    'matches': Path.cwd() / "cached_data" / "Wyscout" / "matches"
} 

save_path = Path.cwd() / "cached_data" / "Wyscout"

data_files = {
    'events': Path.cwd() / "cached_data" / "events.zip",  # ZIP file containing one JSON file for each competition
    'matches': Path.cwd() / "cached_data" / "matches.zip",  # ZIP file containing one JSON file for each competition
    'players': Path.cwd() / "socceraction" / "players.json",  # JSON file
    'teams': Path.cwd() / "socceraction" / "teams.json"  # JSON file
}
print("==================================")
print("==================================")
print("==================================")
import numpy as np
print("==================================")
print("==================================")
df_teams = pd.read_json(data_files['teams'], encoding='unicode_escape')
# df_teams.to_hdf(save_path / "wyscout.h5", key='teams', mode='w')

df_teams['area'] = df_teams['area'].astype(str)
# st.dataframe(df_teams)  


df_players = pd.read_json(data_files['players'], encoding='unicode_escape')
# df_players.to_hdf(save_path / "wyscout.h5", key='players', mode='a')

df_players = df_players.replace('null', np.nan)
mixed_cols = ['passportArea', 'birthArea']
for col in mixed_cols:
    if col in df_players.columns:
        # If the column contains nested dictionaries, extract the 'name' or stringify it
        df_players[col] = df_players[col].apply(
            lambda x: x.get('name') if isinstance(x, dict) else str(x) if pd.notnull(x) else np.nan
        )
        # Ensure the final output is safely treated as a uniform string column
        df_players[col] = df_players[col].astype(str)

# 4. Clean up the explicit ID columns to be nullable integers
id_cols = ['currentTeamId']
for col in id_cols:
    if col in df_players.columns:
        df_players[col] = df_players[col].astype('Int64')
# st.dataframe(df_players)


competitions = [
    'England',
    # 'France',
    # 'Germany',
    # 'Italy',
    # 'Spain',
    # 'European Championship',
    # 'World Cup'
]


dfs_matches = []
for competition in competitions:
    competition_name = competition.replace(' ', '_')
    file_matches = path['matches'] / f"matches_{competition_name}.json"
    df_matches = pd.read_json(file_matches, encoding='unicode_escape')
    dfs_matches.append(df_matches)
df_matches = pd.concat(dfs_matches)
# df_matches.to_hdf(save_path / "wyscout.h5", key='matches', mode='a')

df = pd.DataFrame(df_matches)
keys = df[df['label'].str.contains("arsenal", case=False, na=False)]['wyId']
keys_append = []
for id in keys:
    key = f"actions/game_{id}"
    keys_append.append(key)

all_actions = []

with pd.HDFStore(save_path / "spadl_1609.h5",  mode='r') as store:
    for i, key in enumerate(keys_append):
        print(f"Processing {i}/{len(keys_append)}")
        if f"/{key}" in store.keys() or key in store.keys():
            df_game = store[key]
            all_actions.append(df_game)

if all_actions:
    df_spadl = pd.concat(all_actions, ignore_index=True)
    print(f"Successfully loaded {len(all_actions)} games into df_spadl!")
else:
    df_spadl = pd.DataFrame()
    print("Warning: No matching game keys found in the HDF5 file.")

st.dataframe(df_spadl, hide_index=False)

# st.caption("Matches DataFrame")
# st.dataframe(df_matches)
st.stop()
from socceraction.spadl.wyscout import convert_to_actions

for competition in competitions:
    competition_name = competition.replace(' ', '_')
    file_events = path['events'] / f"events_{competition_name}.json"
    df_events = pd.read_json(file_events)
    rename_dict = {
        'id': 'event_id',
        'eventId': 'type_id',          # Wyscout v2 'eventId' maps to spadl 'type_id'
        'eventName': 'type_name',
        'subEventId': 'subtype_id',    # This fixes the current error!
        'subEventName': 'subtype_name',
        'playerId': 'player_id',
        'matchId': 'game_id',
        'teamId': 'team_id',
        'matchPeriod': 'period_id',
        'eventSec': 'milliseconds'     # Note: spadl convert_to_actions expects milliseconds (seconds * 1000)
    }

    df_events = df_events.rename(columns=rename_dict)

    if df_events['milliseconds'].max() < 10000:
        df_events['milliseconds'] = df_events['milliseconds'] * 1000

    # st.caption("SPADL")
    # st.dataframe(df_actions)
    i = 0
    df_events_matches = df_events.groupby('game_id', as_index=False)
    # for match_id, df_events_match in df_events_matches:
        # i += 1
    #     df_events_match.to_hdf(save_path / "wyscout.h5", key=f'events/match_{match_id}', mode='a')
        # print(f"Converting to spadl {i}/{len(df_events_matches)}")
        # df_events = pd.read_hdf(save_path / "wyscout_v3.h5", key=f"events/match_{match_id}")
        # df_actions = convert_to_actions(df_events, home_team_id=1609)
        # if "original_event_id" in df_actions.columns:
        #     df_actions["original_event_id"] = df_actions["original_event_id"].astype(str)
        # df_actions.to_hdf(save_path / "spadl_1609.h5", key=f"actions/game_{match_id}", mode='a', format="table")

if (save_path / "spadl_1609.h5").exists():
    print(save_path / "spadl_1609.h5")

# with pd.HDFStore(save_path / "wyscout_v3.h5", mode="r") as store:
#     print("Available keys in HDF5:", store.keys())
    



