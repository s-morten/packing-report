from gde.database_io.db_handler import DB_handler
from datetime import datetime
from sqlalchemy import func
from gde.database_io.dims import Games
from gde.database_io.faks import Player

class DB_player():
    def __init__(self, session):
        self.session = session

    def insert_player(self, id: int, name: str, birthday: datetime):
        birthday = datetime.strptime(birthday, "%d-%m-%y").strftime("%Y-%m-%d")
        player = Player(name=str(name), id=int(id), birthday=birthday)
        # print(player)
        self.session.add(player)
        self.session.commit()

    def player_exists(self, id: int) -> bool:
        query_result = self.session.query(Player).filter(Player.id == id).first()
        return not (query_result is None)