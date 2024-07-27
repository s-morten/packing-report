from database_io.db_handler_abs import DB_handler_abs
from database_io.faks import Squads, Team

class DB_squads(DB_handler_abs):
    def insert_player(self, player_id: int, kit_number: int, team_id: int, date: str):
        # insert a player that has been never seen before
        self._number_in_use(team_id, kit_number, date)
        squad_player = Squads(player_id=player_id, kit_number=int(kit_number), team_id=team_id, valid_from="1900-01-01", valid_to="2099-12-31")
        self.session.add(squad_player)
        self.session.commit()

    def update_player(self, player_id: int, kit_number: int, team_id: int, update_date: str):
        # alter old entry
        # TODO same date for valid_from and valid_to
        self._number_in_use(team_id, kit_number, update_date)
        self.session.query(Squads).filter(Squads.player_id == player_id).filter(Squads.valid_to=="2099-12-31").update({"valid_to": update_date})
        squad_player = Squads(player_id=player_id, kit_number=int(kit_number), team_id=team_id, valid_from=update_date, valid_to="2099-12-31")
        self.session.add(squad_player)
        self.session.commit()
    def entry_exists(self, player_id: int, kit_number: int, team_id: int):
        return (self.session.query(Squads).filter(Squads.player_id == player_id).filter(Squads.kit_number == int(kit_number))
                   .filter(Squads.team_id == team_id).filter(Squads.valid_to=="2099-12-31").first()) is not None

    def player_exists(self, player_id: int):
        return self.session.query(Squads).filter(Squads.player_id == player_id).first() is not None
    
    def _number_in_use(self, team_id: int, kit_number: int, date: str):
        # if an entry exists, alter valid to date
        (self.session.query(Squads).filter(Squads.team_id == team_id).filter(Squads.kit_number == int(kit_number))
            .filter(Squads.valid_from <= date).filter(Squads.valid_to >= date)).update({"valid_to": date})
        self.session.commit()

    def match_players(self, date: str, kit_number: int, team_name: str):
        # team_id by name
        team_id = self.session.query(Team.id).filter(Team.name == team_name).first()[0]
        wh_player_id = self.session.query(Squads.player_id).filter(Squads.team_id == team_id).filter(Squads.kit_number == int(kit_number)).filter(Squads.valid_from <= date).filter(Squads.valid_to >= date).first()[0]
        return wh_player_id