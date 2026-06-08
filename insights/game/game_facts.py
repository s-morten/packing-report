import soccerdata as sd
from metrics.low_level.goals import Goals
from metrics.low_level.minutes import Minutes
from metrics.low_level.vaep import Vaep

from database_io.repositories.metric_repo import DB_metric


class GameFacts:
    def __init__(self, ws: sd.WhoScored, game_id: int, home_team_name: str = "") -> None:
        self.events = ws.read_events(match_id=[game_id])
        loader = ws.read_events(match_id=[game_id], output_fmt="loader")
        self.loader_players_df = loader.players(game_id)
        self.df_teams = loader.teams(game_id=game_id)
        self.game_id = game_id
        self.metric = DB_metric()
        self.players_dict = {}
        self.end_of_game = None

        self.spadl = ws.read_events(match_id=[game_id], output_fmt="spadl")

        self.home_team_id = self._resolve_home_team_id(home_team_name)

    def _resolve_home_team_id(self, home_team_name):
        if not home_team_name or self.df_teams.empty:
            return 0
        home_rows = self.df_teams[self.df_teams["team_name"] == home_team_name]
        if not home_rows.empty:
            return int(home_rows["team_id"].values[0])
        return 0

    def handle(self, session):
        minutes = Minutes(self.metric)
        minutes.calculate(self)
        minutes.write(session, self.game_id)

        goals = Goals(self.metric)
        goals.calculate(self)
        goals.write(session, self.game_id)

        vaep = Vaep(self.metric)
        vaep.calculate(self)
        vaep.write(session, self.game_id)
