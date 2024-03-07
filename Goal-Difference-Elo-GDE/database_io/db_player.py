import pandas as pd
from datetime import datetime
from .db_handler import DB_handler
from scraper.club_elo_scraper import ClubEloScraper
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

class DB_player(DB_handler):
    class Elo(declarative_base()):
        __tablename__ = "elo"

        player_id = Column(Integer, primary_key=True)
        game_id = Column(Integer, primary_key=True)
        game_date = Column(String)
        elo_value = Column(Float)

    class Player(declarative_base()):
        __tablename__ = "player"

        id = Column(Integer, primary_key=True)
        name = Column(String)
        birthday = Column(String)

    class Games(declarative_base()):
        __tablename__ = "games"

        game_id = Column(Integer, primary_key=True)
        player_id = Column(Integer, primary_key=True)
        minutes = Column(Integer)
        starter = Column(Integer)
        opposition_team_id = Column(Integer)
        result = Column(String)
        elo = Column(Float)
        opposition_elo = Column(Float)
        game_date = Column(String)
        team_id = Column(Integer)
        expected_game_result = Column(Float)
        roundend_expected_game_result = Column(Float)
        league = Column(String)

    def insert_player(self, id: int, name: str, birthday: datetime):
        birthday = datetime.strptime(birthday, "%d-%m-%y").strftime("%Y-%m-%d")
        player = self.Player(name=str(name), id=int(id), birthday=birthday)
        # print(player)
        self.session.add(player)
        self.session.commit()

    def insert_elo(self, id: int, game_id: int, date: datetime, elo: float):
        elo = self.Elo(player_id=id, game_id=game_id, game_date=date.strftime("%Y-%m-%d"), elo_value=elo)
        self.session.add(elo)
        self.session.commit()

    def insert_game(self, game_id: int, player_id: int, minutes: int, starter: bool, 
                    opposition_team_id: int, result: str, elo: float, opposition_elo: float, 
                    game_date: datetime, team_id: int, expected_game_result: float, 
                    roundend_expected_game_result: float, league: str):
        game = self.Games(game_id=int(game_id), player_id=int(player_id), minutes=int(minutes), starter=int(starter), opposition_team_id=int(opposition_team_id),
                            result=str(result), elo=float(elo), opposition_elo=float(opposition_elo), game_date=game_date.strftime("%Y-%m-%d"),
                            team_id=int(team_id), expected_game_result=float(expected_game_result), 
                            roundend_expected_game_result=float(roundend_expected_game_result), league=str(league))
        self.session.add(game)
        self.session.commit()

    def get_elo(self, id: int, date: datetime, league: str, starter: bool) -> float:
        """ Extracts the Elo per player from the database
            Returns default value if player does not exists
        """
        query_result = self.session.query(self.Elo.elo_value, 
                                          self.Elo.game_date).filter(
                                              self.Elo.player_id == id, 
                                              self.Elo.game_date < date).order_by(
                                                  self.Elo.game_date.desc()).first()

        if not query_result and self.get_player_count_per_league(league) < 50:
            league_elo = ClubEloScraper().get_avg_league_elo_by_date(pd.to_datetime(date, format="%Y-%m-%d"), league)
            start_elo = league_elo if starter else league_elo * 0.8
            # print("start: ", start_elo)
            return start_elo
        elif not query_result:
            a = self.average_elo_by_league(league)
            # print("avg: ", a)
            return a
        elo, _ = query_result
        # print("elo: ", elo)
        return elo
        
    def player_exists(self, id: int) -> bool:
        query_result = self.session.query(self.Player).filter(self.Player.id == id).first()
        return not (query_result is None)

    def average_elo_by_league(self, league: str) -> float:
        pre_select = self.session.query(
            self.Games.player_id,
            func.max(self.Games.game_date).label('max_gd')
        ).filter(self.Games.league == league).group_by(self.Games.player_id).subquery()

        # Main query to calculate average elo_value for players in the pre_select subquery
        average_elo = self.session.query(func.avg(self.Elo.elo_value)).join(
            pre_select, (pre_select.c.player_id == self.Elo.player_id) & (pre_select.c.max_gd == self.Elo.game_date)).scalar()
        return average_elo
    
    def get_player_count_per_league(self, league: str) -> int:
        pre_select = self.session.query(
            self.Games.player_id,
            func.max(self.Games.game_date).label('max_gd')
        ).filter(self.Games.league == league).group_by(self.Games.player_id).subquery()

        # Main query to count the number of rows in the pre_select subquery
        count_result = self.session.query(func.count()).select_from(pre_select).scalar()
        return count_result

    def get_all_games(self):
        query_result = self.session.query(self.Games.minutes, self.Games.elo, self.Games.opposition_elo, self.Games.result).all()
        df = pd.DataFrame(query_result, columns=['minutes', 'elo', 'opposition_elo', 'result'])
        return df

    def get_number_of_games(self):
        query_result = self.session.query(func.count(self.Games.game_id.distinct())).scalar()
        return query_result