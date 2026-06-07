from datetime import datetime, timedelta

from sqlalchemy import func, select

from database_io.models.legacy import Games, Metric


class DB_metric:
    def insert_metric(self, session, id: int, game_id: int, elo: float, name: str):
        elo = Metric(player_id=id, game_id=game_id, metric_value=elo, metric=name)
        session.add(elo)
        session.commit()

    def insert_batch_metric(self, session, batch: list[tuple[int, int, float, str]]):
        elo_batch = [
            Metric(player_id=int(id), game_id=int(game_id), metric_value=float(elo), metric=name)
            for id, game_id, elo, name in batch
        ]
        session.bulk_save_objects(elo_batch)
        session.commit()

    def get_metric(self, session, id: int, date: datetime, league: str, starter: bool, version: float, metric: str) -> float | None:
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
