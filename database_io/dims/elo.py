from datetime import datetime
from scraper.club_elo_scraper import ClubEloScraper
# from database_io.db_handler_abs import DB_handler_abs
import pandas as pd
from database_io.dims import Elo, Games
from sqlalchemy import func

class DB_elo():
    def __init__(self, connection_item):
        self.connection = connection_item.connection
        self.session = connection_item.session
        self.engine = connection_item.engine

    def insert_elo(self, id: int, game_id: int, date: datetime, elo: float, version: float):
        elo = Elo(player_id=id, game_id=game_id, game_date=date, elo_value=elo, version=version)
        self.session.add(elo)
        self.session.commit()

    def insert_batch_elo(self, batch: list[tuple[int, int, datetime, float, float]]):
        elo_batch = [Elo(player_id=id, game_id=game_id, game_date=date, elo_value=elo, version=version) for id, game_id, date, elo, version in batch]
        self.session.bulk_save_objects(elo_batch)
        self.session.commit()
    

    def get_elo(self, id: int, date: datetime, league: str, starter: bool, version: float) -> float:
        """ Extracts the Elo per player from the database
            Returns default value if player does not exists
        """
        query_result = self.session.query(Elo.elo_value, 
                                          Elo.game_date).filter(
                                              Elo.player_id == id,
                                              Elo.version == version, 
                                              Elo.game_date < date).order_by(
                                                  Elo.game_date.desc()).first()

        if not query_result and self.get_player_count_per_league(league, version) < 50:
            league_elo = ClubEloScraper().get_avg_league_elo_by_date(pd.to_datetime(date, format="%Y-%m-%d"), league)
            start_elo = league_elo if starter else league_elo * 0.8
            return start_elo
        elif not query_result:
            a = self.average_elo_by_league(league, version)
            return a
        elo, _ = query_result
        return elo
    
    def average_elo_by_league(self, league: str, version: float) -> float:
        pre_select = self.session.query(
            Games.player_id,
            func.max(Games.game_date).label('max_gd')
        ).filter(Games.league == league, Games.version == version).group_by(Games.player_id).subquery()

        # Main query to calculate average elo_value for players in the pre_select subquery
        average_elo = self.session.query(func.avg(Elo.elo_value)).join(
            pre_select, (pre_select.c.player_id == Elo.player_id) & (pre_select.c.max_gd == Elo.game_date)).scalar()
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
        query_result = self.session.query(Elo.elo_value).filter(
                                              Elo.player_id == player_id,
                                              Elo.version == version).order_by(
                                                  Elo.game_date.desc()).first()
        if not query_result:
            return None
        return query_result
    
from sqlalchemy import select

def elo_query():
    return select(
        Elo.player_id,
        Elo.elo_value,
        func.rank().over(
            partition_by=Elo.player_id,
            order_by=Elo.game_date.desc()
        ).label('RANK')
    ).subquery()