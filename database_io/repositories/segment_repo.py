import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from database_io.models.game import Game
from database_io.models.segment import GameSegment


def _upsert_statement(session: Session):
    """Return a dialect-appropriate ``INSERT .. ON CONFLICT DO UPDATE`` for the segment table.

    SQLAlchemy's generic ``insert().on_conflict_do_update`` needs a dialect-specific insert
    construct, so the two dialects this project supports are handled explicitly.
    """
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        return pg_insert(GameSegment)
    if bind.dialect.name == "sqlite":
        return sqlite_insert(GameSegment)
    raise ValueError(f"Unsupported dialect '{bind.dialect.name}' for segment upsert")


class DB_segment:
    def __init__(self, game_repo=None) -> None:
        from database_io.repositories.game_repo import DB_game

        self.game_repo = game_repo or DB_game()

    def upsert_game(
        self,
        session: Session,
        game_id: int,
        date,
        home_team_id: int,
        away_team_id: int,
        league: str,
        season: str,
        game_minutes: float,
    ) -> None:
        """Upsert the ``BASIS.GAME`` row that ``GAME_SEGMENT`` and ``PLAYER_GAME`` point at.

        Stage 2 orders games chronologically straight from the database and never talks to the
        scraper, so the game date has to be persisted here.
        """
        self.game_repo.upsert_game(
            session=session,
            game_id=int(game_id),
            date=date,
            home_team_id=int(home_team_id),
            away_team_id=int(away_team_id),
            league=str(league),
            season=str(season),
            game_minutes=float(game_minutes),
        )

    def upsert_segments(self, session: Session, segments: list[dict]) -> int:
        """Replace the segments of one game. Idempotent: re-running stage 1 overwrites in place."""
        if not segments:
            return 0
        game_id = int(segments[0]["game_id"])
        session.execute(delete(GameSegment).where(GameSegment.game_id == game_id))

        rows = [
            {
                "game_id": int(s["game_id"]),
                "segment_index": int(s["segment_index"]),
                "start_minute": float(s["start_minute"]),
                "end_minute": float(s["end_minute"]),
                "duration_minutes": float(s["duration_minutes"]),
                "n_players_home": int(s["n_players_home"]),
                "n_players_away": int(s["n_players_away"]),
                "xt_home": float(s["xt_home"]),
                "xt_away": float(s["xt_away"]),
                "net_xt": float(s["net_xt"]),
                "net_xt_per90": float(s["net_xt_per90"]),
                "goals_home": int(s["goals_home"]),
                "goals_away": int(s["goals_away"]),
                "gd90": float(s["gd90"]),
            }
            for s in segments
        ]
        stmt = _upsert_statement(session)
        session.execute(stmt.values(rows))
        session.commit()
        return len(rows)

    def has_segments(self, session: Session, game_id: int) -> bool:
        return session.query(GameSegment.game_id).filter(GameSegment.game_id == int(game_id)).first() is not None

    def delete_games(self, session: Session, game_ids: list[int]) -> int:
        if not game_ids:
            return 0
        result = session.execute(delete(GameSegment).where(GameSegment.game_id.in_([int(g) for g in game_ids])))
        session.commit()
        return result.rowcount or 0

    def get_segments(self, session: Session, game_ids: list[int] | None = None) -> pd.DataFrame:
        """All segments as a frame, joined to the game date and ordered chronologically.

        This is the only input stage 2 needs: it never re-reads raw events.
        """
        stmt = select(
            GameSegment.game_id,
            GameSegment.segment_index,
            GameSegment.start_minute,
            GameSegment.end_minute,
            GameSegment.duration_minutes,
            GameSegment.n_players_home,
            GameSegment.n_players_away,
            GameSegment.xt_home,
            GameSegment.xt_away,
            GameSegment.net_xt,
            GameSegment.net_xt_per90,
            GameSegment.goals_home,
            GameSegment.goals_away,
            GameSegment.gd90,
            Game.date.label("game_date"),
            Game.league,
            Game.season,
        ).join(Game, Game.id == GameSegment.game_id)

        if game_ids is not None:
            stmt = stmt.where(GameSegment.game_id.in_([int(g) for g in game_ids]))

        stmt = stmt.order_by(Game.date, GameSegment.game_id, GameSegment.segment_index)
        return pd.read_sql(stmt, session.get_bind())
