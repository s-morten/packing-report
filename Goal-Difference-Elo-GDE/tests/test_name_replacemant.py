import soccerdata as sd
import pytest
from pathlib import PosixPath
import json



def test_team_name_replacement_ws():
    in_config = []
    # load config
    config = json.load(open("/home/morten/soccerdata/config/teamname_replacements.json", "r"))
    ws = sd.WhoScored(
        leagues=["GER-Bundesliga2", "GER-Bundesliga"],
        seasons=[16, 17, 18, 19, 20, 21],
        no_cache=False,
        no_store=False,
        data_dir=PosixPath("/home/morten/Develop/Open-Data/soccerdata"),
        path_to_browser="/usr/bin/chromium",
        headless=True,
    )
    # load schedule
    schedule = ws.read_schedule()
    teams = schedule["home_team"].unique()
    for team in teams:
        for to_replace in config:
            for from_replace in config[to_replace]:
                if team == from_replace:
                    in_config.append(team)
    set_diff = [x for x in teams if x not in in_config]

    assert len(set_diff) == 0, f"{set_diff}"


def test_team_name_replacement_ce():
    in_config = []
    # load config
    config = json.load(open("/home/morten/soccerdata/config/teamname_replacements.json", "r"))
    ce = sd.ClubElo()
    seasons = [16, 17, 18, 19, 20, 21]
    teams = set()
    for year in seasons:
        df = ce.read_by_date(f"20{year}-08-31").reset_index()
        for t in df[df["league"].isin(["GER-Bundesliga2", "GER-Bundesliga"])].team.values:
            teams.add(t)
    for team in teams:
        for to_replace in config:
            for from_replace in config[to_replace]:
                if team == from_replace:
                    in_config.append(team)
    set_diff = [x for x in teams if x not in in_config]

    assert len(set_diff) == 0, f"{set_diff}"