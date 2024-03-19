from gde.database_io.faks.player import DB_player
from gde.database_io.dims.player_age import DB_player_age
# from gde.database_io.db_handler_abs import DB_handler_abs

# class DB_handler(DB_handler_abs):
class DB_handler():
    def __init__(self, db_path):
        # super().__init__(db_path)
        # self.player = DB_player(db_path)
        self.player_age = DB_player_age(db_path)