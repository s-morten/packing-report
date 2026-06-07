import soccerdata as sd
from metrics.low_level.goals import Goals
from metrics.low_level.minutes import Minutes

from database_io.repositories.metric_repo import DB_metric


class GameFacts:
    def __init__(self, ws: sd.WhoScored, game_id: int) -> None:
        self.events = ws.read_events(match_id=[game_id])
        loader = ws.read_events(match_id=[game_id], output_fmt="loader")
        self.loader_players_df = loader.players(game_id)
        self.df_teams = loader.teams(game_id=game_id)
        self.game_id = game_id
        self.metric = DB_metric()
        self.players_dict = {}
        self.end_of_game = None

    def handle(self, session):
        minutes = Minutes(self.metric)
        minutes.calculate(self)
        minutes.write(session, self.game_id)

        goals = Goals(self.metric)
        goals.calculate(self)
        goals.write(session, self.game_id)
