import soccerdata as sd
from metrics.low_level.goals import Goals
from metrics.low_level.minutes import Minutes
from metrics.low_level.time_to_recovery import TimeToRecovery
from metrics.low_level.vaep import Vaep
from metrics.low_level.xt import Xt

from database_io.repositories.metric_repo import DB_metric


class GameFacts:
    def __init__(self, ws: sd.WhoScored, game_id: int, home_team_name: str) -> None:
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

    def _resolve_home_team_id(self, home_team_name: str) -> int:
        if not home_team_name or not home_team_name.strip():
            raise ValueError("home_team_name must be a non-empty string")
        if self.df_teams is None or self.df_teams.empty:
            raise ValueError(f"no team data available for game {self.game_id}")
        for column in ("team_name", "team_id"):
            if column not in self.df_teams.columns:
                raise KeyError(f"df_teams is missing required column '{column}'")
        normalized_name = home_team_name.strip().lower()
        home_rows = self.df_teams[self.df_teams["team_name"].str.lower() == normalized_name]
        if home_rows.empty:
            raise LookupError(f"could not find team '{home_team_name}' in teams data for game {self.game_id}")
        return int(home_rows["team_id"].iloc[0])

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

        xt = Xt(self.metric)
        xt.calculate(self)
        xt.write(session, self.game_id)

        time_to_recovery = TimeToRecovery(self.metric)
        time_to_recovery.calculate(self)
        time_to_recovery.write(session, self.game_id)
