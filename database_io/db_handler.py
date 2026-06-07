from database_io.connection import get_session
from database_io.repositories.game_repo import DB_games
from database_io.repositories.metric_repo import DB_metric
from database_io.repositories.player_age_repo import DB_player_age
from database_io.repositories.player_repo import DB_player
from database_io.repositories.predictions_repo import DB_predictions
from database_io.repositories.schedule_repo import DB_schedule
from database_io.repositories.squads_repo import DB_squads
from database_io.repositories.team_repo import DB_team


class DB_handler:
    """Thin wrapper for callers that haven't migrated to session-in-method pattern yet.

    Creates a session and delegates repo calls through the session.
    Usage:
        dbh = DB_handler()
        with dbh.session() as s:
            dbh.player.insert_player(s, 1, "name", "01-01-90")
    """

    def __init__(self):
        self.player = DB_player()
        self.player_age = DB_player_age()
        self.team = DB_team()
        self.metric = DB_metric()
        self.games = DB_games()
        self.squads = DB_squads()
        self.schedule = DB_schedule()
        self.predictions = DB_predictions()

    def session(self):
        return get_session()
