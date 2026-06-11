import importlib.metadata
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

# ------------------------------------------------------------------------------- #
# -- GLOBAL DICTIONARY ---------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

class GetUrl(TypedDict):
    ws: str
    fb: str
    fs: str
    ws: str

GET_URL: GetUrl = {
    'ws': "https://www.whoscored.com",
    'fb': "https://fbref.com/en",
    'fs': "https://www.flashscore.com",
    'sd': "https://api.soccerdataapi.com"
}
"""GetUrl: Define the URL for API.

Attributes:
    ['fb'] (FBref) : "https://fbref.com/en"
    ['fs'] (FlashScore) : "https://www.flashscore.com"
    ['sd'] (SoccerdataAPI) : "https://api.soccerdataapi.com"
    ['ws'] (WhoScored) : "https://www.whoscored.com"

## _Example:_
```
GET_URL['ws'] # "https://www.whoscored.com"
```
"""


# ------------------------------------------------------------------------------- #

class GetPath(TypedDict):
    base_dir: Path
    locales: Path
    cache_fb: Path
    cache_ws: Path
    events_path: Callable[[str, str | int, str], Path]

_path = Path(__file__).resolve().parent.parent

GET_PATH: GetPath = {
    'base_dir': _path,
    'locales': _path / "locales",
    'cache_fb': _path / "cached_data" / "FBref",
    'cache_ws': _path / "cached_data" / "WhoScored",
    'events_path': lambda league, season, team: (
        _path / "cached_data" / "WhoScored" / f"{league}_{season}" / team
    )
}
"""GetPath: Define the core directory.

Attributes:
    ['base_dir'] (**standard key**, base directory) :
    ['locales'] (**standard key**, language folder) :
    ['cache_fb'] (**standard key**, cached dataset from fbref) :
    ['cache_ws'] (**standard key**, cached dataset from whoscored) :
    ['events_path'] (**callable key**, events dataset path) : `league` `season` `team` (required parameters)

## _Example:_
```
# standard key lookup
GET_PATH['locales'] # "/home/lyra/veritasq-sv/locales"

# callable key invocation
GET_PATH['events_path'](
    league="ENG-Premier League", 
    season=2526, 
    team="Manchester Utd"
) # "/home/lyra/veritasq-sv/cached_data/WhoScored/ENG-Premier League_2526/Manchester Utd"
```
"""


# ------------------------------------------------------------------------------- #

class WhoScored(TypedDict):
    regional: Path
    tournament: Path
    game_info: Path
    events: Callable[[str, str | int, str, str, str | int], Path]

GET_WHOSCORED: WhoScored = {
    'regional': GET_PATH['cache_ws'] / "_regional_data.csv",
    'tournament': GET_PATH['cache_ws'] / "_tournaments_data.csv",
    'game_info': GET_PATH['cache_ws'] / "_game_info.jsonl",
    'events': lambda league, season, team, game_id: (
        GET_PATH['events_path'](league, season, team) / f"_events_{game_id}.csv"
    )
}
"""WhoScored: Define the dataset location for WhoScored.

Attributes:
    ['regional'] (**standard key**, offline dataset for regions) :
    ['tournament'] (**standard key**, offline dataset for tournaments) :
    ['game_info'] (**standard key**, offline dataset for game_info) :
    ['events'] (**callable key**, events dataset location) : `league` `season` `team` `game_id` (required parameters)

## _Example:_
```
# standard key lookup
GET_PATH['regional'] # "/home/lyra/veritasq-sv/cached_data/WhoScored/_regional_data.csv"

# callable key invocation
GET_PATH['events'](
    league="ENG-Premier League", 
    season=2526, 
    team="Manchester Utd",
    game_id=1729488
) # "/home/lyra/veritasq-sv/cached_data/WhoScored/ENG-Premier League_2526/Manchester Utd/_events_1729488.csv"
```
"""


# ------------------------------------------------------------------------------- #

