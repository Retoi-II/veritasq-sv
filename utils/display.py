import pandas as pd
import streamlit as st

def display_config(config_data: dict) -> dict:
    display_config = {}
    
    for key, value in config_data.items():
        str_key = str(key)

        if "index" in str_key.lower():
            continue

        if len(str_key) > 10:
            display_key = f"{str_key[:7]}..{str_key[-2:]}"
        else:
            display_key = str_key

        if isinstance(value, (list, tuple)) and len(value) > 5:
            display_config[display_key] = f"[{len(value)} items]"
        else:
            display_config[display_key] = str(value)
            
    return display_config


def unflatten_with_config(flat_df, config_mapping):
    """Reconstructs MultiIndex layers and automatically restores row indices."""
    original_tuples = []
    
    for col in flat_df.columns:
        if col in config_mapping:
            lvl0, lvl1 = config_mapping[col]
            if lvl0.startswith('Unnamed:') or lvl0 == 'None' or lvl0 == '':
                lvl0 = ''
            original_tuples.append((lvl0, lvl1))
        else:
            original_tuples.append(('Other', col))
            
    nested_df = flat_df.copy()
    nested_df.columns = pd.MultiIndex.from_tuples(original_tuples)
    
    # AUTO-DETECT INDEX: If columns with an empty top layer ('') match 
    # columns that should be row indices, set them back!
    id_cols = [col for col in nested_df.columns if col[0] == '']
    if id_cols:
        nested_df = nested_df.set_index(id_cols)
        
    return nested_df


def update_team_in_config(team_key, placeholder=""):
    if "cfg_scraper" not in st.session_state:
        st.session_state.cfg_scraper = {}
    
    val = st.session_state.get(team_key)
    st.session_state.cfg_scraper[team_key] = None if val == placeholder else val
