import os
from pathlib import PosixPath
import soccerdata as sd
import pandas as pd
from proto_dir.python.player_proto import PlayerProto, Game
from datetime import datetime
from unidecode import unidecode
import numpy as np

from gde_utils import to_season

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from game_timeline import GameTimeline

class Player():
    def __init__(self, dbh, player_id, player_name, team_id, team_name, kit_number, game_date : datetime, proto_file_path = "/home/morten/Develop/packing-report/Goal-Difference-Elo-GDE/proto_db"):
        # check if data exists, true -> open, false -> create
        self.player_id = player_id
        self.proto_file_path = proto_file_path
        if os.path.exists(f"{proto_file_path}/{player_id}.pdata"):
            self._open_player_proto(proto_file_path, player_id)
        else:
            self.player_proto = PlayerProto()
            self.player_proto.player_id = player_id
            self.player_proto.player_name = player_name
            season = to_season(game_date)
            self.player_proto.born = self._get_birthday(dbh, team_name, kit_number, season)
            self._write_player_proto(self.proto_file_path, self.player_id)

    def _get_birthday(self, dbh, team_name, kit_number, year):
        print(year)
        player_birthday = dbh.get_player_age(team_name, kit_number, year)
        return datetime.strptime(datetime.now().strftime('%Y-%m-%d'), "%Y-%m-%d")
    
    def _find_player(self, player_name, team_name, year, player_births, only_surname=False):
        player_name = unidecode(player_name)
        player_births = player_births[player_births["Year"] == year]
        sub_df = player_births[(player_births["Club"] == team_name) | (player_births["Club2"] == team_name) | (player_births["Club3"] == team_name)].copy()
        sub_df["Name"] = sub_df.Name.apply(unidecode)
        player_name_parts = player_name.split(" ")
        part_in_name_df = sub_df.copy()
        if only_surname:
            part_in_name_df = part_in_name_df[part_in_name_df["Name"].str.contains(player_name_parts[-1])]
        else:
            for part in player_name_parts:
                part_in_name_df = part_in_name_df[part_in_name_df["Name"].str.contains(part)]
        if len(part_in_name_df) == 1:
            return True, part_in_name_df.Name.values[0], part_in_name_df.Birthday.values[0]
        else:
            return False, None, None

    def _open_player_proto(self, proto_file_path, player_id):
        self.player_proto = PlayerProto().parse(
                open(f"{proto_file_path}/{player_id}.pdata", "rb").read()
            )

    def _write_player_proto(self, proto_file_path, player_id):
        with open(f"{proto_file_path}/{str(player_id)}.pdata", "wb") as f:
                f.write(bytes(self.player_proto))

    def add_game(self, game_timeline : "GameTimeline"):  
        proto_game = Game()
        proto_game.game_id = float(game_timeline.game_id)
        proto_game.game_date = game_timeline.game_date
        proto_game.starter = bool(game_timeline.general_info_dict[self.player_id]["starter"])
        proto_game.team_id = int(game_timeline.general_info_dict[self.player_id]["team_id"])
        proto_game.team_name = str(game_timeline.general_info_dict[self.player_id]["team_name"])
        proto_game.home = True # TODO!
        proto_game.minutes_played = int(game_timeline.player_goal_minute_mapping[self.player_id]["minutes"])
        k = self._k(game_timeline.game_date, game_timeline.player_goal_minute_mapping[self.player_id]["minutes"])
        player_elo, opp_elo = self._update_player_elo(game_timeline, k)
        proto_game.elo = float(player_elo)
        proto_game.k = float(k)
        proto_game.opp_average_elo = float(opp_elo)
        proto_game.goal_difference = int(game_timeline.player_goal_minute_mapping[self.player_id]["goals_for"] -
                                        game_timeline.player_goal_minute_mapping[self.player_id]["goals_against"])

        self.player_proto.game.append(proto_game)

        self._write_player_proto(self.proto_file_path, self.player_id)

    def _k(self, game_date, minutes):
        # age
        player_birthday = self.player_proto.born
        age_delta = game_date - player_birthday
        age = age_delta.days / 365 # does not work for leap years
        if age < 20:
            k_age = 50
        elif age < 23:
            k_age = 25
        elif age < 31:
            k_age = 0
        else:
            k_age = 10
        # minutes in game
        k_min = np.clip(minutes / 2, 0, 50)
        # std of old games
        player_games = self.get_games_by_number(10)
        game_ratings = []
        for game in player_games:
            game_ratings.append(game.elo)
        if game_ratings:
            k_std = np.clip(np.std(game_ratings), 0, 50)
        else:
            k_std = 50
        return (k_age + k_min + k_std) / 5
    
    def _calculate_updated_elo(self, elo_opposition, result, k, game_date):
        # results from the 'eye' of the elo player, 0=loss, 0.5=draw, 1=win
        elo_player = self.get_elo(game_date)
        strength_player = pow(10, (elo_player / 200))
        strength_opposition = pow(10, (elo_opposition / 200))
        expected_results_player = strength_player / (strength_player + strength_opposition)
        updated_elo_player = elo_player + k * (result - expected_results_player)
        return updated_elo_player
    
    # for player in timeline.id:
    def _update_player_elo(self, timeline : "GameTimeline", k):
        goal_diff = (timeline.player_goal_minute_mapping[self.player_id]["goals_for"] - 
                     timeline.player_goal_minute_mapping[self.player_id]["goals_against"]) 
        result = goal_diff + 0.5
        result = np.clip(result, 0, 1)

        min_on = timeline.player_goal_minute_mapping[self.player_id]["on"]
        min_off = timeline.player_goal_minute_mapping[self.player_id]["off"]
        elo_opposition = []
        for team_id in timeline.game_timeline_dict:
            if team_id != timeline.player_goal_minute_mapping[self.player_id]["team_id"]:
                opposition_team_id = team_id
        for minute in range(min_on, min_off):
            elo_opposition.append(timeline.game_timeline_dict[opposition_team_id][str(minute)])
        elo_opposition = np.mean(elo_opposition)
        updated_player_elo = self._calculate_updated_elo(
            elo_opposition, result, k, timeline.game_date
        )

        return updated_player_elo, elo_opposition

    def get_elo(self, game_date):
        elo_starting_value = 250
        if not self.player_proto.game:
            return elo_starting_value
        else:
            # TODO is this working as intended?
            for game in reversed(self.player_proto.game):
                if game.game_date < game_date:
                    return game.elo
            return elo_starting_value

    # # TODO deprecated        
    # def _elo_from_team_value(self, game_date, team_name):
    #     ce = sd.ClubElo(
    #         no_cache=False,
    #         no_store=False,
    #         data_dir=PosixPath("/home/morten/Develop/Open-Data/soccerdata"),
    #     )
    #     ce_df = ce.read_by_date(game_date)
    #     elo = ce_df.loc[team_name].elo
    #     return elo - 200

    def get_games_by_date(self, min_date, max_date):
        games = []
        proto_games = self.player_proto.game
        rproto_games = reversed(proto_games)
        for g in reversed(self.player_proto.game):
            if min_date <= g.game_date < max_date:
                games.append(g)
            if min_date > g.game_date:
                return games
        return games
    
    def get_games_by_number(self, number_of_games):
        return self.player_proto.game[-number_of_games:]
    

    def get_birthday(self):
        return self.player_proto.born