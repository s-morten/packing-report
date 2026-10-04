"""Stage 1 of the plus-minus pipeline: turn one processed game into durable segment facts.

Runs after the low-level metrics, because it reuses ``game_facts.players_dict`` and
``game_facts.end_of_game`` (built by :class:`metrics.low_level.minutes.Minutes`) and the single xT
pricing pass (built by :class:`metrics.low_level.xt.Xt`).

Three things are written:

* ``BASIS.GAME`` -- the game header. Stage 2 orders games chronologically straight from the
  database and never touches the scraper, so the date has to be persisted.
* ``BASIS.PLAYER_GAME`` -- one row per player with the presence interval ``on_minute`` /
  ``off_minute``. These two columns are all that is needed to rebuild who was on the pitch in each
  segment, so no per-segment player table is needed.
* ``METRICS.GAME_SEGMENT`` -- one row per segment with both dependent variables.

Everything is upserted, so re-running stage 1 for a game overwrites it in place.
"""

import pandas as pd
from metrics.low_level.xt import Xt

from database_io.repositories.player_game_repo import DB_player_game
from database_io.repositories.segment_repo import DB_segment
from game.game_segments import build_segments, goals_per_segment
from utils.date_utils import to_season


class GameMetrics:
    def __init__(self, segment_repo=None, player_game_repo=None, xt=None):
        self.segment_repo = segment_repo or DB_segment()
        self.player_game_repo = player_game_repo or DB_player_game()
        self.xt = xt or Xt()

    def handle(self, session, game_facts, date, league: str):
        segments = build_segments(game_facts)
        segment_goals = goals_per_segment(game_facts, segments)

        # One xT pricing pass, shared by the per-player metric and the per-segment DV.
        self.xt.calculate(game_facts, segments)
        self.xt.write(session, game_facts.game_id)

        self.segment_repo.upsert_game(
            session=session,
            game_id=game_facts.game_id,
            date=date,
            home_team_id=game_facts.home_team_id,
            away_team_id=self._away_team_id(game_facts),
            league=league,
            season=to_season(date),
            game_minutes=game_facts.end_of_game,
        )

        self.player_game_repo.upsert_player_games(session, self._player_game_rows(game_facts))
        self.segment_repo.upsert_segments(session, self.xt.segment_rows(game_facts.game_id, segments, segment_goals))

    @staticmethod
    def _away_team_id(game_facts) -> int:
        team_ids = [int(t) for t in game_facts.df_teams["team_id"].unique()]
        if len(team_ids) != 2:
            raise ValueError(f"expected exactly 2 teams for game {game_facts.game_id}, got {team_ids}")
        for team_id in team_ids:
            if team_id != int(game_facts.home_team_id):
                return team_id
        raise ValueError(f"home team {game_facts.home_team_id} not found among {team_ids}")

    def _player_game_rows(self, game_facts) -> list[dict]:
        """One ``PLAYER_GAME`` row per player, carrying the presence interval."""
        players_df = game_facts.loader_players_df
        starters: set[int] = set()
        kit_numbers: dict[int, object] = {}
        if players_df is not None and not players_df.empty:
            starters_df = players_df[players_df["is_starter"]]
            starters = {int(p) for p in starters_df["player_id"]}
            for player_id, kit in zip(players_df["player_id"], players_df["jersey_number"], strict=False):
                kit_numbers[int(player_id)] = kit

        # goals_for / goals_against are resolved by metrics.low_level.goals.Goals, which runs
        # earlier in GameFacts.handle and leaves its per-player mapping on game_facts.
        goal_mapping = getattr(game_facts, "player_goal_minute_mapping", None) or {}

        home_team_id = int(game_facts.home_team_id)
        rows = []
        for player_id, info in game_facts.players_dict.items():
            player_id = int(player_id)
            on = float(info["on"])
            off = float(info["off"])
            goals = goal_mapping.get(player_id, {})
            kit_number = kit_numbers.get(player_id)
            rows.append(
                {
                    "player_id": player_id,
                    "game_id": int(game_facts.game_id),
                    "team_id": int(info["team_id"]),
                    "minutes": int(off - on),
                    "on_minute": on,
                    "off_minute": off,
                    "starter": int(player_id in starters),
                    "goals_for": int(goals.get("goals_for", 0)),
                    "goals_against": int(goals.get("goals_against", 0)),
                    "kit_number": int(kit_number) if kit_number is not None and not pd.isna(kit_number) else None,
                    "is_home": int(int(info["team_id"]) == home_team_id),
                }
            )
        return rows
