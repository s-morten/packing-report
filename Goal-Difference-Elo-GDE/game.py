import numpy as np
import pandas as pd
import datetime

from player import Player


class GameTimeline:
    def __init__(self, ws, game_id, game_date) -> None:
        self.events = ws.read_events(match_id=[game_id])
        self.loader = ws.read_events(match_id=[game_id], output_fmt='loader')
        self.loader_players_df = self.loader.players(game_id)
        self.df_teams = self.loader.teams(game_id=game_id)

        self.player_min_dict = self._get_player_minutes_dict(self.loader_players_df, self.events)
        self.goal_dict = self._get_goal_dict(self.events)
        self.end_of_game = self._calc_game_end(self.events)
        self.goals_per_player = self._get_goals_per_player(self.goal_dict, self.player_min_dict, self.end_of_game)

        timelines = []
        characters = []
        for player in self.player_min_dict:
            player_df = self.loader_players_df[self.loader_players_df["player_id"] == player]
            player_name = player_df.player_name.values[0]
            player_starter = player_df.is_starter.values[0]
            player_team_id = player_df.team_id.values[0]
            player_minutes = player_df.minutes_played.values[0]
            player_team_name = self.df_teams[self.df_teams["team_id"]== player_team_id]["team_name"].values[0]
            characters.append([player, player_name, player_starter, player_minutes, player_team_name])
            
            ########  ########  #######  ########  #########  
            # create timeline entry
            player_elo = Player(int(player)).get_elo(game_date, player_team_name)

            player_timeline = np.empty(
                self.end_of_game + 4
            )  # + 2 for id and team id, +1 for gd, +1 for index of last minute
            player_timeline[:] = np.nan
            player_timeline[0] = player
            player_timeline[1] = self.player_min_dict[player]["team_id"]
            player_timeline[2] = (
                self.goals_per_player[player]["for"] - self.goals_per_player[player]["against"]
            )
            player_on = self.player_min_dict[player]["on"] + 3
            player_off = (
                (self.player_min_dict[player]["off"] + 3)
                if self.player_min_dict[player]["off"] != -1
                else self.end_of_game + 4
            )
            player_timeline[player_on:player_off] = player_elo
            timelines.append(player_timeline)

        self.game_timeline = pd.DataFrame(
            timelines,
            columns=["id", "team_id", "gd", *np.arange(self.end_of_game + 1).astype(str)],
        )

        characters_df = pd.DataFrame(
            characters,
            columns=["id", "name", "starter", "minutes", "team_name"],
        )

        self.game_timeline = self.game_timeline.merge(characters_df, on="id", how='left')

    def get_timeline(self):
        return self.game_timeline
    
    def _calc_game_end(self, events):
        event_end = events.loc[(events["type"] == "End")]
        end_of_game = event_end[
            (event_end["period"] == "SecondHalf") & (event_end["team_id"] == events["team_id"].values[0])
        ]["expanded_minute"].values[0]
        return end_of_game


    def _get_player_minutes_dict(self, loader_players_df, events):
        loader_players_df = loader_players_df[loader_players_df["is_starter"] == True]
        players = np.swapaxes(
            [
                loader_players_df["player_id"].values,
                loader_players_df["team_id"].values,
                [0 for _ in range(len(loader_players_df["player_id"].values))],
                [-1 for _ in range(len(loader_players_df["player_id"].values))],
            ],
            0,
            1,
        )
        sub_dataframe = events.loc[
            (events["type"] == "SubstitutionOn") | (events["type"] == "SubstitutionOff")
        ]
        on_dataframe = sub_dataframe.loc[(sub_dataframe["type"] == "SubstitutionOn")].copy()
        # on_dataframe["time_in_seconds"] = (on_dataframe["minute"] * 60) + on_dataframe["second"]
        on_players = np.swapaxes(
            [
                on_dataframe["player_id"].values.astype(int),
                on_dataframe["team_id"].values,
                on_dataframe["expanded_minute"].values,
                [-1 for _ in range(len(on_dataframe["player_id"].values))],
            ],
            0,
            1,
        )
        players_dict = {}
        for starter in [*players, *on_players]:
            if starter[0] == 0:
                continue
            players_dict[starter[0]] = {}
            players_dict[starter[0]]["team_id"] = starter[1]
            players_dict[starter[0]]["on"] = starter[2]
            players_dict[starter[0]]["off"] = starter[3]

        off_dataframe = sub_dataframe.loc[
            (sub_dataframe["type"] == "SubstitutionOff")
        ].copy()
        # off_dataframe["time_in_seconds"] = (off_dataframe["minute"] * 60) + off_dataframe["second"]
        off_players = np.swapaxes(
            [
                off_dataframe["player_id"].values.astype(int),
                off_dataframe["expanded_minute"].values,
            ],
            0,
            1,
        )
        for sub_off in off_players:
            if sub_off[0] == 0: # sometimes players dont exist?
                continue
            players_dict[sub_off[0]]["off"] = sub_off[1]

        return players_dict


    def _get_goal_dict(self, event_dataframe):
        event_dataframe = event_dataframe[event_dataframe["type"] == "Goal"]
        goal_dict = {
            "time": event_dataframe["expanded_minute"].values,
            "team": event_dataframe["team_id"].values,
        }
        return goal_dict


    def _get_goals_per_player(self, goal_dict, player_dict, end_of_game):
        player_goal = {}
        for player_id in player_dict:
            minutes = (
                end_of_game
                if (
                    (player_dict[player_id]["off"] == -1)
                    and (player_dict[player_id]["on"] == 0)
                )
                else (int(end_of_game - (player_dict[player_id]["on"])))
                if (player_dict[player_id]["off"] == -1)
                and (player_dict[player_id]["on"] != 0)
                else (int((player_dict[player_id]["off"] - player_dict[player_id]["on"])))
            )
            player_goal[player_id] = {
                "team_id": player_dict[player_id]["team_id"],
                "for": 0,
                "against": 0,
                "minutes": minutes,
            }
            index_on = next(
                (x[0]
                for x in enumerate(goal_dict["time"])
                if x[1] > player_dict[player_id]["on"]), len(goal_dict["time"])
            )
            index_off = (
                len(goal_dict["time"])
                if (player_dict[player_id]["off"] == -1)
                else next(
                    (x[0]
                    for x in enumerate(goal_dict["time"])
                    if x[1] > player_dict[player_id]["off"])
                , len(goal_dict["time"]))
            )
            for index in range(index_on, index_off):
                if goal_dict["team"][index] == player_goal[player_id]["team_id"]:
                    player_goal[player_id]["for"] += 1
                else:
                    player_goal[player_id]["against"] += 1

        return player_goal

    def get_teamname(self, player_id):
        player_df = self.loader_players_df[self.loader_players_df["player_id"] == player_id]
        player_team_id = player_df.team_id.values[0]
        player_team_name = self.df_teams[self.df_teams["team_id"]== player_team_id]["team_name"].values[0]
        return player_team_name