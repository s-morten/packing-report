# from database_io.db_handler_abs import DB_handler_abs
from database_io.faks import Player, Team
from database_io.dims import Metric, Games
from sqlalchemy import func
import numpy as np
from time import sleep
from sqlalchemy import Column, Integer, String, Date, Float
from sqlalchemy.ext.declarative import declarative_base
import pandas as pd

class Latest_elo(declarative_base()):
    __tablename__ = "METRIC_LATEST"
    __table_args__ = {'schema': 'METRICS'}
    
    player_id = Column(Integer, primary_key=True)
    elo_value = Column(Float)
    game_date = Column(Date)
    name = Column(String)
    birthday = Column(Date)
    league = Column(String)
    team_name = Column(String)
    


class DB_webpage():
    def __init__(self, connection_item):
        self.connection = connection_item.connection
        self.session = connection_item.session
        self.engine = connection_item.engine
    
    def get_table_data(self):
        # TODO sort descending and return a rank
        df = pd.DataFrame(self.session.query(Latest_elo.player_id, Latest_elo.game_date,
                                             Latest_elo.elo_value, Latest_elo.name,
                                             Latest_elo.birthday, Latest_elo.league, Latest_elo.team_name).order_by(Latest_elo.elo_value.desc()).all(),
                          columns=['player_id', 'game_date', 'elo_value', 'name', 'birthday', 'league', 'team_name'])
        df['rank'] = df['elo_value'].rank(method='min', ascending=False).astype(int)
        return df

    def get_clubs(self, league, date):
        # TODO very bad solution of fixing database problems with sqlalchemy multithreading 
        # https://stackoverflow.com/questions/41279157/connection-problems-with-sqlalchemy-and-multiple-processes
        sleep(1)
        result = (
            self.session.query(
                Team.name
            )
            .join(Games, Team.id == Games.team_id)
            .filter(Games.league.in_(league), Games.game_date > date)
        ).distinct().all()
        return np.array(result)
    
    def get_team_table(self, min_date, max_date, league):
        max_elo_date = (
            self.session.query(
                Metric.player_id,
                func.max(Metric.game_date).label("found_date")
            )
            .filter(Metric.game_date >= min_date)
            .filter(Metric.game_date <= max_date)
            .group_by(Metric.player_id)
            .subquery()
        )

        filterd_elo = (
            self.session.query(
                Metric.player_id,
                Metric.metric_value, 
                Metric.game_id
            )
            .join(max_elo_date, (
                Metric.player_id == max_elo_date.c.player_id
            ) & (
                max_elo_date.c.found_date == Metric.game_date
            )).subquery()
        )

        get_games = (
            self.session.query(
                Games.team_id,
                func.avg(filterd_elo.c.elo_value).label("strength")
            )
            .join(filterd_elo, 
                  (Games.player_id == filterd_elo.c.player_id) 
                  & (filterd_elo.c.game_id == Games.game_id))
            .group_by(Games.team_id)
            .subquery()
        )

        result = (
            self.session.query(
                Team.name, 
                get_games.c.strength    
            )
            .join(get_games, Team.id == get_games.c.team_id)
            .order_by(get_games.c.strength.desc())
            # .all()      
        )
        print(result)

        return result


    def trend(self, player_id):
        sleep(2)
        elo_game_subquery = (
            self.session.query(
                Metric,
                Games.minutes,
                Games.starter,
                Games.opposition_team_id,
                Games.result,
                Games.elo.label('game_elo'),
                Games.opposition_elo,
                Games.team_id,
                Games.expected_game_result_lower,
                Games.expected_game_result_upper
            )
            .filter(Metric.player_id == player_id)
            .join(Games, (Metric.game_id == Games.game_id) & (Metric.player_id == Games.player_id))
            .subquery()
            )

            # Main query to join elo_game_subquery and Player table
        result = (
            self.session.query(
                elo_game_subquery,
                Player.name
            )
            .join(Player, elo_game_subquery.c.player_id == Player.id).all()
        )

        return result

    def player_id_select(self):
        result = (
            self.session.query(
                Player.id,
                Player.name
            ).all()
        )
        return result