from sqlalchemy import Column, Integer, String, Float, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base

class Metric(declarative_base()):
    __tablename__ = "METRIC"
    __table_args__ = {'schema': 'METRICS'}

    player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, primary_key=True)
    game_date = Column(Date)
    metric_value = Column(Float)
    version = Column(Float, primary_key=True)
    metric = Column(String, primary_key=True)

class Games(declarative_base()):
    __tablename__ = "GAMES"
    __table_args__ = {'schema': 'BASIS'}

    game_id = Column(Integer, primary_key=True)
    player_id = Column(Integer, primary_key=True)
    minutes = Column(Integer)
    starter = Column(Integer)
    opposition_team_id = Column(Integer)
    result = Column(String)
    elo = Column(Float)
    opposition_elo = Column(Float)
    game_date = Column(Date)
    team_id = Column(Integer)
    expected_game_result_lower = Column(Float)
    expected_game_result_upper = Column(Float)
    league = Column(String)
    version = Column(Float, primary_key=True)
    home = Column(Integer)
    game_minutes = Column(Integer)
    valid = Column(Integer)

class Processed_Footballsquads(declarative_base()):
    __tablename__ = "FOOTBALLSQUADS_PROCESSED"
    __table_args__ = {'schema': 'SCRAPING'}

    processed = Column(String, primary_key=True)
