#!/usr/bin/python

import soccerdata as sd
from datetime import datetime
import os
import sys

sys.path.append("/home/morten/Develop/packing-report/xT-impact/")
from proto_files.games import GameList, Game
from proto_files.player import Player
from proto_files.player import Game as PlayerGame

from pathlib import PosixPath
import pandas as pd
from global_packing import init_logging, get_xT_modell, LEAGUE_LIST
import socceraction.spadl as spadl
import socceraction.xthreat as xthreat
import numpy as np
from handlers_packing import LineupHandler, TableHandler

keeper_actions_save = ["keeper_save"]
# keeper_actions_other = ["keeper_claim", "keeper_punch"] #, "keeper_pick_up"
defensive_actions = ["tackle", "interception", "clearance"]  # "keeper_save"

def add_lineup(df_players):
    linuep_handler = LineupHandler()
    team_names = df_players.team_name.unique()
    for team_name in team_names:
        linuep_handler.add_lineup(team_name, df_players)
    linuep_handler.write_lineup()


def get_top_league_elo(df_elo):
    top_league = 0
    for league in LEAGUE_LIST:
        league_elo = np.mean(df_elo[df_elo["league"] == league]["elo"])
        if league_elo > top_league:
            top_league = league_elo
    return top_league


def update_table_entries(
    home_team_id, home_team, away_team_id, away_team, home_goals, away_goals, league
):
    table_handler = TableHandler()
    table_handler.update_table(league, home_team_id, home_team, True, home_goals, away_goals)
    table_handler.update_table(league, away_team_id, away_team, False, away_goals, home_goals)
    table_handler.write_table()


def get_table_info(team, opp, league, home):
    table_handler = TableHandler()
    return table_handler.get_table_info(team, opp, league, home)


def calc_game_score(df_teams, df_players, df_events):
    df_actions = (
        spadl.opta.convert_to_actions(df_events, df_teams["team_id"].values[0])
        .merge(spadl.actiontypes_df())
        .merge(df_players[["player_name", "player_id"]])
    )
    df_actions_ltr = spadl.play_left_to_right(df_actions, df_teams["team_id"].values[0])
    df_shot_actions = pd.concat(
        [
            df_actions_ltr[df_actions_ltr["type_id"] == 11],
            df_actions_ltr[df_actions_ltr["type_id"] == 12],
            df_actions_ltr[df_actions_ltr["type_id"] == 13],
        ]
    )
    df_goals = df_shot_actions[df_shot_actions["result_id"] == 1]
    df_own_goals = df_actions_ltr[df_actions_ltr["result_id"] == 3]
    df_all_goals = pd.concat([df_goals, df_own_goals], ignore_index=True)
    df_all_goals = pd.DataFrame(
        {
            "time": ((df_all_goals["period_id"] - 1) * 45)
            + (df_all_goals["time_seconds"] / 60),
            "team": [
                x["team_id"]
                if (x["result_id"] == 1)
                else df_teams[df_teams["team_id"] != x["team_id"]]["team_id"].values[0]
                for _, x in df_all_goals.iterrows()
            ],
        }
    )
    home_goals = df_all_goals[
        df_all_goals["team"] == df_teams["team_id"].values[0]
    ].shape[0]
    away_goals = df_all_goals[
        df_all_goals["team"] == df_teams["team_id"].values[1]
    ].shape[0]
    return home_goals, away_goals

