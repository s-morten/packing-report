import json
from functools import cache
from pathlib import Path


@cache
def _load_team_substitutes() -> dict[str, list[str]]:
    config_path = Path(__file__).resolve().parent / "teamname_replacements.json"
    with open(config_path) as f:
        return json.load(f)


def replace_name(club_name: str) -> str:
    for replace, names in _load_team_substitutes().items():
        if club_name in names:
            return replace
    raise ValueError(f"Could not find replacement for {club_name}")
