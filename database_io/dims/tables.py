from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

class Elo(declarative_base()):
    __tablename__ = "gde"
    __table_args__ = {'schema': 'METRICS'}

    player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, primary_key=True)
    game_date = Column(String)
    elo_value = Column(Float)
    version = Column(Float, primary_key=True)

class Games(declarative_base()):
    __tablename__ = "games"
    __table_args__ = {'schema': 'BASIS'}

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
    version = Column(Float, primary_key=True)
    home = Column(Integer)

class Processed_Footballsquads(declarative_base()):
    __tablename__ = "footballsquads_processed"
    __table_args__ = {'schema': 'SCRAPING'}

    processed = Column(String, primary_key=True)
