import numpy as np
import pandas as pd
from utils.football_data_utils import get_score
class Goals:
    def __init__(self, db_handler):
        self.db_handler = db_handler

    def create_player_goal_minute_mapping(self, events, loader_players_df, df_teams):
        """ dict of player_id: {team_id, goals_for, goals_against, minutes, on, off}"""
        # player and minutes, including subs
        loader_players_df = loader_players_df[loader_players_df["is_starter"] == True]
        players = np.swapaxes(
            [
                loader_players_df["player_id"].values, # player
                loader_players_df["team_id"].values, # team
                [0 for _ in range(len(loader_players_df["player_id"].values))], # on
                [-1 for _ in range(len(loader_players_df["player_id"].values))], # off
            ],
            0,
            1,
        )
        sub_dataframe = events.loc[(events["type"] == "SubstitutionOn") | (events["type"] == "SubstitutionOff")]
        on_dataframe = sub_dataframe.loc[(sub_dataframe["type"] == "SubstitutionOn")].copy()
        off_dataframe = sub_dataframe.loc[(sub_dataframe["type"] == "SubstitutionOff")].copy()

        subbed_on_players = np.swapaxes(
            [
                on_dataframe["player_id"].values.astype(int), # player
                on_dataframe["team_id"].values, # team
                on_dataframe["expanded_minute"].values, # on
                [-1 for _ in range(len(on_dataframe["player_id"].values))], # off
            ],
            0,
            1,
        )
        subbed_off_players = np.swapaxes(
            [
                off_dataframe["player_id"].values.astype(int), # player
                off_dataframe["team_id"].values, # team
                [0 for _ in range(len(off_dataframe["player_id"].values))], # on
                off_dataframe["expanded_minute"].values, # off
            ],
            0,
            1,
        )
        # TODO dafault dict?
        players_dict = {}
        for player in [*players, *subbed_on_players, *subbed_off_players]:
            if player[0] == 0: # player does not exist in date, bug!
                continue
            if player[0] not in players_dict:
                players_dict[player[0]] = {}
                players_dict[player[0]]["team_id"] = player[1]
                players_dict[player[0]]["on"] = player[2]
                players_dict[player[0]]["off"] = player[3]
            else:
                players_dict[player[0]]["on"] = max(player[2], players_dict[player[0]]["on"])
                players_dict[player[0]]["off"] = max(player[3], players_dict[player[0]]["off"])
        
        # get goals and minutes
        event_dataframe = get_score(events, df_teams)
        # goal dict {key minute: value team}
        goal_dict = dict(
            zip(event_dataframe["expanded_minute"].values,
            event_dataframe["goal_team_id"].values)
        )

        # end of game, either the last minute or a red card -> game no longer representative
        red_card_df = events[(events["type"]== "Card") & (events["card_type"].isin(["SecondYellow", "Red"]))]
        game_end_df = events.loc[(events["type"] == "End")]
        end_of_game = game_end_df[(game_end_df["period"] == "SecondHalf")]["expanded_minute"].values[0]
        official_end_of_game = end_of_game
        if not red_card_df.empty:
            red_card_game_end = min(red_card_df["expanded_minute"].values)
            end_of_game = min(end_of_game, red_card_game_end)
        self.end_of_game = end_of_game

        # set game end in dict
        player_dict_keys = list(players_dict.keys())
        for player in player_dict_keys:
            # remove players subbed on after a possible red card
            if players_dict[player]["on"] > end_of_game:
                del players_dict[player]
                continue
            # set end game of players not subbed of before
            if (players_dict[player]["off"] == -1) or (players_dict[player]["off"] > end_of_game):
                players_dict[player]["off"] = end_of_game
        # remove goals after red card incident 
        goal_dict_keys = list(goal_dict.keys())
        for goal in goal_dict_keys:
            if goal > end_of_game:
                del goal_dict[goal]

        # player_goal_minute_mapping = {team_id, goals for, goals against, minutes, on, off}
        player_goal_minute_mapping = {}
        for player in players_dict:
            player_on = players_dict[player]["on"]
            player_off = players_dict[player]["off"]
            player_team_id = players_dict[player]["team_id"]
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
                "minutes": player_off - players_dict[player]["on"], 
                "on": players_dict[player]["on"], 
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