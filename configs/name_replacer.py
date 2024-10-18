import json
class NameReplacer:
    def __init__(self):
        self.team_substitutes = json.load(open("configs/teamname_replacements.json"))
    def replace_name(self, club_name: str) -> str:
        for replace in self.team_substitutes:
            for name in self.team_substitutes[replace]:
                if name == club_name:
                    return replace
        raise ValueError(f"Could not find replacement for {club_name}")