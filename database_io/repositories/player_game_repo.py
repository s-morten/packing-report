import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from database_io.models.game import Game
from database_io.models.player_game import PlayerGame


class DB_player_game:
    """Repository for ``BASIS.PLAYER_GAME``.

    The presence interval (``on_minute`` / ``off_minute``) is what lets the plus-minus stage
    rebuild who was on the pitch in each segment without storing a per-segment player table:
    a player occupies segment ``[b_k, b_k+1)`` exactly when ``on <= b_k and off >= b_k+1``.
    """

    @staticmethod
    def _upsert_statement(session: Session):
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            return pg_insert(PlayerGame)
        if bind.dialect.name == "sqlite":
            return sqlite_insert(PlayerGame)
        raise ValueError(f"Unsupported dialect '{bind.dialect.name}' for player game upsert")

    def upsert_player_games(self, session: Session, rows: list[dict]) -> int:
        if not rows:
            return 0
        game_id = int(rows[0]["game_id"])
        session.execute(delete(PlayerGame).where(PlayerGame.game_id == game_id))

        values = [
            {
                "player_id": int(r["player_id"]),
                "game_id": int(r["game_id"]),
                "team_id": int(r["team_id"]),
                "minutes": int(r["minutes"]),
                "on_minute": float(r["on_minute"]),
                "off_minute": float(r["off_minute"]),
                "starter": int(r["starter"]),
                "goals_for": int(r.get("goals_for") or 0),
                "goals_against": int(r.get("goals_against") or 0),
                "kit_number": int(r["kit_number"]) if r.get("kit_number") is not None else None,
                "is_home": int(r["is_home"]),
            }
            for r in rows
        ]
        session.execute(self._upsert_statement(session).values(values))
        session.commit()
        return len(values)

    def delete_games(self, session: Session, game_ids: list[int]) -> int:
        if not game_ids:
            return 0
        result = session.execute(delete(PlayerGame).where(PlayerGame.game_id.in_([int(g) for g in game_ids])))
        session.commit()
        return result.rowcount or 0

    def get_player_games(self, session: Session, game_ids: list[int] | None = None) -> pd.DataFrame:
        stmt = select(
            PlayerGame.player_id,
            PlayerGame.game_id,
            PlayerGame.team_id,
            PlayerGame.minutes,
            PlayerGame.on_minute,
            PlayerGame.off_minute,
            PlayerGame.starter,
            PlayerGame.is_home,
        ).join(Game, Game.id == PlayerGame.game_id)

        if game_ids is not None:
            stmt = stmt.where(PlayerGame.game_id.in_([int(g) for g in game_ids]))

        stmt = stmt.order_by(Game.date, PlayerGame.game_id, PlayerGame.player_id)
        return pd.read_sql(stmt, session.get_bind())
