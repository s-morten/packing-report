import numpy as np
import pandas as pd
from  datetime import datetime
import soccerdata as sd
from utils.date_utils import to_season
from utils.football_data_utils import get_score
from database_io.db_handler import DB_handler
import metrics.elo as elo
from collections import defaultdict
from scraper.club_elo_scraper import ClubEloScraper
from metrics.mov_elo.regressor import MOV_Regressor
import metrics.pm as pm

class GameTimeline:
    def __init__(self, ws : sd.WhoScored, game_id : int , game_date: datetime, league: str,  db_handler: DB_handler, version: float, home: str
                 , mov_regressor: MOV_Regressor
                 ) -> None:
        # get necessary dataframes
        self.events = ws.read_events(match_id=[game_id])
        self.loader = ws.read_events(match_id=[game_id], output_fmt='loader')
        self.loader_players_df = self.loader.players(game_id)
        self.df_teams = self.loader.teams(game_id=game_id)
        self.db_handler = db_handler
        self.mov_regressor = mov_regressor
        self.metric_pm = pm.PM()
        self.metric_elo = elo.PlayerELO()

        self.valid_for_training = None
        self.game_date = game_date
        self.game_id = game_id
        self.game_league = league
        self.home_team_name = home
        self.version = version
        self.year = to_season(self.game_date)

        # create game timeline dict
        self._create_player_goal_minute_mapping()
        
        # create general info dict 
        self._create_general_info_dict()

        self.player_info_df = self.db_handler.player.get_overall_info(list(map(int, self.general_info_dict.keys())), self.game_date)
        for team_id, team_name in self.df_teams[["team_id", "team_name"]].values:
            if not self.db_handler.team.team_exists(int(team_id)):  
                self.db_handler.team.insert_team(int(team_id), team_name)
        
        self._valid_for_training()
        self._handle_missing()
        self._handle_squads()

        self.game_timeline_dfs = {}
        self.game_timeline_dicts = {}
        for metric in ["elo", "pm"]:
            self._create_timeline_df(metric)
            self._create_timeline_dict(metric)
        
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
        league_elo = None
        for player_id in missing_df[["id"]].values:
            # get age
            birthday = self.db_handler.player_age.get_player_age(self.general_info_dict[int(player_id)]["team_name"], 
                                                                    self.general_info_dict[int(player_id)]["kit_number"], 
                                                                    self.year)
            # insert to db
            self.db_handler.player.insert_player(int(player_id), 
                                                    self.general_info_dict[int(player_id)]["player_name"], 
                                                    birthday)
            
            # init ELO
            if self.db_handler.metric.get_player_count_per_league(self.game_league, self.version) < 50:
                if league_elo is None:
                    # get Elo from Club Elo, because not enough players are 
                    league_elo = ClubEloScraper().get_avg_league_elo_by_date(pd.to_datetime(self.game_date, format="%Y-%m-%d"), self.game_league)
                start_elo = league_elo if self.general_info_dict[int(player_id)]["starter"] else league_elo * 0.7
                self.player_info_df.loc[self.player_info_df["id"] == int(player_id), "elo"] = start_elo
                print("league_elo", start_elo)
            else:
                self.player_info_df.loc[self.player_info_df["id"] == int(player_id), "elo"] = np.float64(self.db_handler.metric.average_elo(self.game_league, self.general_info_dict[int(player_id)]["team_id"], self.game_date, self.version)) # * 0.7
                print("50 players", np.float64(self.db_handler.metric.average_elo(self.game_league, self.general_info_dict[int(player_id)]["team_id"], self.game_date, self.version)) * 0.7)
            # init pm
            self.player_info_df.loc[self.player_info_df["id"] == int(player_id), "pm"] = 0    
        
        missing_bd_df = self.player_info_df.loc[self.player_info_df["birthday"].isna() & self.player_info_df["exists"]]
        for player_id in missing_bd_df[["id"]].values:
            birthday = self.db_handler.player_age.get_player_age(self.general_info_dict[int(player_id)]["team_name"], 
                                                                 self.general_info_dict[int(player_id)]["kit_number"], 
                                                                 self.year)
            if birthday is not None:
                self.db_handler.player.update_player_bday(int(player_id), birthday)

    def _create_general_info_dict(self):
        # {player_id: team_id, team_name, player_name, starter}
        general_info_dict = {}
        players = list(self.player_goal_minute_mapping)
        for player in players:
            player_df = self.loader_players_df[self.loader_players_df["player_id"] == player]
            if player_df.shape[0] == 0: # sometimes whoscored messes up and player does not exist, shouldnt happen to often
                del self.player_goal_minute_mapping[player]
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

    def _create_player_goal_minute_mapping(self):
        # player and minutes, including subs
        loader_players_df = self.loader_players_df[self.loader_players_df["is_starter"] == True]
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
        sub_dataframe = self.events.loc[(self.events["type"] == "SubstitutionOn") | (self.events["type"] == "SubstitutionOff")]
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
        event_dataframe = get_score(self.events, self.df_teams)
        # goal dict {key minute: value team}
        goal_dict = dict(
            zip(event_dataframe["expanded_minute"].values,
            event_dataframe["goal_team_id"].values)
        )

        # end of game, either the last minute or a red card -> game no longer representative
        red_card_df = self.events[(self.events["type"]== "Card") & (self.events["card_type"].isin(["SecondYellow", "Red"]))]
        game_end_df = self.events.loc[(self.events["type"] == "End")]
        end_of_game = game_end_df[(game_end_df["period"] == "SecondHalf")]["expanded_minute"].values[0]
        self.official_end_of_game = end_of_game
        if not red_card_df.empty:
            red_card_game_end = min(red_card_df["expanded_minute"].values)
            end_of_game = min(end_of_game, red_card_game_end)
        self.end_of_game = end_of_game

        # set game end in dict
        player_dict_keys = list(players_dict.keys())
        for player in player_dict_keys:
            # remove players subbed on after a possible red card
            if players_dict[player]["on"] > self.end_of_game:
                del players_dict[player]
                continue
            # set end game of players not subbed of before
            if (players_dict[player]["off"] == -1) or (players_dict[player]["off"] > self.end_of_game):
                players_dict[player]["off"] = self.end_of_game
        # remove goals after red card incident 
        goal_dict_keys = list(goal_dict.keys())
        for goal in goal_dict_keys:
            if goal > self.end_of_game:
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

    def _create_timeline_df(self, metric):
        player_timelines = []
        player_general_infos = []
        for player in self.player_goal_minute_mapping:
            # create timeline entry
            player_metric = self.player_info_df[self.player_info_df["id"] == player][metric].values[0]
            game_timeline = np.empty(
                self.end_of_game + 1
            )  # +1 for index of last minute
            game_general_info = np.empty( 3 )  # player id, team id, gd
            
            game_timeline[:] = np.nan
            game_general_info[0] = player
            game_general_info[1] = self.player_goal_minute_mapping[player]["team_id"]
            game_general_info[2] = (
                self.player_goal_minute_mapping[player]["goals_for"] - self.player_goal_minute_mapping[player]["goals_against"]
            )
            game_timeline[self.player_goal_minute_mapping[player]["on"]:self.player_goal_minute_mapping[player]["off"] + 1] = player_metric
            player_timelines.append(game_timeline)
            player_general_infos.append(game_general_info)
        
        self.game_timeline_dfs[metric] = pd.DataFrame(
            player_timelines,
            columns=[*np.arange(self.end_of_game + 1).astype(str)]
            ) 
        self.game_general_info_df = pd.DataFrame(
            player_general_infos,
            columns=["id", "team_id", "gd"])
        
    def _create_timeline_dict(self, metric):
        game_timeline_dict = {}
        teams = self.game_general_info_df["team_id"].unique()
        for team in teams:
            game_timeline_dict[team] = {}
        for minute in self.game_timeline_dfs[metric]:
            for team in game_timeline_dict:
                minute_df = self.game_timeline_dfs[metric].loc[self.game_general_info_df["team_id"] == team, minute]
                average_elo = minute_df.mean()
                game_timeline_dict[team][minute] = average_elo

        self.game_timeline_dicts[metric] = game_timeline_dict

    def handle(self):
        games_batch = []
        for player_id in self.general_info_dict:
            player_name = self.general_info_dict[player_id]["player_name"]
            team_id = self.general_info_dict[player_id]["team_id"]
            team_name = self.general_info_dict[player_id]["team_name"]
            opposition_team_id = self.df_teams[self.df_teams["team_id"] != team_id].team_id.values[0]
            minutes = self.player_goal_minute_mapping[int(player_id)]["minutes"]
            starter = self.general_info_dict[int(player_id)]["starter"]
            player_on = self.player_goal_minute_mapping[int(player_id)]["on"]
            player_off = self.player_goal_minute_mapping[int(player_id)]["off"]
            home = self.general_info_dict[int(player_id)]["home"]
            p_mov = self.player_goal_minute_mapping[player_id]["goals_for"] - self.player_goal_minute_mapping[player_id]["goals_against"]
            minutes_3_mon = self.player_info_df[self.player_info_df["id"] == player_id]["total_minutes"].values[0]

            # METRIC Elo ################################
            # update elo, elo calc
            p_elo = self.player_info_df[self.player_info_df["id"] == player_id]["elo"].values[0]
            p_team_elo = np.mean([self.game_timeline_dicts["elo"][team_id][str(minute)] for minute in range(player_on, player_off + 1)])
            opp_elo = np.mean([self.game_timeline_dicts["elo"][opposition_team_id][str(minute)] for minute in range(player_on, player_off + 1)])
      
            # update elo
            exp_res_lower, exp_res_upper = self.metric_elo.predict( home, p_elo, p_team_elo, opp_elo, self.end_of_game - minutes, self.mov_regressor)
            updated_elo = self.metric_elo.update(p_mov, exp_res_lower, exp_res_upper, minutes, minutes_3_mon)
            
            self.player_info_df.loc[self.player_info_df["id"] == player_id, "updated_elo"] = updated_elo
            self.player_info_df.loc[self.player_info_df["id"] == player_id, "exp_res_lower_elo"] = exp_res_lower
            self.player_info_df.loc[self.player_info_df["id"] == player_id, "exp_res_upper_elo"] = exp_res_upper
            
            # METRIC pm ################################ 
            p_pm = self.player_info_df[self.player_info_df["id"] == player_id]["pm"].values[0]
            p_team_pm = np.mean([self.game_timeline_dicts["pm"][team_id][str(minute)] for minute in range(player_on, player_off + 1)])
            opp_pm = np.mean([self.game_timeline_dicts["pm"][opposition_team_id][str(minute)] for minute in range(player_on, player_off + 1)])
            exp_res = self.metric_pm.predict(p_pm, p_team_pm, opp_pm, minutes)
            updated_pm = self.metric_pm.update(p_pm, p_mov, exp_res)
            self.player_info_df.loc[self.player_info_df["id"] == player_id, "updated_pm"] = updated_pm
            self.player_info_df.loc[self.player_info_df["id"] == player_id, "exp_res_lpm"] = exp_res

            # add new game
            result = f"{self.player_goal_minute_mapping[int(player_id)]['goals_for']}-{self.player_goal_minute_mapping[int(player_id)]['goals_against']}"
            games_batch.append([self.game_id, player_id, minutes, starter, opposition_team_id, result, p_elo, opp_elo, self.game_date, team_id, 
                                exp_res_lower, exp_res_upper, self.game_league, self.version, self.general_info_dict[int(player_id)]["home"], 
                                self.end_of_game, self.valid_for_training])

        # TODO can remove list(set()) when double ids are taken care off
        elo_batch = list(set([(int(p_id), int(self.game_id), self.game_date, updated_elo, self.version, "elo") for p_id, updated_elo in self.player_info_df[["id", "updated_elo"]].values]))
        pm_batch = list(set([(int(p_id), int(self.game_id), self.game_date, updated_pm, self.version, "pm") for p_id, updated_pm in self.player_info_df[["id", "updated_pm"]].values]))
        self.db_handler.metric.insert_batch_metric(elo_batch)
        self.db_handler.metric.insert_batch_metric(pm_batch)
        self.db_handler.games.insert_games_batch(games_batch)

    
    
    

    
    
    def predict(self):
        print(self.general_info_dict)
        general_info_df = pd.DataFrame.from_dict(self.general_info_dict)
        print(general_info_df)
        home_ids = general_info_df.loc[general_info_df["starter"] == 1 & 
                                              general_info_df["team_name"] == self.home_team_name, 
                                              "player_id"]
        home_elo = self.player_info_df.loc[self.player_info_df["id"].isin(home_ids), "elo"].mean()
        away_ids = general_info_df.loc[general_info_df["starter"] == 1 & 
                                               general_info_df["team_name"] != self.home_team_name, 
                                              "player_id"]
        away_elo = self.player_info_df.loc[self.player_info_df["id"].isin(away_ids), "elo"].mean()
        # predict using model
        # TODO using MOV regressor, just for eval right now, better model needed for prediction
        prediction_low, prediction_high = self.mov_regressor.predict(1, home_elo - away_elo, 0, elo_diff_faktor=352, goal_diff_faktor=8, minutes_faktor=101)
        # write to db
        goals_df = get_score(self.events, self.df_teams)
        home_goals = goals_df.loc[self.goals_df["team_id"] == self.df_teams["team_name" == self.home_team_name, "team_id"]].count()
        away_goals = goals_df.loc[self.goals_df["team_id"] == self.df_teams["team_name" != self.home_team_name, "team_id"]].count()
        self.db_handler.predictions(self.game_id, home_elo, away_elo, prediction_low, prediction_high, 
              f"{home_goals}-{away_goals}")