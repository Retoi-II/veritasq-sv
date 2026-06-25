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
