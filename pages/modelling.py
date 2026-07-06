import streamlit as st
import os
import glob
import json
import pandas as pd
import soccerdata as sd
import lightgbm as lgb

from collections.abc import Iterable
from config.settings import GET_PATH, GET_WHOSCORED
from soccerdata._config import TEAMNAME_REPLACEMENTS
from soccerdata.whoscored import WHOSCORED_DATADIR
from utils import ws_patch as wsp
from pathlib import Path


# ------------------------------------------------------------------------------- #
# -- UI STRUCTURE AND LOG HANDLER ----------------------------------------------- #
# ------------------------------------------------------------------------------- #

menu = st.empty()

if "session_logs" not in st.session_state:
    st.session_state["session_logs"] = []

if st.button("Add New Log"):
    st.session_state["session_logs"].append("New Activity Recorded!")

st.write(st.session_state["session_logs"])

# -- ---------------------------------------------------------------------------- #

def main():
    # -- 1ST SECTION - DATA CONTROL --------------------------------------------- #

    opt_menus = []
    option_map = {
        1: "Player Classification",
        2: "Modelling",
        3: "Team Formation",
        4: "etc"
    }
    selection = menu.segmented_control(
        "Menu",
        options=option_map.keys(),
        format_func=lambda option: option_map[option],
        selection_mode="single",
        width="stretch"
    )

    # ---- 1st Column - Configuration ------------------------------------------- #

    if selection == 1:
        league = "ENG-Premier League"
        season = 2526
        path_dir = GET_WHOSCORED['raw_events'] / f"{league}_{season}" / "1903429.json"

        with open(path_dir, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        st.json(raw_data, expanded=False)

        # lv1_keys = []
        # home_list = list(raw_data['home'].keys())
        # away_list = list(raw_data['away'].keys())
        # lv1_keys = [home_list, away_list]
        # print(lv1_keys)


    if selection == 2:
        def calculate_exact_minutes(formations_array):
            """
            Calculates exact minutes played for every player by tracking 
            their presence across different formation phases.
            """
            player_minutes = {}
            current_minute = 0  # Starts at kickoff (0)
            
            for phase in formations_array:
                # Get the minute this specific phase ended (e.g., when a sub happened)
                end_minute = phase.get('endMinuteExpanded', current_minute)
                
                # Calculate how long this specific phase lasted
                phase_duration = end_minute - current_minute
                
                player_ids = phase.get('playerIds', [])
                slots = phase.get('formationSlots', [])
                
                # Loop through all players in the roster for this phase
                for player_id, slot in zip(player_ids, slots):
                    if slot > 0:  
                        # Slot > 0 means they are on the pitch (1-11)
                        # Add the phase duration to their total time
                        if player_id not in player_minutes:
                            player_minutes[player_id] = 0
                        player_minutes[player_id] += phase_duration
                        
                # The end of this phase is the start of the next phase
                current_minute = end_minute 
                
            return player_minutes
        
        @st.cache_data(show_spinner=True, show_time=True)
        def load_master_table():
            league = "ENG-Premier League"
            season = 2526
            path_dir = GET_WHOSCORED['raw_events'] / f"{league}_{season}"

            all_players_data = []
            for path_file in path_dir.glob("*.json"):
                with open(path_file, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        continue

                    match_id = data.get('matchId', path_file.stem)
                    match_date = data.get('startDate', match_id)
                    
                    for side in ['home', 'away']:
                        if side not in data: continue

                        team_formations = data[side].get('formations', [])
                        exact_minutes_dict = calculate_exact_minutes(team_formations)

                        team_id = data[side].get('teamId', "Unknown")
                        team_name = data[side].get('name', "Unknown")
                        players = data[side].get('players', [])
                        
                        for p in players:
                            player_id = p.get('playerId')
                            is_starter = 1 if p.get('isFirstEleven') else 0
                            mins_played = exact_minutes_dict.get(player_id, 0)
                            position = p.get('position', 'Sub')
                            rating = p.get('stats', {}).get('ratings', {}).get('matchRating', 6.0)
                            
                            all_players_data.append({
                                'match_id': match_id,
                                'date': match_date,
                                'team_id': team_id,
                                'team_name': team_name,
                                'player_id': player_id,
                                'player_name': p.get('name', f"Player_{player_id}"),
                                'is_starter': is_starter,
                                'minutes_played': mins_played,
                                'rating': rating,
                                'position': position
                            })

            df = pd.DataFrame(all_players_data)
            df = df.sort_values(by=['date', 'match_id'])
            st.caption("Dataframe")
            st.dataframe(df)
            return df
            
        df = load_master_table()

        df = df.copy()
            
        df = df.sort_values(by=['player_id', 'date'])
        
        df['started_last_match'] = df.groupby('player_id')['is_starter'].shift(1).fillna(0)
        df['mins_last_match'] = df.groupby('player_id')['minutes_played'].shift(1).fillna(0)
        df['form_last_3'] = df.groupby('player_id')['rating'].transform(
            lambda x: x.shift(1).rolling(window=3, min_periods=1).mean()
        ).fillna(6.0) # Default to 6.0 if no history
        df['mins_last_3'] = df.groupby('player_id')['minutes_played'].transform(
            lambda x: x.shift(1).rolling(window=3, min_periods=1).sum()
        ).fillna(0)
        df['position_last_match'] = df.groupby('player_id')['position'].shift(1).fillna('Unknown')
        
        df['position_last_match'] = df['position_last_match'].astype('category')
        df['team_id'] = df['team_id'].astype('category')
        
        st.caption("Feature Engineering")
        st.dataframe(df)

        features = [
            'started_last_match', 
            'mins_last_match', 
            'form_last_3', 
            'mins_last_3',
            'position_last_match', 
            'team_id'
        ]
        target = 'is_starter'
        
        unique_matches = df['match_id'].unique()
        split_idx = int(len(unique_matches) * 0.75)
        
        train_matches = unique_matches[:split_idx]
        test_matches = unique_matches[split_idx:]
        
        train_df = df[df['match_id'].isin(train_matches)]
        test_df = df[df['match_id'].isin(test_matches)]
        
        X_train, y_train = train_df[features], train_df[target]
        X_test, y_test = test_df[features], test_df[target]
        
        st.text(f"Training on {len(train_df)} player-match records. Testing on {len(test_df)}.")
        
        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=5,
            random_state=42,
            class_weight='balanced'
        )
        
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(stopping_rounds=20)]
        )
        
        test_df = test_df.copy()
        test_df['start_probability'] = model.predict_proba(X_test)[:, 1]

        st.caption("Testing Dataframe")
        st.dataframe(test_df)

        predicted_lineups = []
    
        # Group by Match and Team
        grouped = test_df.groupby(['match_id', 'team_id'])
        
        total_correct = 0
        total_predictions = 0
        
        for (match_id, team_id), team_match_df in grouped:
            
            # Sort players by their probability of starting
            team_match_df = team_match_df.sort_values(by='start_probability', ascending=False)
            
            # Method 1: Simply take the top 11 probabilities
            # (For advanced logic, you would filter by position: 1 GK, 4 DEF, etc.)
            predicted_starters = team_match_df.head(11)
            actual_starters = team_match_df[team_match_df['is_starter'] == 1]
            
            # Calculate Overlap (How many of our predicted 11 were actually in the 11?)
            correct_guesses = len(set(predicted_starters['player_id']).intersection(set(actual_starters['player_id'])))
            
            total_correct += correct_guesses
            total_predictions += 11
            
            predicted_lineups.append({
                'match_id': match_id,
                'team_id': team_id,
                'predicted_11': predicted_starters['player_name'].tolist(),
                'actual_11': actual_starters['player_name'].tolist(),
                'correct_count': correct_guesses
            })

        accuracy = total_correct / total_predictions
        print(f"\n--- EVALUATION ---")
        st.info(f"Average Lineup Accuracy: {accuracy:.1%} ({total_correct}/{total_predictions} players guessed correctly)")
        
        st.caption("Predicted Lineups")
        st.dataframe(pd.DataFrame(predicted_lineups))

    if selection == 3:
        league = "ENG-Premier League"
        season = 2526
        path_dir = GET_WHOSCORED['raw_events'] / f"{league}_{season}"

        all_formations = []
        for path_file in path_dir.iterdir():

            if path_file.suffix != '.json':
                continue

            with open(path_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            home = raw_data['home']
            away = raw_data['away']

            formations = {
                'game_id': path_file.stem,
                'home.formationName': home['formations'][0]['formationName'],
                'home.formationId': home['formations'][0]['formationId'],
                'home.formationPlayer': home['formations'][0]['playerIds'],
                'home.formationCaptain': home['formations'][0]['captainPlayerId'],
                'home.formationPosition': [
                    (pos['horizontal'], pos['vertical']) 
                    for pos in home['formations'][0]['formationPositions']
                ],
                'away.formationName': away['formations'][0]['formationName'],
                'away.formationId': away['formations'][0]['formationId'],
                'away.formationPlayer': away['formations'][0]['playerIds'],
                'away.formationCaptain': away['formations'][0]['captainPlayerId'],
                'away.formationPosition': [
                    (pos['horizontal'], pos['vertical']) 
                    for pos in away['formations'][0]['formationPositions']
                ],
            }

            all_formations.append(formations)

        df_formations = pd.DataFrame(all_formations)
        st.dataframe(df_formations)

    if selection == 4:
        # ==============================================================================
        # PHASE 1: DATA PARSING & AGGREGATION
        # ==============================================================================
        def load_match_data(folder_path):
            """
            Parses all WhoScored JSON files in a directory to extract player appearances.
            """
            all_players_data = []
            
            file_pattern = os.path.join(folder_path, "*.json")
            for filepath in glob.glob(file_pattern):
                with open(filepath, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        continue
                    
                    match_id = data.get('matchId', filepath.split('/')[-1].replace('.json', ''))
                    match_date = data.get('startDate', match_id) 

                    for side in ['home', 'away']:
                        if side not in data: continue
                        
                        team_id = data[side].get('teamId', 'Unknown')
                        team_name = data[side].get('name', 'Unknown')
                        players = data[side].get('players', [])
                        
                        for p in players:
                            player_id = p.get('playerId')
                            is_starter = 1 if p.get('isFirstEleven') else 0
                            
                            mins_played = p.get('expandedMinutes', 0)
                            position = p.get('position', 'Sub')
                            rating = p.get('stats', {}).get('ratings', {}).get('matchRating', 6.0)
                            
                            all_players_data.append({
                                'match_id': match_id,
                                'date': match_date,
                                'team_id': team_id,
                                'team_name': team_name,
                                'player_id': player_id,
                                'player_name': p.get('name', f'Player_{player_id}'),
                                'is_starter': is_starter,       # TARGET
                                'minutes_played': mins_played,  # feature engineering
                                'rating': rating,               # feature engineering
                                'position': position            # Context
                            })

            df = pd.DataFrame(all_players_data)
            st.dataframe(df)
            df = df.sort_values(by=['date', 'match_id'])
            return df
        
        # ==============================================================================
        # PHASE 2: FEATURE ENGINEERING (Rolling/Lag Features)
        # ==============================================================================
        def create_lag_features(df):
            """
            Creates historical context. A player's chance of starting depends on their 
            status in the matches *prior* to the current one.
            """
            df = df.copy()
            
            # Sort by player, then by date to calculate rolling stats safely
            df = df.sort_values(by=['player_id', 'date'])
            
            # 1. Did they start the LAST match? (Shift by 1)
            df['started_last_match'] = df.groupby('player_id')['is_starter'].shift(1).fillna(0)
            
            # 2. Minutes played in the last match (Fatigue proxy)
            df['mins_last_match'] = df.groupby('player_id')['minutes_played'].shift(1).fillna(0)
            
            # 3. Rolling average rating over the last 3 matches (Form proxy)
            df['form_last_3'] = df.groupby('player_id')['rating'].transform(
                lambda x: x.shift(1).rolling(window=3, min_periods=1).mean()
            ).fillna(6.0) # Default to 6.0 if no history
            
            # 4. Total minutes played in the last 3 matches (Deep fatigue)
            df['mins_last_3'] = df.groupby('player_id')['minutes_played'].transform(
                lambda x: x.shift(1).rolling(window=3, min_periods=1).sum()
            ).fillna(0)

            df['position_last_match'] = df.groupby('player_id')['position'].shift(1).fillna('Unknown')
            
            # Convert categorical columns for LightGBM
            df['position_last_match'] = df['position_last_match'].astype('category')
            df['team_id'] = df['team_id'].astype('category')
            
            return df

        # ==============================================================================
        # PHASE 3 & 4: MODEL TRAINING (LightGBM)
        # ==============================================================================
        def train_model(df):
            """
            Splits the data chronologically and trains the LightGBM model.
            """

            features = [
                'started_last_match', 
                'mins_last_match', 
                'form_last_3', 
                'mins_last_3',
                'position_last_match', 
                'team_id'
            ]
            target = 'is_starter'
            
            unique_matches = df['match_id'].unique()
            split_idx = int(len(unique_matches) * 0.75)
            
            train_matches = unique_matches[:split_idx]
            test_matches = unique_matches[split_idx:]
            
            train_df = df[df['match_id'].isin(train_matches)]
            test_df = df[df['match_id'].isin(test_matches)]
            
            X_train, y_train = train_df[features], train_df[target]
            X_test, y_test = test_df[features], test_df[target]
            
            print(f"Training on {len(train_df)} player-match records. Testing on {len(test_df)}.")
            
            # Initialize and Train LightGBM
            model = lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=5,
                random_state=42,
                class_weight='balanced' # Helps because there are more bench players than starters
            )
            
            model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                callbacks=[lgb.early_stopping(stopping_rounds=20)]
            )
            
            # Add predictions back to the test dataframe
            test_df = test_df.copy()
            # predict_proba returns [prob_0, prob_1]. We want prob_1 (chance of starting)
            test_df['start_probability'] = model.predict_proba(X_test)[:, 1] 
            
            return model, test_df

        # ==============================================================================
        # PHASE 5: LINEUP CONSTRUCTION & EVALUATION
        # ==============================================================================
        def construct_lineups(test_df):
            """
            Takes the probabilities and forces them into a valid 11-man starting lineup.
            """
            predicted_lineups = []
            
            # Group by Match and Team
            grouped = test_df.groupby(['match_id', 'team_id'])
            
            total_correct = 0
            total_predictions = 0
            
            for (match_id, team_id), team_match_df in grouped:
                
                # Sort players by their probability of starting
                team_match_df = team_match_df.sort_values(by='start_probability', ascending=False)
                
                # Method 1: Simply take the top 11 probabilities
                # (For advanced logic, you would filter by position: 1 GK, 4 DEF, etc.)
                predicted_starters = team_match_df.head(11)
                actual_starters = team_match_df[team_match_df['is_starter'] == 1]
                
                # Calculate Overlap (How many of our predicted 11 were actually in the 11?)
                correct_guesses = len(set(predicted_starters['player_id']).intersection(set(actual_starters['player_id'])))
                
                total_correct += correct_guesses
                total_predictions += 11
                
                predicted_lineups.append({
                    'match_id': match_id,
                    'team_id': team_id,
                    'predicted_11': predicted_starters['player_name'].tolist(),
                    'actual_11': actual_starters['player_name'].tolist(),
                    'correct_count': correct_guesses
                })

            accuracy = total_correct / total_predictions
            print(f"\n--- EVALUATION ---")
            print(f"Average Lineup Accuracy: {accuracy:.1%} ({total_correct}/{total_predictions} players guessed correctly)")
            
            return pd.DataFrame(predicted_lineups)

        # ==============================================================================
        # RUN THE PIPELINE
        # ==============================================================================
        if __name__ == "__main__":
            # 1. Load Data
            print("Loading data...")
            raw_df = load_match_data(folder_path=GET_PATH['base_dir'] / "cached_data" / "WhoScored" / "events" / "json" / "ENG-Premier League_2526")
            st.stop()
            if len(raw_df) == 0:
                print("No data loaded. Check folder path and JSON structure.")
            else:
                # 2. Feature Engineering
                print("Creating features...")
                feat_df = create_lag_features(raw_df)
                
                # 3 & 4. Train Model
                print("Training LightGBM Model...")
                model, predictions_df = train_model(feat_df)
                
                # 5. Construct Lineups and Evaluate
                print("Constructing 11-man lineups...")
                results = construct_lineups(predictions_df)
                
                # Look at the first prediction
                print("\nSample Match Prediction:")
                print(results.iloc[0])

if __name__ == "__main__":
    main()

