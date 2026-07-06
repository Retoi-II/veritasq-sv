import streamlit as st


# ------------------------------------------------------------------------------- #
# -- HELPER UTILITIES------------------------------------------------------------ #
# ------------------------------------------------------------------------------- #

def initialize_state() -> None:
    """Maintains atomic persistence layers for multi-page user interactions."""
    PLACEHOLDER = "Select a team..."
    if "team_a" not in st.session_state: 
        st.session_state.team_a = PLACEHOLDER
    if "team_b" not in st.session_state: 
        st.session_state.team_b = PLACEHOLDER
    if "cfg_scraper" not in st.session_state: 
        st.session_state.cfg_scraper = {}
    
    config = st.session_state.get('cfg_scraper', {})
    team_badge_state = st.session_state.get('team_badge', {})
    is_loaded = st.session_state.get('is_loaded', 0)

    conf = {
        'cfg_region_prev': config.get("region"),
        'cfg_tournament_prev': config.get("tournament"),
        'cfg_season_prev': config.get("season"),
        'directory_value': config.get("directory", ''),
        'team_a_prev': team_badge_state.get("team_a", ''),
        'team_b_prev': team_badge_state.get("team_b", ''),
    }

    return config, conf, is_loaded
