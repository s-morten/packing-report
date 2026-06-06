import json
from pathlib import Path


class NameReplacer:
    def __init__(self):
        config_path = Path(__file__).resolve().parent / "teamname_replacements.json"
        self.team_substitutes = json.load(open(config_path))

    def replace_name(self, club_name: str) -> str:
        for replace in self.team_substitutes:
            for name in self.team_substitutes[replace]:
                if name == club_name:
                    return replace
        raise ValueError(f"Could not find replacement for {club_name}")
