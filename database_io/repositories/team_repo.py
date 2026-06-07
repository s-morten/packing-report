from database_io.models import Team


class DB_team:
    def insert_team(self, session, id: int, name: str):
        team = Team(name=str(name), id=int(id))
        session.add(team)
        session.commit()

    def team_exists(self, session, id: int) -> bool:
        return session.query(Team).filter(Team.id == id).first() is not None
