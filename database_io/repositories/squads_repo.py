from datetime import datetime

from sqlalchemy import between, select

from database_io.models import Team
from database_io.models.legacy import Squads


class DB_squads:
    def insert_player(self, session, player_id: int, kit_number: int, team_id: int, date: datetime):
        self._number_in_use(session, team_id, kit_number, date)
        squad_player = Squads(
            player_id=player_id,
            kit_number=int(kit_number),
            team_id=team_id,
            valid_from=datetime.strptime("1900-01-01", "%Y-%m-%d"),
            valid_to=datetime.strptime("2099-12-31", "%Y-%m-%d"),
        )
        session.add(squad_player)
        session.commit()

    def update_player(self, session, player_id: int, kit_number: int, team_id: int, update_date: datetime):
        self._number_in_use(session, team_id, kit_number, update_date)
        session.query(Squads).filter(
            Squads.player_id == player_id,
            Squads.valid_to == datetime.strptime("2099-12-31", "%Y-%m-%d"),
        ).update({"valid_to": update_date})
        squad_player = Squads(
            player_id=player_id,
            kit_number=int(kit_number),
            team_id=team_id,
            valid_from=update_date,
            valid_to=datetime.strptime("2099-12-31", "%Y-%m-%d"),
        )
        session.add(squad_player)
        session.commit()

    def entry_exists(self, session, player_id: int, kit_number: int, team_id: int):
        return (
            session.query(Squads)
            .filter(
                Squads.player_id == player_id,
                Squads.kit_number == int(kit_number),
                Squads.team_id == team_id,
                Squads.valid_to == datetime.strptime("2099-12-31", "%Y-%m-%d"),
            )
            .first()
        ) is not None

    def player_exists(self, session, player_id: int):
        return session.query(Squads).filter(Squads.player_id == player_id).first() is not None

    def _number_in_use(self, session, team_id: int, kit_number: int, date: datetime):
        session.query(Squads).filter(
            Squads.team_id == team_id,
            Squads.kit_number == int(kit_number),
            Squads.valid_from <= date,
            Squads.valid_to >= date,
        ).update({"valid_to": date})
        session.commit()

    def match_players(self, session, date: str, kit_number: int, team_name: str):
        date = datetime.strptime(date, "%Y-%m-%d")
        team_id = session.query(Team.id).filter(Team.name == team_name).first()[0]
        wh_player_id = (
            session.query(Squads.player_id)
            .filter(
                Squads.team_id == team_id,
                Squads.kit_number == int(kit_number),
                Squads.valid_from <= date,
                Squads.valid_to >= date,
            )
            .first()
        )
        return wh_player_id[0] if wh_player_id else None


def squads_query(game_date):
    return (
        select(Squads.player_id, Squads.kit_number, Squads.team_id)
        .filter(between(game_date, Squads.valid_from, Squads.valid_to))
        .subquery()
    )
