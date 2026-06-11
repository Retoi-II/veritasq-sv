import streamlit as st
import pandas as pd

dataframe = pd.DataFrame()
st.write(dataframe)

state = {
    # 'team_badge': "Teams"
}

PLACE = "Select a team..." if 'team_badge' not in state else "Exists"

st.text(PLACE)

configuration = {
    # 'team_a': "Arsenal",
    # 'team_b': "Crystal Palace"
}
st.text(configuration.get('team_a', PLACE))

st.text("HEY ANTEK ASENG!!")

st.json(st.session_state)
