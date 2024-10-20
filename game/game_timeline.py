import numpy as np
import pandas as pd
from  datetime import datetime
import soccerdata as sd
from utils.date_utils import to_season
from utils.football_data_utils import get_score
from database_io.db_handler import DB_handler
import metrics.elo as elo

class GameTimeline:
    def __init__(self, ws : sd.WhoScored, game_id : int , game_date: datetime, league: str,  db_handler: DB_handler, version: float, home: str) -> None:
        # get necessary dataframes
        self.events = ws.read_events(match_id=[game_id])
        self.loader = ws.read_events(match_id=[game_id], output_fmt='loader')
        self.loader_players_df = self.loader.players(game_id)
        self.df_teams = self.loader.teams(game_id=game_id)
        self.db_handler = db_handler

        self.game_date = game_date
        self.game_id = game_id
        self.game_league = league
        self.home_team_name = home
        self.version = version

        # create game timeline dict
        self._create_player_goal_minute_mapping()
        
        # create general info dict 
        self._create_general_info_dict()

        self._create_timeline_df()
        self._create_timeline_dict()

        # TODO load all players from database, to reduce requests, all Database get/exists calls

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

    def _create_timeline_df(self):
        player_timelines = []
        player_general_infos = []
        for player in self.player_goal_minute_mapping:
            # create timeline entry
            player_elo = self.db_handler.elo.get_elo(int(player), self.game_date, self.game_league, self.general_info_dict[int(player)]["starter"], self.version)
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
            game_timeline[self.player_goal_minute_mapping[player]["on"]:self.player_goal_minute_mapping[player]["off"] + 1] = player_elo
            player_timelines.append(game_timeline)
            player_general_infos.append(game_general_info)
        
        self.game_timeline_df = pd.DataFrame(
            player_timelines,
            columns=[*np.arange(self.end_of_game + 1).astype(str)]
            ) 
        self.game_general_info_df = pd.DataFrame(
            player_general_infos,
            columns=["id", "team_id", "gd"])
        
    def _create_timeline_dict(self):
        game_timeline_dict = {}
        teams = self.game_general_info_df["team_id"].unique()
        for team in teams:
            game_timeline_dict[team] = {}
        for minute in self.game_timeline_df:
            for team in game_timeline_dict:
                minute_df = self.game_timeline_df.loc[self.game_general_info_df["team_id"] == team, minute]
                average_elo = minute_df.mean()
                game_timeline_dict[team][minute] = average_elo

        self.game_timeline_dict = game_timeline_dict

    def handle(self):
        for player_id in self.general_info_dict:
            player_name = self.general_info_dict[player_id]["player_name"]
            team_id = self.general_info_dict[player_id]["team_id"]
            team_name = self.general_info_dict[player_id]["team_name"]
            if not self.db_handler.team.team_exists(int(team_id)):  
                self.db_handler.team.insert_team(int(team_id), team_name)
            opposition_team_id = self.df_teams[self.df_teams["team_id"] != team_id].team_id.values[0]
            minutes = self.player_goal_minute_mapping[int(player_id)]["minutes"]
            starter = self.general_info_dict[int(player_id)]["starter"]
            player_on = self.player_goal_minute_mapping[int(player_id)]["on"]
            player_off = self.player_goal_minute_mapping[int(player_id)]["off"]
            year = to_season(self.game_date)
            if not self.db_handler.squads.entry_exists(int(player_id), self.general_info_dict[int(player_id)]["kit_number"], int(team_id)):
                if self.db_handler.squads.player_exists(int(player_id)):
                    self.db_handler.squads.update_player(int(player_id), self.general_info_dict[int(player_id)]["kit_number"], int(team_id), self.game_date)
                else:
                    self.db_handler.squads.insert_player(int(player_id), self.general_info_dict[int(player_id)]["kit_number"], int(team_id), self.game_date)

            if not self.db_handler.player.player_exists(int(player_id)): 
                # get age
                birthday = self.db_handler.player_age.get_player_age(team_name, self.general_info_dict[int(player_id)]["kit_number"], year)
                # insert to db
                self.db_handler.player.insert_player(int(player_id), player_name, birthday)
            # if player has no bday, look again
            if self.db_handler.player.player_has_no_bday(int(player_id)):
                birthday = self.db_handler.player_age.get_player_age(team_name, self.general_info_dict[int(player_id)]["kit_number"], year)
                if birthday is not None:
                    self.db_handler.player.update_player_bday(int(player_id), birthday)

            # update elo, elo calc
            p_mov = self.player_goal_minute_mapping[player_id]["goals_for"] - self.player_goal_minute_mapping[player_id]["goals_against"]
            p_team_elo = np.mean([self.game_timeline_dict[team_id][str(minute)] for minute in range(player_on, player_off + 1)])
            opp_elo = np.mean([self.game_timeline_dict[opposition_team_id][str(minute)] for minute in range(player_on, player_off + 1)])
            p_elo = self.db_handler.elo.get_elo(int(player_id), self.game_date, self.game_league, starter, self.version)
            updated_elo, expected_game_result, roundend_expected_game_result = elo.calc_elo_update(p_mov, p_elo, p_team_elo, opp_elo, minutes, self.db_handler, self.version)
            # add updated elo
            self.db_handler.elo.insert_elo(int(player_id), int(self.game_id), self.game_date, updated_elo, self.version)
            # add new game

            result = f"{self.player_goal_minute_mapping[int(player_id)]['goals_for']}-{self.player_goal_minute_mapping[int(player_id)]['goals_against']}"
            self.db_handler.games.insert_game(self.game_id, player_id, minutes, starter, opposition_team_id, result, p_elo, opp_elo, self.game_date, team_id, 
                                              expected_game_result, roundend_expected_game_result, self.game_league, self.version, self.general_info_dict[int(player_id)]["home"])

        # TODO add to database in one go, not one by one to improve performance