def update_proto(xTModell, game_entry, ws, live, ce):
    league = game_entry.league
    game_id = int(game_entry.game_id)
    loader = ws.read_events(
        match_id=int(game_id), force_cache=True, output_fmt="loader", live=live
    )
    df_teams = loader.teams(game_id=game_id)
    df_players = loader.players(game_id=game_id)
    df_teams = loader.teams(game_id=game_id)
    add_lineup(df_players.merge(df_teams))
    df_events = loader.events(game_id=game_id)
    df_events.dropna(subset=["player_id"], inplace=True)
    home_score, away_score = calc_game_score(df_teams, df_players, df_events)
    update_table_entries(
        df_teams.team_id.values[0],
        df_teams.team_name.values[0],
        df_teams.team_id.values[1],
        df_teams.team_name.values[1],
        home_score,
        away_score,
        league,
    )
    ce_df = ce.read_by_date(game_entry["game_date"][:10])
    # defensive actions
    df_actions = (
        spadl.opta.convert_to_actions(df_events, df_teams.team_id.values[0])
        .merge(spadl.actiontypes_df())
        .merge(df_players[["player_name", "player_id"]])
    )
    df_actions_ltr = spadl.play_left_to_right(
        df_actions, df_teams.team_id.values[0]
    )
    df_actions_rtl = spadl.play_left_to_right(
        df_actions, df_teams.team_id.values[0]
    )
    df_all_defense_pressing = df_actions_ltr[
        df_actions_ltr["type_name"].isin(defensive_actions)
    ]
    df_all_defense_pressing = df_all_defense_pressing[
        df_all_defense_pressing["result_id"] == 1
    ]
    df_all_defense_normal = df_actions_rtl[
        df_actions_rtl["type_name"].isin(defensive_actions)
    ]
    df_all_defense_normal = df_all_defense_normal[
        df_all_defense_normal["result_id"] == 1
    ]
    xt_defense_ratings_pressing = xTModell.rate_defensive(
        df_all_defense_pressing.reset_index()
    )
    xt_defense_ratings_normal = xTModell.rate_defensive(
        df_all_defense_normal.reset_index()
    )
    df_xd_press = pd.DataFrame(
        {
            "time": ((df_all_defense_pressing["period_id"] - 1) * 45)
            + (df_all_defense_pressing["time_seconds"] / 60),
            "team": df_all_defense_pressing["team_id"],
            "xd_press": xt_defense_ratings_pressing,
        }
    )
    df_xd_normal = pd.DataFrame(
        {
            "time": ((df_all_defense_normal["period_id"] - 1) * 45)
            + (df_all_defense_normal["time_seconds"] / 60),
            "team": df_all_defense_normal["team_id"],
            "xd_normal": xt_defense_ratings_normal,
        }
    )
    # attacking actions
    df_attacking_actions = xthreat.get_successful_move_actions(df_actions_ltr)
    xt_attacking_ratings = xTModell.rate(df_attacking_actions)
    df_xt = pd.DataFrame(
        {
            "time": ((df_attacking_actions["period_id"] - 1) * 45)
            + (df_attacking_actions["time_seconds"] / 60),
            "team": df_attacking_actions["team_id"],
            "xt": xt_attacking_ratings,
        }
    )
    # goalie actions
    # TODO fix goalie
    # df_keeper_save = df_actions_rtl[df_actions_rtl['type_name'].isin(keeper_actions_save)]
    # df_keeper_save = df_keeper_save[df_keeper_save['result_id'] == 1]
    # xt_keeper_save = xTModell.rate_defensive(df_keeper_save.reset_index())
    # xG actions
    df_shot_actions = df_actions_ltr[df_actions_ltr["type_id"] == 11]
    xG_ratings = xTModell.rate_xG(df_shot_actions.reset_index())
    df_xg = pd.DataFrame(
        {
            "time": ((df_shot_actions["period_id"] - 1) * 45)
            + (df_shot_actions["time_seconds"] / 60),
            "team": df_shot_actions["team_id"],
            "xg": xG_ratings,
        }
    )
    # GI actions
    df_goals = df_shot_actions[df_shot_actions["result_id"] == 1]
    df_own_goals = df_actions_ltr[df_actions_ltr["result_id"] == 3]
    df_all_goals = pd.concat([df_goals, df_own_goals], ignore_index=True)
    df_all_goals = pd.DataFrame(
        {
            "time": ((df_all_goals["period_id"] - 1) * 45)
            + (df_all_goals["time_seconds"] / 60),
            "team": [
                x["team_id"]
                if (x["result_id"] == 1)
                else df_teams[df_teams["team_id"] != x["team_id"]][
                    "team_id"
                ].values[0]
                for _, x in df_all_goals.iterrows()
            ],
        }
    )

    # create people dict
    people_dict = {}
    for people_id in df_players["player_id"]:
        people_dict[people_id] = {}
        people_dict[people_id]["name"] = df_players[
            df_players["player_id"] == people_id
        ]["player_name"].values[0]
        people_dict[people_id]["played"] = (
            False
            if df_players[df_players["player_id"] == people_id][
                "minutes_played"
            ].values[0]
            == 0
            else True
        )
        people_dict[people_id]["opp_team_name"] = df_teams[
            df_teams["team_id"]
            != df_players[df_players["player_id"] == people_id]["team_id"].values[0]
        ]["team_name"].values[0]
        people_dict[people_id]["team_name"] = df_teams[
            df_teams["team_id"]
            == df_players[df_players["player_id"] == people_id]["team_id"].values[0]
        ]["team_name"].values[0]
        people_dict[people_id]["team_id"] = df_players[
            df_players["player_id"] == people_id
        ]["team_id"].values[0]
        people_dict[people_id]["opp_id"] = df_teams[
            df_teams["team_id"] != people_dict[people_id]["team_id"]
        ]["team_id"].values[0]
        people_dict[people_id]["is_starter"] = df_players[
            df_players["player_id"] == people_id
        ]["is_starter"].values[0]
        people_dict[people_id]["home"] = (
            df_teams.team_id.values[0] == people_dict[people_id]["team_id"]
        )
        people_dict[people_id]["table_info"] = get_table_info(
            people_dict[people_id]["team_id"],
            people_dict[people_id]["opp_id"],
            league,
            people_dict[people_id]["home"],
        )
        people_dict[people_id]["minutes"] = df_players[
            df_players["player_id"] == people_id
        ]["minutes_played"].values[0]

        people_dict[people_id]["team_elo"] = ce_df.loc[
            people_dict[people_id]["team_name"]
        ].elo
        people_dict[people_id]["opp_elo"] = ce_df.loc[
            people_dict[people_id]["opp_team_name"]
        ].elo
        people_dict[people_id]["league_elo"] = np.mean(
            ce_df[ce_df["league"] == league].elo
        )
        people_dict[people_id]["top_league_elo"] = get_top_league_elo(ce_df)

        # TODO
        # people_dict[people_id]['full_game_length'] = df_games[df_games['game_id'] == game_id]['duration'].values[0]
        people_dict[people_id]["full_game_length"] = 90
        people_dict[people_id]["minutes_started"] = (
            0
            if people_dict[people_id]["is_starter"]
            else people_dict[people_id]["full_game_length"]
            - people_dict[people_id]["minutes"]
        )
        people_dict[people_id]["minutes_ended"] = (
            people_dict[people_id]["minutes_started"]
            + people_dict[people_id]["minutes"]
        )

        people_dict[people_id]["game_date"] = game_entry["game_date"][:10]
        people_dict[people_id]["xG"] = (
            df_xg.loc[
                (df_xg["team"] == people_dict[people_id]["team_id"])
                & (df_xg["time"] > people_dict[people_id]["minutes_started"])
                & (df_xg["time"] < people_dict[people_id]["minutes_ended"])
            ]["xg"].sum()
            / 11
        )
        people_dict[people_id]["xT_all"] = (
            df_xt.loc[
                (df_xt["team"] == people_dict[people_id]["team_id"])
                & (df_xt["time"] > people_dict[people_id]["minutes_started"])
                & (df_xt["time"] < people_dict[people_id]["minutes_ended"])
            ]["xt"].sum()
            / 11
        )  # all
        people_dict[people_id]["xT_only_pos"] = (
            df_xt.loc[
                (df_xt["team"] == people_dict[people_id]["team_id"])
                & (df_xt["time"] > people_dict[people_id]["minutes_started"])
                & (df_xt["time"] < people_dict[people_id]["minutes_ended"])
                & (df_xt["xt"] > 0)
            ]["xt"].sum()
            / 11
        )  # only positiv
        people_dict[people_id]["xD_press"] = (
            df_xd_press.loc[
                (df_xd_press["team"] == people_dict[people_id]["team_id"])
                & (df_xd_press["time"] > people_dict[people_id]["minutes_started"])
                & (df_xd_press["time"] < people_dict[people_id]["minutes_ended"])
            ]["xd_press"].sum()
            / 11
        )
        people_dict[people_id]["xD_def"] = (
            df_xd_normal.loc[
                (df_xd_normal["team"] == people_dict[people_id]["team_id"])
                & (df_xd_normal["time"] > people_dict[people_id]["minutes_started"])
                & (df_xd_normal["time"] < people_dict[people_id]["minutes_ended"])
            ]["xd_normal"].sum()
            / 11
        )
        # TODO fix goalie
        people_dict[people_id]["xK_save"] = 0
        people_dict[people_id]["xG_against"] = (
            df_xg.loc[
                (df_xg["team"] == people_dict[people_id]["opp_id"])
                & (df_xg["time"] > people_dict[people_id]["minutes_started"])
                & (df_xg["time"] < people_dict[people_id]["minutes_ended"])
            ]["xg"].sum()
            / 11
        )
        people_dict[people_id]["xT_against_all"] = (
            df_xt.loc[
                (df_xt["team"] == people_dict[people_id]["opp_id"])
                & (df_xt["time"] > people_dict[people_id]["minutes_started"])
                & (df_xt["time"] < people_dict[people_id]["minutes_ended"])
            ]["xt"].sum()
            / 11
        )  # all
        people_dict[people_id]["xT_against_only_pos"] = (
            df_xt.loc[
                (df_xt["team"] == people_dict[people_id]["opp_id"])
                & (df_xt["time"] > people_dict[people_id]["minutes_started"])
                & (df_xt["time"] < people_dict[people_id]["minutes_ended"])
                & (df_xt["xt"] > 0)
            ]["xt"].sum()
            / 11
        )  # only positiv
        people_dict[people_id]["gI"] = (
            df_all_goals.loc[
                (df_all_goals["team"] == people_dict[people_id]["team_id"])
                & (df_all_goals["time"] > people_dict[people_id]["minutes_started"])
                & (df_all_goals["time"] < people_dict[people_id]["minutes_ended"])
            ].shape[0]
            - df_all_goals.loc[
                (df_all_goals["team"] == people_dict[people_id]["opp_id"])
                & (df_all_goals["time"] > people_dict[people_id]["minutes_started"])
                & (df_all_goals["time"] < people_dict[people_id]["minutes_ended"])
            ].shape[0]
        ) / 11

    # create Proto files
    for player_id in people_dict.keys():
        if not people_dict[player_id]["played"]:
            # only handle player if he played
            continue
        # search dir for existing proto file:
        if str(player_id) + ".pb" not in os.listdir("/home/morten/Develop/packing-report/xT-impact/data/data_0.3/"):
            # create new proto obj
            proto_player = Player()
            proto_player.player_id = player_id
            proto_player.player_name = people_dict[player_id]["name"]
            # add new player to csv
            pd.DataFrame(
                {"player_name": [people_dict[player_id]["name"]], "id": [player_id]}
            ).to_csv(
                "/home/morten/Develop/packing-report/xT-impact/data/data_0.3/player_db.csv",
                mode="a",
                header=False,
                index=False,
                sep=";",
            )
        else:
            proto_player = Player().parse(
                open(f"/home/morten/Develop/packing-report/xT-impact/data/data_0.3/{str(player_id)}.pb", "rb").read()
            )
        # create game
        player_game = PlayerGame()
        player_game.game_id = game_id
        player_game.game_date = people_dict[player_id]["game_date"]
        player_game.xg = people_dict[player_id]["xG"]
        player_game.xt_all = people_dict[player_id]["xT_all"]
        player_game.xt_only_pos = people_dict[player_id]["xT_only_pos"]
        player_game.xd_press = people_dict[player_id]["xD_press"]
        player_game.xd_def = people_dict[player_id]["xD_def"]
        player_game.xk_save = people_dict[player_id]["xK_save"]
        player_game.xg_against = people_dict[player_id]["xG_against"]
        player_game.xt_against_all = people_dict[player_id]["xT_against_all"]
        player_game.xt_against_only_pos = people_dict[player_id][
            "xT_against_only_pos"
        ]
        player_game.gi = people_dict[player_id]["gI"]
        player_game.starter = people_dict[player_id]["is_starter"]
        player_game.team = people_dict[player_id]["team_id"]
        player_game.home = people_dict[player_id]["home"]
        player_game.minutes_played = people_dict[player_id]["minutes"]
        player_game.team_elo = people_dict[player_id]["team_elo"]
        player_game.opposition_elo = people_dict[player_id]["opp_elo"]
        player_game.league_elo = people_dict[player_id]["league_elo"]
        player_game.top_league_elo = people_dict[player_id]["top_league_elo"]

        player_game.team_pos = people_dict[player_id]["table_info"][
            "team_table_pos"
        ]
        player_game.opp_position = people_dict[player_id]["table_info"][
            "opp_table_pos"
        ]
        player_game.team_pos_home_away = people_dict[player_id]["table_info"][
            "team_home_away_table_pos"
        ]
        player_game.opp_position_home_away = people_dict[player_id]["table_info"][
            "opp_home_away_table_pos"
        ]
        player_game.team_form_for = people_dict[player_id]["table_info"][
            "team_form_for"
        ]
        player_game.team_form_against = people_dict[player_id]["table_info"][
            "team_form_against"
        ]
        player_game.opp_form_for = people_dict[player_id]["table_info"][
            "opp_form_for"
        ]
        player_game.opp_form_against = people_dict[player_id]["table_info"][
            "opp_form_against"
        ]
        player_game.team_form_home_away_for = people_dict[player_id]["table_info"][
            "team_home_away_form_for"
        ]
        player_game.team_form_home_away_against = people_dict[player_id][
            "table_info"
        ]["team_home_away_form_against"]
        player_game.opp_form_home_away_for = people_dict[player_id]["table_info"][
            "opp_home_away_form_for"
        ]
        player_game.opp_form_home_away_against = people_dict[player_id][
            "table_info"
        ]["opp_home_away_form_against"]

        proto_player.expected_game_impact.append(player_game)
        with open(f"/home/morten/Develop/packing-report/xT-impact/data/data_0.3/{str(player_id)}.pb", "wb") as f:
            f.write(bytes(proto_player))


