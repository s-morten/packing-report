import numpy as np
import pandas as pd
from  datetime import datetime
import soccerdata as sd
from utils.date_utils import to_season
from database_io.db_handler import DB_handler
from collections import defaultdict
from scraper.club_elo_scraper import ClubEloScraper
from metrics.low_level.goals import Goals
from metrics.low_level.minutes import Minutes

class GameTimeline:
    def __init__(self, ws : sd.WhoScored, game_id : int , game_date: datetime, league: str,  
                 db_handler: DB_handler, version: float, home: str) -> None:
        # get necessary dataframes
        self.events = ws.read_events(match_id=[game_id])
        self.loader = ws.read_events(match_id=[game_id], output_fmt='loader')
        self.loader_players_df = self.loader.players(game_id)
        self.df_teams = self.loader.teams(game_id=game_id)
        self.db_handler = db_handler
        # self.mov_regressor = mov_regressor

        self.valid_for_training = None
        self.game_date = game_date
        self.game_id = game_id
        self.game_league = league
        self.home_team_name = home
        self.version = version
        self.year = to_season(self.game_date)

        # insert new teams
        # self.player_info_df = self.db_handler.player.get_overall_info(list(map(int, self.general_info_dict.keys())), 
        #                                                               self.game_date)

        # get player info. 
        self.player_info_df = self.db_handler.player.get_basic_info(list(map(int, self.loader_players_df.player_id)), 
                                                                self.game_date)
        for team_id, team_name in self.df_teams[["team_id", "team_name"]].values:
            if not self.db_handler.team.team_exists(int(team_id)):  
                self.db_handler.team.insert_team(int(team_id), team_name)
        
        # create general info dict 
        self._create_general_info_dict()

        self._valid_for_training()
        self._handle_missing()
        self._handle_squads()
        
    def _valid_for_training(self):
        missing_df = self.player_info_df[~self.player_info_df["exists"]]
        missing_quote = missing_df.shape[0] / self.player_info_df.shape[0]
        not_enough_entries = self.player_info_df[self.player_info_df["entries"] < 5]
        not_enough_entries_quote = not_enough_entries.shape[0] / self.player_info_df.shape[0]

        if missing_quote > 0.2 or not_enough_entries_quote > 0.2:
            self.valid_for_training = 0
        else:
            self.valid_for_training = 1

    def _handle_squads(self):
        for player_id in self.general_info_dict.keys():
            kit_number = self.general_info_dict[int(player_id)]["kit_number"]
            team_id = self.general_info_dict[int(player_id)]["team_id"]
            if not (self.player_info_df.loc[(self.player_info_df["id"] == player_id) & (self.player_info_df["kit_number"] == kit_number) & (self.player_info_df["team_id"] == team_id)]).empty:
                row = self.player_info_df.loc[self.player_info_df["id"] == player_id]
                if not row["kit_number"].isna().values[0]:
                # if (self.player_info_df.loc[self.player_info_df["id"] == player_id, "kit_number"]):
                    self.db_handler.squads.update_player(int(player_id), self.general_info_dict[int(player_id)]["kit_number"], int(team_id), self.game_date)
                else:
                    self.db_handler.squads.insert_player(int(player_id), self.general_info_dict[int(player_id)]["kit_number"], int(team_id), self.game_date)

    def _handle_missing(self):
        missing_df = self.player_info_df[~self.player_info_df["exists"]]
        for player_id in missing_df[["id"]].values:
            # get age
            birthday = self.db_handler.player_age.get_player_age(self.general_info_dict[int(player_id)]["team_name"], 
                                                                 self.general_info_dict[int(player_id)]["kit_number"], 
                                                                 self.year)
            # insert to db
            self.db_handler.player.insert_player(int(player_id), 
                                                    self.general_info_dict[int(player_id)]["player_name"], 
                                                    birthday)
        
        missing_bd_df = self.player_info_df.loc[self.player_info_df["birthday"].isna() & self.player_info_df["exists"]]
        for player_id in missing_bd_df[["id"]].values:
            birthday = self.db_handler.player_age.get_player_age(self.general_info_dict[int(player_id)]["team_name"], 
                                                                 self.general_info_dict[int(player_id)]["kit_number"], 
                                                                 self.year)
            if birthday is not None:
                self.db_handler.player.update_player_bday(int(player_id), birthday)

    def _create_general_info_dict(self):
        """ dict of player_id: team_id, team_name, home, player_name, starter, kit_number"""
        # {player_id: team_id, team_name, player_name, starter}
        general_info_dict = {}
        players = list(self.loader_players_df.player_id)
        for player in players:
            player_df = self.loader_players_df[self.loader_players_df["player_id"] == player]
            if player_df.shape[0] == 0: # sometimes whoscored messes up and player does not exist, shouldnt happen to often
                # del self.player_goal_minute_mapping[player]
                self.loader_players_df = self.loader_players_df[self.loader_players_df["player_id"] != player]
                print("player not found")
                continue
            general_info_dict[player] = {}
            general_info_dict[player]["team_id"] = player_df.team_id.values[0]
            general_info_dict[player]["team_name"] = self.df_teams[self.df_teams["team_id"] == general_info_dict[player]["team_id"]]["team_name"].values[0]
            general_info_dict[player]["home"] = 1 if self.home_team_name == general_info_dict[player]["team_name"] else 0
            general_info_dict[player]["player_name"] = player_df.player_name.values[0]
            general_info_dict[player]["starter"] = player_df.is_starter.values[0]
            general_info_dict[player]["kit_number"] = player_df.jersey_number.values[0]
        self.general_info_dict = general_info_dict


    def handle(self):
        # games_batch = []
        # for player_id in self.general_info_dict:
        #     player_name = self.general_info_dict[player_id]["player_name"]
        #     team_id = self.general_info_dict[player_id]["team_id"]
        #     team_name = self.general_info_dict[player_id]["team_name"]
        #     opposition_team_id = self.df_teams[self.df_teams["team_id"] != team_id].team_id.values[0]
        #     minutes = self.player_goal_minute_mapping[int(player_id)]["minutes"]
        #     starter = self.general_info_dict[int(player_id)]["starter"]
        #     player_on = self.player_goal_minute_mapping[int(player_id)]["on"]
        #     player_off = self.player_goal_minute_mapping[int(player_id)]["off"]
        #     home = self.general_info_dict[int(player_id)]["home"]
        #     p_mov = self.player_goal_minute_mapping[player_id]["goals_for"] - self.player_goal_minute_mapping[player_id]["goals_against"]
        #     minutes_3_mon = self.player_info_df[self.player_info_df["id"] == player_id]["total_minutes"].values[0]

        #     # add new game
        #     result = f"{self.player_goal_minute_mapping[int(player_id)]['goals_for']}-{self.player_goal_minute_mapping[int(player_id)]['goals_against']}"
        #     games_batch.append([self.game_id, player_id, minutes, starter, opposition_team_id, result, p_elo, opp_elo, self.game_date, team_id, 
        #                         exp_res_lower, exp_res_upper, self.game_league, self.version, self.general_info_dict[int(player_id)]["home"], 
        #                         self.end_of_game, self.valid_for_training])

        # # TODO can remove list(set()) when double ids are taken care off
        # elo_batch = list(set([(int(p_id), int(self.game_id), self.game_date, updated_elo, self.version, "elo") for p_id, updated_elo in self.player_info_df[["id", "updated_elo"]].values]))
        # pm_batch = list(set([(int(p_id), int(self.game_id), self.game_date, updated_pm, self.version, "pm") for p_id, updated_pm in self.player_info_df[["id", "updated_pm"]].values]))
        # self.db_handler.metric.insert_batch_metric(elo_batch)
        # self.db_handler.metric.insert_batch_metric(pm_batch)
        # self.db_handler.games.insert_games_batch(games_batch)
        metrics = [Minutes(self.db_handler), Goals(self.db_handler)]
        for metric in metrics:
            metric.calculate(self)
            metric.write(self.game_id)

    
    
    

    
    
    # def predict(self):
    #     print(self.general_info_dict)
    #     general_info_df = pd.DataFrame.from_dict(self.general_info_dict)
    #     print(general_info_df)
    #     home_ids = general_info_df.loc[general_info_df["starter"] == 1 & 
    #                                           general_info_df["team_name"] == self.home_team_name, 
    #                                           "player_id"]
    #     home_elo = self.player_info_df.loc[self.player_info_df["id"].isin(home_ids), "elo"].mean()
    #     away_ids = general_info_df.loc[general_info_df["starter"] == 1 & 
    #                                            general_info_df["team_name"] != self.home_team_name, 
    #                                           "player_id"]
    #     away_elo = self.player_info_df.loc[self.player_info_df["id"].isin(away_ids), "elo"].mean()
    #     # predict using model
    #     # TODO using MOV regressor, just for eval right now, better model needed for prediction
    #     prediction_low, prediction_high = self.mov_regressor.predict(1, home_elo - away_elo, 0, elo_diff_faktor=352, goal_diff_faktor=8, minutes_faktor=101)
    #     # write to db
    #     goals_df = get_score(self.events, self.df_teams)
    #     home_goals = goals_df.loc[self.goals_df["team_id"] == self.df_teams["team_name" == self.home_team_name, "team_id"]].count()
    #     away_goals = goals_df.loc[self.goals_df["team_id"] == self.df_teams["team_name" != self.home_team_name, "team_id"]].count()
    #     self.db_handler.predictions(self.game_id, home_elo, away_elo, prediction_low, prediction_high, 
    #           f"{home_goals}-{away_goals}")