from database_io.db_handler_abs import DB_handler_abs
from datetime import datetime
from database_io.faks import Player

class DB_player(DB_handler_abs):
    def insert_player(self, id: int, name: str, birthday: datetime):
        birthday = datetime.strptime(birthday, "%d-%m-%y").strftime("%Y-%m-%d") if birthday else None
        player = Player(name=str(name), id=int(id), birthday=birthday, fapi_id=None)
        self.session.add(player)
        self.session.commit()

    def player_exists(self, id: int) -> bool:
        query_result = self.session.query(Player).filter(Player.id == id).first()
        return not (query_result is None)
    
    def player_has_no_bday(self, id: int) -> bool:
        query_result = self.session.query(Player).filter(Player.id == id, Player.birthday == None).first()
        return not (query_result is None)
    
    def update_player_bday(self, id: int, birthday: datetime):
        birthday = datetime.strptime(birthday, "%d-%m-%y").strftime("%Y-%m-%d") if birthday else None
        player = self.session.query(Player).filter(Player.id == id).first()
        player.birthday = birthday
        self.session.commit()

    def update_player_fapi_id(self, id: int, fapi_id: int):
        player = self.session.query(Player).filter(Player.id == id).first()
        player.fapi_id = fapi_id
        self.session.commit()