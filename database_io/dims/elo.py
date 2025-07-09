from datetime import datetime, timedelta
from scraper.club_elo_scraper import ClubEloScraper
# from database_io.db_handler_abs import DB_handler_abs
import pandas as pd
from database_io.dims import Metric, Games
from sqlalchemy import func, select

class DB_metric():
    def __init__(self, connection_item):
        self.connection = connection_item.connection
        self.session = connection_item.session
        self.engine = connection_item.engine

    def insert_metric(self, id: int, game_id: int, date: datetime, elo: float, version: float, name: str):
        elo = Metric(player_id=id, game_id=game_id, game_date=date, metric_value=elo, version=version, metric=name)
        self.session.add(elo)
        self.session.commit()

    def insert_batch_metric(self, batch: list[tuple[int, int, datetime, float, float, str]]):
        elo_batch = [Metric(player_id=id, game_id=game_id, game_date=date, metric_value=elo, version=version, metric=name) for id, game_id, date, elo, version, name in batch]
        self.session.bulk_save_objects(elo_batch)
        self.session.commit()
    

    def get_metric(self, id: int, date: datetime, league: str, starter: bool, version: float, metric: str) -> float:
        """ Extracts the Elo per player from the database
            Returns default value if player does not exists
        """
        query_result = self.session.query(Metric.metric_value, 
                                          Metric.game_date).filter(
                                              Metric.player_id == id,
                                              Metric.version == version, 
                                              Metric.metric == metric,
                                              Metric.game_date < date).order_by(
                                                  Metric.game_date.desc()).first()

        if not query_result: # and self.get_player_count_per_league(league, version) < 50:
        #     league_elo = ClubEloScraper().get_avg_league_elo_by_date(pd.to_datetime(date, format="%Y-%m-%d"), league)
        #     start_elo = league_elo if starter else league_elo * 0.8
        #     return start_elo
        # elif not query_result:
        #     a = self.average_elo_by_league(league, version)
        #     return a
            return None
        elo, _ = query_result
        return elo
    
    def average_elo(self, league: str, club_id: int, game_date: datetime, version: float) -> float:
        elo = self.average_elo_by_club(club_id, game_date, version)
        if elo is None: 
            return self.average_elo_by_league(league, game_date, version)
        return elo

    def average_elo_by_club(self, club_id: int, game_date: datetime, version: float) -> float | None:
        if self.session.query(Games).filter(Games.team_id == int(club_id), Games.version == version).count() < 50:
            return None
        pre_select = self.session.query(
            Games.player_id,
            func.max(Games.game_date).label('max_gd')
        ).filter(Games.team_id == int(club_id), Games.version == version).group_by(Games.player_id).subquery()

        # Main query to calculate average elo_value for players in the pre_select subquery
        average_elo = self.session.query(func.avg(Metric.metric_value)).filter(Metric.game_date >= game_date - timedelta(weeks=6*4)).join(
            pre_select, (pre_select.c.player_id == Metric.player_id) & (pre_select.c.max_gd == Metric.game_date)).scalar()
        return average_elo

    def average_elo_by_league(self, league: str, game_date: datetime, version: float) -> float:
        pre_select = self.session.query(
            Games.player_id,
            func.max(Games.game_date).label('max_gd')
        ).filter(Games.league == league, Games.version == version).group_by(Games.player_id).subquery()

        # Main query to calculate average elo_value for players in the pre_select subquery
        average_elo = self.session.query(func.avg(Metric.metric_value)).filter(Metric.game_date >= game_date - timedelta(weeks=6*4)).join(
            pre_select, (pre_select.c.player_id == Metric.player_id) & (pre_select.c.max_gd == Metric.game_date)).scalar()
        return average_elo
    
    def get_player_count_per_league(self, league: str, version: float) -> int:
        pre_select = self.session.query(
            Games.player_id,
            func.max(Games.game_date).label('max_gd')
        ).filter(Games.league == league, Games.version == version).group_by(Games.player_id).subquery()

        # Main query to count the number of rows in the pre_select subquery
        count_result = self.session.query(func.count()).select_from(pre_select).scalar()
        return count_result
    
    def extract_latest_elo(self, player_id: int, version: float) -> float:
        query_result = self.session.query(Metric.metric_value).filter(
                                              Metric.player_id == player_id,
                                              Metric.version == version).order_by(
                                                  Metric.game_date.desc()).first()
        if not query_result:
            return None
        return query_result

def metric_query():
    return select(
        Metric.player_id,
        Metric.metric,
        Metric.metric_value,
        func.rank().over(
            partition_by=[Metric.player_id, Metric.metric],
            order_by=Metric.game_date.desc()
        ).label('RANK')
    ).subquery()