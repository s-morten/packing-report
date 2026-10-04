from datetime import datetime, timedelta

from sqlalchemy import delete, distinct, func, select

from database_io.models.legacy import Games, Metric
from database_io.models.metric import PlayerGameMetric


class DB_metric:
    def insert_metric(self, session, id: int, game_id: int, elo: float, name: str):
        obj = PlayerGameMetric(player_id=id, game_id=game_id, value=elo, metric=name)
        session.merge(obj)
        session.commit()

    def insert_batch_metric(self, session, batch: list[tuple[int, int, float, str]]):
        for id, game_id, elo, name in batch:
            obj = PlayerGameMetric(player_id=int(id), game_id=int(game_id), value=float(elo), metric=name)
            session.merge(obj)
        session.commit()

    def get_processed_game_ids(self, session) -> set[int]:
        rows = session.query(distinct(PlayerGameMetric.game_id)).all()
        return {r[0] for r in rows}

    def delete_metrics(self, session, game_ids, metric_names) -> int:
        """Delete the named metrics for the given games.

        Used by the plus-minus runner so re-scoring a game replaces its rows instead of merging
        into them: a rebuild that covers fewer games than a previous run would otherwise leave the
        dropped games' ratings behind, since merging only touches the rows being written.
        """
        statement = delete(PlayerGameMetric).where(
            PlayerGameMetric.game_id.in_(list(game_ids)),
            PlayerGameMetric.metric.in_(list(metric_names)),
        )
        result = session.execute(statement)
        session.commit()
        return result.rowcount

    def get_metric(
        self, session, id: int, date: datetime, league: str, starter: bool, version: float, metric: str
    ) -> float | None:  # noqa: E501
        query_result = (
            session.query(Metric.metric_value, Metric.game_date)
            .filter(Metric.player_id == id, Metric.version == version, Metric.metric == metric, Metric.game_date < date)
            .order_by(Metric.game_date.desc())
            .first()
        )
        if not query_result:
            return None
        elo, _ = query_result
        return elo

    def average_elo(self, session, league: str, club_id: int, game_date: datetime, version: float) -> float | None:
        elo = self.average_elo_by_club(session, club_id, game_date, version)
        if elo is None:
            return self.average_elo_by_league(session, league, game_date, version)
        return elo

    def average_elo_by_club(self, session, club_id: int, game_date: datetime, version: float) -> float | None:
        if session.query(Games).filter(Games.team_id == int(club_id), Games.version == version).count() < 50:
            return None
        pre_select = (
            session.query(Games.player_id, func.max(Games.game_date).label("max_gd"))
            .filter(Games.team_id == int(club_id), Games.version == version)
            .group_by(Games.player_id)
            .subquery()
        )
        average_elo = (
            session.query(func.avg(Metric.metric_value))
            .filter(Metric.game_date >= game_date - timedelta(weeks=6 * 4), Metric.metric == "elo")
            .join(pre_select, (pre_select.c.player_id == Metric.player_id) & (pre_select.c.max_gd == Metric.game_date))
            .scalar()
        )
        return average_elo

    def average_elo_by_league(self, session, league: str, game_date: datetime, version: float) -> float | None:
        pre_select = (
            session.query(Games.player_id, func.max(Games.game_date).label("max_gd"))
            .filter(Games.league == league, Games.version == version)
            .group_by(Games.player_id)
            .subquery()
        )
        average_elo = (
            session.query(func.avg(Metric.metric_value))
            .filter(Metric.game_date >= game_date - timedelta(weeks=6 * 4), Metric.metric == "elo")
            .join(pre_select, (pre_select.c.player_id == Metric.player_id) & (pre_select.c.max_gd == Metric.game_date))
            .scalar()
        )
        return average_elo

    def get_player_count_per_league(self, session, league: str, version: float) -> int:
        pre_select = (
            session.query(Games.player_id, func.max(Games.game_date).label("max_gd"))
            .filter(Games.league == league, Games.version == version)
            .group_by(Games.player_id)
            .subquery()
        )
        return session.query(func.count()).select_from(pre_select).scalar()

    def extract_latest_elo(self, session, player_id: int, version: float) -> float | None:
        query_result = (
            session.query(Metric.metric_value)
            .filter(Metric.player_id == player_id, Metric.version == version)
            .order_by(Metric.game_date.desc())
            .first()
        )
        if not query_result:
            return None
        return query_result


def metric_query():
    return select(
        Metric.player_id,
        Metric.metric,
        Metric.metric_value,
        func.rank()
        .over(partition_by=[Metric.player_id, Metric.metric], order_by=Metric.game_date.desc())
        .label("RANK"),
    ).subquery()