class FBref(TypedDict):
    team_season: Callable[[str, str | int], Path]
    team_season_map: Callable[[str, str | int], Path]
    player_season: Callable[[str], Path]
    player_season_map: Callable[[str], Path]

GET_FBREF: FBref = {
    'team_season': lambda league, season: (
        GET_PATH['cache_fb'] /
        f"_read_team_season_stats_{league}_{season}.csv"
    ),
    'team_season_map': lambda league, season: (
        GET_PATH['cache_fb'] /
        f"_read_team_season_stats_{league}_{season}.json"
    ),
    'player_season': lambda stat_type: (
        GET_PATH['cache_fb'] /
        f"_read_player_season_stats_2021_2526_{stat_type}.csv"
    ),
    'player_season_map': lambda stat_type: (
        GET_PATH['cache_fb'] /
        f"_read_player_season_stats_2021_2526_{stat_type}.json"
    ),
}
"""FBref: Define the dataset location for WhoScored.

Attributes:
    ['team_season'] (**callable key**, offline dataset for team_season) : `league` `season` (required parameters)
    ['team_season_map'] (**callable key**, dataset configuration for team_season) : `league` `season` (required parameters)
    ['player_season'] (**callable key**, offline dataset for player_season) : `stat_type` (required parameter)
    ['player_season_map'] (**callable key**, dataset configuration for player_season) : `stat_type` (required parameter)

## _Example:_
    ```
    # callable key invocation
    GET_PATH['team_season'](
        league="ENG-Premier League", 
        season=2526
    ) # "/home/lyra/veritasq-sv/cached_data/FBref/_read_team_season_stats_ENG-Premier League_2526.csv"
    ```
"""


# ------------------------------------------------------------------------------- #

class Settings:
    def __init__(
        self, 
        default_container: DeltaGenerator | None = None, 
        default_color: str = "blue"
    ):
        """
        Initialize the Settings class.
        You can set app-wide defaults here.
        """
        self.default_container = default_container or st
        self.default_color = default_color
        
    # --------------------------------------------------------------------------- #
    
    def load_module_version(self, module_name: str) -> str:
        """
        Get the version of a module.
        """
        try:
            return importlib.metadata.version(module_name)
        except importlib.metadata.PackageNotFoundError:
            return "not installed"
        
    # --------------------------------------------------------------------------- #

    def logMsg(
        self, 
        msg: str, 
        level: int = 0, 
        container: DeltaGenerator | None = None, 
        color: str | None = None
    ) -> None:
        """
        Log messages with different levels to both Streamlit and the console.

        Parameters
        ----------
        msg : str
            The text message to log. his is **required argument**.
            Pass a raw string or call a translation module so it 
            can log and appear the string to the system console
            and the UI.
        level : int, default 0
            Determines which Streamlit UI element to use. 
            Except for level 0, messages are printed to both the UI
            and the system console.
            + 1 = success
            + 2 = caption
            + 3 = badge
            + 6 = write
            + 7 = text
            + 8 = subheader
            + 9 = title
            + 0 = console only
        container: DeltaGenerator, optional
            A dynamic Streamlit container or placeholder 
            (e.g., `st.empty()`). This act as an anchor to reserve 
            UI space in advance, allowing content to be updated 
            later via this function.
            + Examples
            ```
            view = st.empty()
            logMsg(container = view, msg="..")
            ```
        color: str, optional
            If passed no argument, the default color is `blue`.
        """
        c = container or self.default_container
        badge_color = color or self.default_color

        actions = {
            1: lambda: c.success(msg),
            2: lambda: c.caption(msg),
            3: lambda: c.badge(msg, color=badge_color),
            6: lambda: c.write(msg),
            7: lambda: c.text(msg),
            8: lambda: c.subheader(msg),
            9: lambda: c.title(msg),
        }

        if level in actions:
            actions[level]()

        print(re.sub(r":\w+\[(.*?)\]", r"\1", msg))
