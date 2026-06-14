from datetime import datetime

import soccerdata as sd

from database_io.connection import get_session
from database_io.repositories.player_age_repo import DB_player_age
from database_io.repositories.player_repo import DB_player
from database_io.repositories.squads_repo import DB_squads
from database_io.repositories.team_repo import DB_team
from utils.date_utils import to_season


class GamePrepare:
    def __init__(
        self,
        ws: sd.WhoScored,
        game_id: int,
        game_date: datetime,
        league: str,
        home: str,
    ) -> None:
        loader = ws.read_events(match_id=[game_id], output_fmt="loader")
        self.loader_players_df = loader.players(game_id)
        self.df_teams = loader.teams(game_id=game_id)

        self.player = DB_player()
        self.player_age = DB_player_age()
        self.team = DB_team()
        self.squads = DB_squads()

        self.valid_for_training = None
        self.game_date = game_date
        self.game_id = game_id
        self.game_league = league
        self.home_team_name = home
        self.year = to_season(self.game_date)

    def sync(self):
        with get_session() as session:
            self.player_info_df = self.player.get_basic_info(
                session,
                list(map(int, self.loader_players_df.player_id)),
                self.game_date,
            )
            for team_id, team_name in self.df_teams[["team_id", "team_name"]].values:
                if not self.team.team_exists(session, int(team_id)):
                    self.team.insert_team(session, int(team_id), team_name)

            self._create_general_info_dict()
            self._valid_for_training()
            self._handle_missing(session)
            self._handle_squads(session)

    def _valid_for_training(self):
        missing_df = self.player_info_df[~self.player_info_df["exists"]]
        missing_quote = missing_df.shape[0] / self.player_info_df.shape[0]
        not_enough_entries = self.player_info_df[self.player_info_df["entries"] < 5]
        not_enough_entries_quote = not_enough_entries.shape[0] / self.player_info_df.shape[0]

        if missing_quote > 0.2 or not_enough_entries_quote > 0.2:
            self.valid_for_training = 0
        else:
            self.valid_for_training = 1

    def _handle_squads(self, session):
        for player_id in self.general_info_dict:
            kit_number = self.general_info_dict[int(player_id)]["kit_number"]
            team_id = self.general_info_dict[int(player_id)]["team_id"]
            if not (
                self.player_info_df.loc[
                    (self.player_info_df["id"] == player_id)
                    & (self.player_info_df["kit_number"] == kit_number)
                    & (self.player_info_df["team_id"] == team_id)
                ]
            ).empty:
                row = self.player_info_df.loc[self.player_info_df["id"] == player_id]
                if not row["kit_number"].isna().values[0]:
                    self.squads.update_player(
                        session,
                        int(player_id),
                        self.general_info_dict[int(player_id)]["kit_number"],
                        int(team_id),
                        self.game_date,
                    )
                else:
                    self.squads.insert_player(
                        session,
                        int(player_id),
                        self.general_info_dict[int(player_id)]["kit_number"],
                        int(team_id),
                        self.game_date,
                    )

    def _handle_missing(self, session):
        missing_df = self.player_info_df[~self.player_info_df["exists"]]
        for player_id in missing_df[["id"]].values:
            birthday = self.player_age.get_player_age(
                session,
                self.general_info_dict[int(player_id)]["team_name"],
                self.general_info_dict[int(player_id)]["kit_number"],
                self.year,
            )
            self.player.insert_player(
                session,
                int(player_id),
                self.general_info_dict[int(player_id)]["player_name"],
                birthday,
            )

        missing_bd_df = self.player_info_df.loc[self.player_info_df["birthday"].isna() & self.player_info_df["exists"]]
        for player_id in missing_bd_df[["id"]].values:
            birthday = self.player_age.get_player_age(
                session,
                self.general_info_dict[int(player_id)]["team_name"],
                self.general_info_dict[int(player_id)]["kit_number"],
                self.year,
            )
            if birthday is not None:
                self.player.update_player_bday(session, int(player_id), birthday)

    def _create_general_info_dict(self):
        general_info_dict = {}
        players = list(self.loader_players_df.player_id)
        for player in players:
            player_df = self.loader_players_df[self.loader_players_df["player_id"] == player]
            if player_df.shape[0] == 0:
                self.loader_players_df = self.loader_players_df[self.loader_players_df["player_id"] != player]
                print("player not found")
                continue
            general_info_dict[player] = {}
            general_info_dict[player]["team_id"] = player_df.team_id.values[0]
            general_info_dict[player]["team_name"] = self.df_teams[
                self.df_teams["team_id"] == general_info_dict[player]["team_id"]
            ]["team_name"].values[0]
            general_info_dict[player]["home"] = (
                1 if self.home_team_name == general_info_dict[player]["team_name"] else 0
            )
            general_info_dict[player]["player_name"] = player_df.player_name.values[0]
            general_info_dict[player]["starter"] = player_df.is_starter.values[0]
            general_info_dict[player]["kit_number"] = player_df.jersey_number.values[0]
        self.general_info_dict = general_info_dict
