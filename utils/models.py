import json
import lightgbm as lgb
import pandas as pd
import streamlit as st
from pathlib import Path
from config.settings import GET_WHOSCORED


# =============================================================================== #
# -- case 01: Data Parsing & Aggregation ---------------------------------------- #
# =============================================================================== #

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

def get_final_rating(ratings_dict):
    """Extracts the rating from the final recorded minute efficiently."""
    if not isinstance(ratings_dict, dict) or not ratings_dict:
        return 6.0 
    
    # Using a generator expression (...) instead of a list [...] saves memory.
    # It evaluates values on the fly without storing an intermediate array.
    valid_minutes = (int(k) for k in ratings_dict.keys() if k.isdigit())
    
    try:
        last_minute = max(valid_minutes)
        return ratings_dict[str(last_minute)]
    except ValueError:
        # Triggered if valid_minutes yields no items (e.g., empty dict or no digits)
        return 6.0

def analyze_rating_periods(ratings_dict, period_length=30):
    """Breaks down live match ratings into 30-minute chunks in O(N) time."""
    if not isinstance(ratings_dict, dict) or not ratings_dict:
        return {}

    # Pre-allocate period names. 
    # Index 0 -> 0-29, 1 -> 30-59, 2 -> 60-89, 3 -> 90+
    period_names = ["0'-29'", "30'-59'", "60'-89'", "90'+"]
    periods = {}
    
    # 1. Single O(N) pass to group ratings into buckets (no sorting needed)
    for m_str, rating in ratings_dict.items():
        if not m_str.isdigit():
            continue
            
        minute = int(m_str)
        period_idx = minute // period_length
        
        # Cap the index at 3 so anything 90 and above goes to the "90'+" bucket
        period_idx = min(period_idx, 3) 
        
        p_name = period_names[period_idx]
        if p_name not in periods:
            periods[p_name] = []
        periods[p_name].append(rating)

    if not periods:
        return {}

    results = {}
    previous_avg = None
    
    # 2. Iterate via period_names to naturally guarantee chronological order
    for p_name in period_names:
        if p_name not in periods:
            continue # Skip periods where the player didn't play/have ratings
            
        r_list = periods[p_name]
        count = len(r_list)
        
        avg_rating = sum(r_list) / count
        max_rating = max(r_list)
        min_rating = min(r_list)
        
        diff_from_prev = avg_rating - previous_avg if previous_avg is not None else 0.0
        
        results[p_name] = {
            "average": round(avg_rating, 2),
            "highest": max_rating,
            "lowest": min_rating,
            "internal_volatility": round(max_rating - min_rating, 2),
            "change_from_prev_period": round(diff_from_prev, 2)
        }
        previous_avg = avg_rating
        
    return results

@st.cache_data(show_spinner=True, show_time=True)
def load_match_data(league, seasons, path_dir: Path = GET_WHOSCORED['raw_events']):
    """
    Parses all corresponding datasets from a group of folder.
    Available dataset options:

    Attributes:
        path_dir (Path) : Directory Location where the datasets stored

    Args:
        JSON (WhoScored) : "Nested JSON"
        tbd (coming soon) :

    Returns:
        pd.DataFrame :


    Raise:

    Examples:

    """
    if isinstance(seasons, list):
        for season in seasons:
            path_dir = path_dir / f"{league}_{season}"
            path_dir = path_dir.append()
    else:
        path_dir = path_dir / f"{league}_{seasons}"

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
    return df



# =============================================================================== #
# -- case 02: Feature Engineering (Rolling/Lag Features)------------------------- #
# =============================================================================== #

def create_lag_features(df):
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

    return df


# =============================================================================== #
# -- case 03: Model Training (LightGBM) ----------------------------------------- #
# =============================================================================== #

def train_model(df):
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
    
    return model, test_df


# =============================================================================== #
# -- case 04: Lineup Construction + Evaluation ---------------------------------- #
# =============================================================================== #

def construct_lineups(test_df):
    predicted_lineups = []
    # Group by Match and Team
    grouped = test_df.groupby(['match_id', 'team_id'])
    
    total_correct = 0
    total_predictions = 0
    
    for (match_id, team_id), team_match_df in grouped:
        
        # Sort players by their probability of starting
        team_match_df = team_match_df.sort_values(by='start_probability', ascending=False)
        
        predicted_starters = team_match_df.head(11)
        actual_starters = team_match_df[team_match_df['is_starter'] == 1]
        
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

    return pd.DataFrame(predicted_lineups)
