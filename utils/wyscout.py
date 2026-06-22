import os
import sys
import json
import pandas as pd
from pathlib import Path
from rich.console import Console


class ProjectEnvironment:
    """Manages project roots, paths, and global configuration."""

    def __init__(self, anchor_files: list[str] = None):
        self.indicators = anchor_files or ["app.py", "notebook"]
        self.root_path = self._find_root()

    def _find_root(self) -> Path:
        """Seek upward to find the project root dynamically."""
        current = Path.cwd().resolve()

        for path in [current] + list(current.parents):
            if all((path / indicator).exists() for indicator in self.indicators):
                return path
            
            print("WARNING: Project root markers not found. Revert to cwd().")
            return current
        
    def activate(self, change_cwd: bool = True):
        """Injects root into sys.path and optionally changes the working directory."""
        if str(self.root_path) not in sys.path:
            sys.path.insert(0, str(self.root_path))

        if change_cwd:
            os.chdir(self.root_path)
        
        Console().print(f"[green]Environment initialized at:[/green] {self.root_path}")
        return self


class Wyscout:
    def __init__(self, env: ProjectEnvironment = None):
        self.env = env or ProjectEnvironment().activate()
        self._rich_console = Console()
        self.path_data = {
            'events': self.env.root_path / "socceraction" / "events",
            'matches': self.env.root_path / "socceraction" / "matches",
            'players': self.env.root_path / "socceraction" / "players.json",
            'teams': self.env.root_path / "socceraction" / "teams.json",
            '1903496': self.env.root_path / "socceraction" / "1903496.json"
        }
    
    def read_json_file(self, target: str | Path) -> str:
        """
        Reads a file and automatically decodes unicode escape sequences.
        
        Accepts:
        - A dictionary key from self.path_data (e.g., 'players', 'teams')
        - A direct Path object or relative path string
        """
        if isinstance(target, str) and target in self.path_data:
            file_path = self.path_data[target]
        else:
            file_path = self.env.root_path / target

        if not file_path.is_file():
            raise FileNotFoundError(f"Target JSON file not found at: {file_path}")
        
        with open(file_path, 'rb') as json_file:
            return json_file.read().decode('unicode_escape')

    def get_dataframe(self, target: str) -> pd.DataFrame:
        """Helper method to convert the processed JSON string directly to a DataFrame"""
        raw_json = self.read_json_file(target)
        data = json.loads(raw_json, strict=False)
        
        if isinstance(data, dict) and 'events' in data:
            return pd.DataFrame(data['events'])
        return pd.DataFrame(data)
