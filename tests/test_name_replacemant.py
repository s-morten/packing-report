import soccerdata as sd
import pytest
from pathlib import PosixPath
import json
import numpy as np
import toml
import sys
import filesystem_io.filesystem_io as filesystem_io


def test_team_name_replacement_ws():
    in_config = set()
    # load config
    config = json.load(open("/home/morten/soccerdata/config/teamname_replacements.json", "r"))
    run_config = toml.load("gde/config.toml")
    ws = sd.WhoScored(
        leagues=run_config["whoscored"]["leagues"],
        seasons=run_config["whoscored"]["seasons"],
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
                    in_config.add(team)
    set_diff = [x for x in teams if x not in in_config]

    assert len(set_diff) == 0, f"{set_diff}"


def test_team_name_replacement_ce():
    in_config = set()
    # load config
    config = json.load(open("/home/morten/soccerdata/config/teamname_replacements.json", "r"))
    run_config = toml.load("gde/config.toml")
    
    ce = sd.ClubElo()
    seasons = run_config["whoscored"]["seasons"]
    teams = set()
    for year in seasons:
        df = ce.read_by_date(f"20{year}-08-31").reset_index()
        for t in df[df["league"].isin(run_config["whoscored"]["leagues"])].team.values:
            teams.add(t)
    for team in teams:
        for to_replace in config:
            for from_replace in config[to_replace]:
                if team == from_replace:
                    in_config.add(team)
    set_diff = [x for x in teams if x not in in_config]

    assert len(set_diff) == 0, f"{set_diff}"

def test_name_replacements_footballsquads():
    valid_countries = ["eng", "ger"]
    ignore = ["wsl", # womans super league
              "confer", # National League Eng
              "confnat", # National League Eng
              "national", # National League Eng
              "confprem", # Premier League Eng
              "fltwo", # League Two Eng
              "div3", # League Two Eng
              "flone", # League One Eng
              "div2", # League One Eng
              "flcham", # Championship Eng
              "div1", # Championship Eng
              "spalali", # La Liga Spa
              "spalali2", # La Liga 2 Spa
              "spasega", # La Liga 2 Spa
              "seriea", # Serie A It
              "serieb", # Serie B It
              "fralig1", # Ligue 1 Fra
              "fradiv1", # Ligue 1 Fra
              "fralig2" # Ligue 2 Fra
              ]
    in_config_league, in_config = set(), set()
    cache_file_list = filesystem_io.directory_files("/home/morten/Develop/packing-report/gde/.cache_footballsquads")
    config = json.load(open("/home/morten/soccerdata/config/teamname_replacements.json", "r"))
    league_config = json.load(open("/home/morten/soccerdata/config/league_replacements.json", "r"))
    teams, leagues = set(), set()
    for cache_file in cache_file_list:
        country, league, team = (cfs:=cache_file.split("_"))[1], cfs[2], cfs[3].split(".")[0]
        leagues.add(league)
        if country in valid_countries:
            for to_replace in league_config:
                for from_replace in league_config[to_replace]:
                    if league == from_replace:
                        in_config_league.add(league)
                        teams.add(team)

    for team in teams:
        for to_replace in config:
            for from_replace in config[to_replace]:
                if team == from_replace:
                    in_config.add(team)
    print(in_config_league)
    set_diff = [x for x in leagues if x not in in_config_league and x not in ignore]
    assert len(set_diff) == 0, f"{set_diff}"
    set_diff = [x for x in teams if x not in in_config]
    assert len(set_diff) == 0, f"{set_diff}"