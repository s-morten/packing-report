from database_io.faks.player import DB_player
from database_io.dims.player_age import DB_player_age
from database_io.faks.team import DB_team
from database_io.dims.elo import DB_elo
from database_io.dims.games import DB_games
from database_io.webpage import DB_webpage
from database_io.faks.squads import DB_squads
from database_io.faks.schedule import DB_schedule
from database_io.db_handler_abs import DB_handler_connection
from database_io.faks.predictions import DB_predictions

class DB_handler():
    def __init__(self):
        connection = DB_handler_connection()
        self.player = DB_player(connection)
        self.player_age = DB_player_age(connection)
        self.team = DB_team(connection)
        self.elo = DB_elo(connection)
        self.games = DB_games(connection)
        self.webpage = DB_webpage(connection)
        self.squads = DB_squads(connection)
        self.schedule = DB_schedule(connection)
        self.predictions = DB_predictions(connection)