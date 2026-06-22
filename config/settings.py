import importlib.metadata
import pandas as pd
import re
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from rich.console import Console

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
    cache_sd: Path
    events_path: Callable[[str, str | int, str], Path]

_path = Path(__file__).resolve().parent.parent

GET_PATH: GetPath = {
    'base_dir': _path,
    'locales': _path / "locales",
    'cache_fb': _path / "cached_data" / "FBref",
    'cache_ws': _path / "cached_data" / "WhoScored",
    'cache_sd': _path / "cached_data" / "soccerdata",
    'events_path': lambda league, season, team: (
        _path / "cached_data" / "WhoScored" / "events" / "csv" / f"{league}_{season}" / team
    ),
    'badges': _path / "static" / "images" / "badges"
}
"""GetPath: Define the core directory.

Attributes:
    ['base_dir'] (**standard key**, base directory) :
    ['locales'] (**standard key**, language folder) :
    ['cache_fb'] (**standard key**, cached dataset from fbref) :
    ['cache_ws'] (**standard key**, cached dataset from whoscored) :
    ['cache_sd'] (**standard key**, cached raw data from soccerdata) :
    ['events_path'] (**callable key**, events dataset path) : `league` `season` `team` (required parameters)

## _Example:_
```
# standard key lookup
GET_PATH['locales'] # "/home/lyra/veritasq-sv/locales"

# callable key invocation
GET_PATH['events_path'](
    league="ENG-Premier League", 
    season=2526, 
    team="Manchester United"
) # "/home/lyra/veritasq-sv/cached_data/WhoScored/ENG-Premier League_2526/Manchester United"
```
"""


# ------------------------------------------------------------------------------- #

class WhoScored(TypedDict):
    regional: Path
    tournament: Path
    game_info: Path
    schedule: Path
    raw_events: Path
    events: Callable[[str, str | int, str, str, str | int], Path]
    spadl: Callable[[str, str | int, str, str], Path]
    badge: int

