# from database_io.db_handler_abs import DB_handler_abs
from database_io.faks import Team

class DB_team():
    def __init__(self, connection_item):
        self.connection = connection_item.connection
        self.session = connection_item.session
        self.engine = connection_item.engine
    def insert_team(self, id: int, name: str):
        team = Team(name=str(name), id=int(id))
        self.session.add(team)
        self.session.commit()

    def team_exists(self, id: int) -> bool:
        query_result = self.session.query(Team).filter(Team.id == id).first()
        return not (query_result is None)