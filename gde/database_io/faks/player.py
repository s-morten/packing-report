from gde.database_io.db_handler_abs import DB_handler_abs
from datetime import datetime
from gde.database_io.faks import Player

class DB_player(DB_handler_abs):
    def insert_player(self, id: int, name: str, birthday: datetime):
        birthday = datetime.strptime(birthday, "%d-%m-%y").strftime("%Y-%m-%d")
        player = Player(name=str(name), id=int(id), birthday=birthday)
        self.session.add(player)
        self.session.commit()

    def player_exists(self, id: int) -> bool:
        query_result = self.session.query(Player).filter(Player.id == id).first()
        return not (query_result is None)