GET_WHOSCORED: WhoScored = {
    'regional': GET_PATH['cache_ws'] / "_regional_data.csv",
    'tournament': GET_PATH['cache_ws'] / "_tournaments_data.csv",
    'game_info': GET_PATH['cache_ws'] / "_game_info.jsonl",
    'schedule': GET_PATH['cache_ws'] / "_schedule.csv",
    'raw_events': GET_PATH['cache_ws'] / "events" / "json",
    'events': lambda league, season, team, game_id: (
        GET_PATH['events_path'](league, season, team) / f"_events_{game_id}.csv"
    ),
    'spadl': lambda league, season, type: (
        GET_PATH['cache_ws'] / "events" / f"{league}_{season}_{type}.parquet"
    ),
    'badge': lambda id: (
        GET_PATH['badges'] / f"{id}.png"
    )
}
"""WhoScored: Define the dataset location for WhoScored.

Attributes:
    ['regional'] (**standard key**, offline dataset for regions) :
    ['tournament'] (**standard key**, offline dataset for tournaments) :
    ['game_info'] (**standard key**, offline dataset for game_info) :
    ['schedule'] (**standard key**, offline dataset for schedule) :
    ['events'] (**callable key**, events dataset location) : `league` `season` `team` `game_id` (required parameters)
    ['spadl'] (**callable key**, events dataset location) : `league` `season` `type` (required parameters)
    ['badge'] (**callable key**, events dataset location) : `id` (required parameters)

## _Example:_
```
# standard key lookup
GET_PATH['regional'] # "/home/lyra/veritasq-sv/cached_data/WhoScored/_regional_data.csv"

# callable key invocation
GET_PATH['events'](
    league="ENG-Premier League", 
    season=2526, 
    team="Manchester United",
    game_id=1903490
) # "/home/lyra/veritasq-sv/cached_data/WhoScored/ENG-Premier League_2526/Manchester United/_events_1903490.csv"
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
        self._rich_console = Console()
        self.master_club_registry = {
            'Leeds United': {
                'fbref': "Leeds United",
                'whoscored': "Leeds",
                'flashscore': "Leeds"
            },
            'Leicester City': {
                'fbref': "Leicester City",
                'whoscored': "Leicester",
                'flashscore': "Leicester"
            },
            'Manchester Utd': {
                'fbref': "Manchester Utd",
                'whoscored': "Manchester United",
                'flashscore': "Manchester United"
            },
            'Newcastle United': {
                'fbref': "Newcastle United",
                'whoscored': "Newcastle",
                'flashscore': "Newcastle"
            },
            'Tottenham Hotspur': {
                'fbref': "Tottenham Hotspur",
                'whoscored': "Tottenham",
                'flashscore': "Tottenham"
            },
            'West Brom': {
                'fbref': "West Brom",
                'whoscored': "West Bromwich Albion",
                'flashscore': "West Bromwich Albion"
            },
            'West Ham United': {
                'fbref': "West Ham United",
                'whoscored': "West Ham",
                'flashscore': "West Ham"
            },
            'Norwich City': {
                'fbref': "Norwich City",
                'whoscored': "Norwich",
                'flashscore': "Norwich"
            },
            'Luton Town': {
                'fbref': "Luton Town",
                'whoscored': "Luton",
                'flashscore': "Luton"
            },
            'Ipswich Town': {
                'fbref': "Ipswich Town",
                'whoscored': "Ipswich",
                'flashscore': "Ipswich"
            },
            'Alavés': {
                'fbref': "Alavés",
                'whoscored': "Deportivo Alaves",
                'flashscore': "Alavés"
            },
            'Atlético Madrid': {
                'fbref': "Atlético Madrid",
                'whoscored': "Atletico Madrid",
                'flashscore': "Atlético Madrid"
            },
            'Cádiz': {
                'fbref': "Cádiz",
                'whoscored': "Cadiz",
                'flashscore': "Cádiz"
            },
            'Huesca': {
                'fbref': "Huesca",
                'whoscored': "SD Huesca",
                'flashscore': "Huesca"
            },
            'Valladolid': {
                'fbref': "Valladolid",
                'whoscored': "Real Valladolid",
                'flashscore': "Valladolid"
            },
            'Almería': {
                'fbref': "Almería",
                'whoscored': "Almeria",
                'flashscore': "Almería"
            },
            'Leganés': {
                'fbref': "Leganés",
                'whoscored': "Leganes",
                'flashscore': "Leganés"
            },
            'Oviedo': {
                'fbref': "Oviedo",
                'whoscored': "Real Oviedo",
                'flashscore': "Oviedo"
            },
            'Nîmes': {
                'fbref': "Nîmes",
                'whoscored': "Nimes",
                'flashscore': "Nîmes"
            },
            'Saint-Étienne': {
                'fbref': "Saint-Étienne",
                'whoscored': "Saint-Etienne",
                'flashscore': "Saint-Étienne"
            },
            'Ajaccio': {
                'fbref': "Ajaccio",
                'whoscored': "AC Ajaccio",
                'flashscore': "Ajaccio"
            },
            'N. Macedonia': {
                'fbref': "N. Macedonia",
                'whoscored': "North Macedonia",
                'flashscore': "N. Macedonia"
            },
            'Türkiye': {
                'fbref': "Türkiye",
                'whoscored': "Turkiye",
                'flashscore': "Türkiye"
            },
            'China PR': {
                'fbref': "China PR",
                'whoscored': "China",
                'flashscore': "China PR"
            },
            'Korea Republic': {
                'fbref': "Korea Republic",
                'whoscored': "South Korea",
                'flashscore': "Korea Republic"
            },
            'Rep. of Ireland': {
                'fbref': "Rep. of Ireland",
                'whoscored': "Ireland",
                'flashscore': "Rep. of Ireland"
            },
            'IR Iran': {
                'fbref': "IR Iran",
                'whoscored': "Iran",
                'flashscore': "IR Iran"
            },
            'United States': {
                'fbref': "United States",
                'whoscored': "USA",
                'flashscore': "United States"
            },
            'Hellas Verona': {
                'fbref': "Hellas Verona",
                'whoscored': "Verona",
                'flashscore': "Hellas Verona"
            },
            'Milan': {
                'fbref': "Milan",
                'whoscored': "AC Milan",
                'flashscore': "Milan"
            },
            'Parma': {
                'fbref': "Parma",
                'whoscored': "Parma Calcio 1913",
                'flashscore': "Parma"
            },
            'Arminia': {
                'fbref': "Arminia",
                'whoscored': "Arminia Bielefeld",
                'flashscore': "Arminia"
            },
            'Dortmund': {
                'fbref': "Dortmund",
                'whoscored': "Borussia Dortmund",
                'flashscore': "Dortmund"
            },
            'Gladbach': {
                'fbref': "Gladbach",
                'whoscored': "Borussia M.Gladbach",
                'flashscore': "Gladbach"
            },
            'Hertha BSC': {
                'fbref': "Hertha BSC",
                'whoscored': "Hertha Berlin",
                'flashscore': "Hertha BSC"
            },
            'Köln': {
                'fbref': "Köln",
                'whoscored': "FC Koln",
                'flashscore': "Köln"
            },
            'Leverkusen': {
                'fbref': "Leverkusen",
                'whoscored': "Bayer Leverkusen",
                'flashscore': "Leverkusen"
            },
            'Stuttgart': {
                'fbref': "Stuttgart",
                'whoscored': "VfB Stuttgart",
                'flashscore': "Stuttgart"
            },
            'Greuther Fürth': {
                'fbref': "Greuther Fürth",
                'whoscored': "Greuther Fuerth",
                'flashscore': "Greuther Fürth"
            },
            'Darmstadt 98': {
                'fbref': "Darmstadt 98",
                'whoscored': "Darmstadt",
                'flashscore': "Darmstadt 98"
            },
            'Heidenheim': {
                'fbref': "Heidenheim",
                'whoscored': "FC Heidenheim",
                'flashscore': "Heidenheim"
            },
            'St Pauli': {
                'fbref': "St Pauli",
                'whoscored': "St. Pauli",
                'flashscore': "St Pauli"
            }
        }
        # Dynamically build specific translation dictionaries from the registy
        self.mappings = {}
        self._build_directional_mappings()
        
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
            + 4 = info
            + 5 = succcess
            + 6 = write
            + 7 = text
            + 8 = subheader
            + 9 = title
            + 404 = error
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

        ui_msg = msg

        console_msg = msg.replace("&emsp;", "\t").replace("&nbsp;", " ")
        console_msg = re.sub(r"\*\*:([a-zA-Z]+)\[(.*?)\]\*\*", r"[bold \1]\2[/bold \1]", console_msg)
        console_msg = re.sub(r":([a-zA-Z]+)\[(.*?)\]", r"[\1]\2[/\1]", console_msg)

        actions = {
            1: lambda: c.success(ui_msg),
            2: lambda: c.caption(ui_msg),
            3: lambda: c.badge(ui_msg, color=badge_color),
            4: lambda: c.info(ui_msg),
            5: lambda: c.success(ui_msg),
            6: lambda: c.write(ui_msg),
            7: lambda: c.text(ui_msg),
            8: lambda: c.subheader(ui_msg),
            9: lambda: c.title(ui_msg),
            404: lambda: c.error(ui_msg),
        }

        if level in actions:
            actions[level]()

        self._rich_console.print(console_msg)

    # --------------------------------------------------------------------------- #

    def _build_directional_mappings(self):
        """Automatically builds Source->Canonical and Canonical->Source maps."""
        # Find all available source platforms dynamically
        first_key = list(self.master_club_registry.keys())[0]
        sources = self.master_club_registry[first_key].keys() # ['fbref', 'whoscored', etc.]
        
        for source in sources:
            # 1. Map: Variant Name -> Canonical Name
            self.mappings[f"{source}_to_canonical"] = {
                details[source]: canonical 
                for canonical, details in self.master_club_registry.items()
            }
            # 2. Map: Canonical Name -> Variant Name
            self.mappings[f"canonical_to_{source}"] = {
                canonical: details[source] 
                for canonical, details in self.master_club_registry.items()
            }

    def load_club_registry(self, series: pd.Series, from_source: str, to_source: str) -> pd.Series:
        """Translates a column seamlessly between ANY two sources."""
        clean_series = pd.Series(series, dtype="string[python]")
        
        # Step 1: Convert original source name to the Master Canonical name
        if from_source != "canonical":
            to_canonical_map = self.mappings.get(f"{from_source}_to_canonical", {})
            clean_series = clean_series.map(to_canonical_map).fillna(clean_series)
            
        # Step 2: Convert Master Canonical name to the target source name
        if to_source != "canonical":
            to_target_map = self.mappings.get(f"canonical_to_{to_source}", {})
            clean_series = clean_series.map(to_target_map).fillna(clean_series)
            
        return clean_series