def load_data(xTModell):
    game_id = 0 
    logger = init_logging()
    # load past_games.pb
    past_games = GameList().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/past_games.pb", "rb").read())
    logger.info("Loaded past games data")
    # scrape game data
    df_games = pd.DataFrame(past_games.games)
    df_games = df_games.sort_values("game_date")
    ce = sd.ClubElo(
        no_cache=False,
        no_store=False,
        data_dir=PosixPath("/home/morten/Develop/Open-Data/soccerdata"),
    )
    ws = sd.WhoScored(
        leagues=LEAGUE_LIST,  # "GER-Bundesliga",
        seasons=[22],
        no_cache=False,
        no_store=False,
        data_dir=PosixPath("/home/morten/Develop/Open-Data/soccerdata"),
        path_to_browser="/usr/bin/chromium",
        headless=False,
    )
    for _, game_entry in df_games.iterrows():
        try:
            update_proto(xTModell, game_entry, ws, False, ce)
        except TypeError:
            logger.error(f"Failed to retrieve game with id {game_id}")
            try:
                update_proto(xTModell, game_entry, ws, True, ce)
                logger.error(f"Got it anyway")
            except TypeError:
                logger.error(f"Couldnt get it anyway")
    # remove game from past_games (Just remove file?)
    os.remove("/home/morten/Develop/packing-report/xT-impact/automation/database/past_games.pb")


if __name__ == "__main__":
    xTModell = get_xT_modell()
    load_data(xTModell)
