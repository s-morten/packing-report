import numpy as np
import pandas as pd
from utils.football_data_utils import get_score
class Goals:
    def __init__(self, db_handler):
        self.db_handler = db_handler

    def calculate(self, game_timeline):
        # get goals and minutes
        event_dataframe = get_score(game_timeline.events, game_timeline.df_teams)
        # goal dict {key minute: value team}
        goal_dict = dict(
            zip(event_dataframe["expanded_minute"].values,
            event_dataframe["goal_team_id"].values)
        )

        # TODO make sure players_dict is implemented in game_timeline

        # player_goal_minute_mapping = {team_id, goals for, goals against, minutes, on, off}
        player_goal_minute_mapping = {}
        for player in game_timeline.players_dict:
            player_on = game_timeline.players_dict[player]["on"]
            player_off = game_timeline.players_dict[player]["off"]
            player_team_id = game_timeline.players_dict[player]["team_id"]
            player_goals_for = 0
            player_goals_against = 0
            for goal in goal_dict:
                if (goal > player_on) and (goal < player_off):
                    if goal_dict[goal] == player_team_id:
                        player_goals_for += 1
                    else:
                        player_goals_against += 1
            player_goal_minute_mapping[player] = {
                "team_id": player_team_id,
                "goals_for": player_goals_for,
                "goals_against": player_goals_against,
                "minutes": player_off - game_timeline.players_dict[player]["on"], 
                "on": game_timeline.players_dict[player]["on"], 
                "off": player_off
                }
        self.player_goal_minute_mapping = player_goal_minute_mapping

    def write(self, game_id):
        metric_batch = []
        for player in self.player_goal_minute_mapping:
            metric_batch.append([
                player,
                game_id,
                self.player_goal_minute_mapping[player]["goals_for"] - self.player_goal_minute_mapping[player]["goals_against"],
                "goals"])
        self.db_handler.metric.insert_batch_metric(metric_batch)

    # def _create_timeline_df(self, metric):
    #     """ dataframe. columns are minutes of the game. rows are players (not explicitly set right now TODO)
    #         metric at minute"""
    #     player_timelines = []
    #     player_general_infos = []
    #     for player in self.player_goal_minute_mapping:
    #         # create timeline entry
    #         player_metric = self.player_info_df[self.player_info_df["id"] == player][metric].values[0]
    #         game_timeline = np.empty(
    #             self.end_of_game + 1
    #         )  # +1 for index of last minute
    #         game_general_info = np.empty( 3 )  # player id, team id, gd
            
    #         game_timeline[:] = np.nan
    #         game_general_info[0] = player
    #         game_general_info[1] = self.player_goal_minute_mapping[player]["team_id"]
    #         game_general_info[2] = (
    #             self.player_goal_minute_mapping[player]["goals_for"] - self.player_goal_minute_mapping[player]["goals_against"]
    #         )
    #         game_timeline[self.player_goal_minute_mapping[player]["on"]:self.player_goal_minute_mapping[player]["off"] + 1] = player_metric
    #         player_timelines.append(game_timeline)
    #         player_general_infos.append(game_general_info)
        
    #     self.game_timeline_dfs[metric] = pd.DataFrame(
    #         player_timelines,
    #         columns=[*np.arange(self.end_of_game + 1).astype(str)]
    #         ) 
    #     self.game_general_info_df = pd.DataFrame(
    #         player_general_infos,
    #         columns=["id", "team_id", "gd"])
        
    # def _create_timeline_dict(self, metric):
    #     """ dict. team_id: minute: average metric"""
    #     game_timeline_dict = {}
    #     teams = self.game_general_info_df["team_id"].unique()
    #     for team in teams:
    #         game_timeline_dict[team] = {}
    #     for minute in self.game_timeline_dfs[metric]:
    #         for team in game_timeline_dict:
    #             minute_df = self.game_timeline_dfs[metric].loc[self.game_general_info_df["team_id"] == team, minute]
    #             average_elo = minute_df.mean()
    #             game_timeline_dict[team][minute] = average_elo

    #     self.game_timeline_dicts[metric] = game_timeline_dict