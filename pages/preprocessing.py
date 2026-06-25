import streamlit as st
import json
import glob
import os
import soccerdata as sd

from collections.abc import Iterable
from config.settings import GET_PATH
from soccerdata._config import TEAMNAME_REPLACEMENTS
from soccerdata.whoscored import WHOSCORED_DATADIR
from utils import ws_patch as wsp
from pathlib import Path


# ------------------------------------------------------------------------------- #
# -- UI STRUCTURE AND LOG HANDLER ----------------------------------------------- #
# ------------------------------------------------------------------------------- #

menu = st.empty()

# -- ---------------------------------------------------------------------------- #

def main():
    # -- 1ST SECTION - DATA CONTROL --------------------------------------------- #

    opt_menus = []
    option_map = {
        1: "Events",
        2: "etc"
    }
    selection = menu.segmented_control(
        "Menu",
        options=option_map.keys(),
        format_func=lambda option: option_map[option],
        selection_mode="single",
        width="stretch"
    )

    if selection == 1:
        file_path = WHOSCORED_DATADIR / "events" / "ENG-Premier League_2526" / "1903117.json"
        
        with open(file_path, 'r') as file:
            json_data = json.load(file)

        st.json(json_data, expanded=False)
if __name__ == "__main__":
    main()

