from database_io.faks.player import DB_player
from database_io.dims.player_age import DB_player_age
from database_io.faks.team import DB_team
from database_io.dims.elo import DB_elo
from database_io.dims.games import DB_games
from database_io.webpage import DB_webpage
from database_io.faks.squads import DB_squads

class DB_handler():
    def __init__(self, db_path):
        self.player = DB_player(db_path)
        self.player_age = DB_player_age(db_path)
        self.team = DB_team(db_path)
        self.elo = DB_elo(db_path)
        self.games = DB_games(db_path)
        self.webpage = DB_webpage(db_path)
        self.squads = DB_squads(db_path)