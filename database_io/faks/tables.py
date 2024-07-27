from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

class Player(declarative_base()):
    __tablename__ = "player"
    __table_args__ = {'schema': 'BASIS'}

    id = Column(Integer, primary_key=True)
    name = Column(String)
    birthday = Column(String)
    fapi_id = Column(Integer)

class Birthday_Footballsquads(declarative_base()):
    __tablename__ = "footballsquads_birthday"
    __table_args__ = {'schema': 'SCRAPING'}

    kit_number = Column(Integer, primary_key=True)
    name = Column(String, primary_key=True)
    nationality = Column(String)
    position = Column(String)
    height = Column(String)
    weight = Column(String)
    date_of_birth = Column(String)
    place_of_birth = Column(String)
    previous_club = Column(String)
    team = Column(String, primary_key=True)
    league = Column(String)
    season = Column(String, primary_key=True)

class Team(declarative_base()):
    __tablename__ = "teams"
    __table_args__ = {'schema': 'BASIS'}

    id = Column(Integer, primary_key=True)
    name = Column(String)

class Squads(declarative_base()):
    __tablename__ = "squads"
    __table_args__ = {'schema': 'BASIS'}

    squad_id = Column(Integer, primary_key=True)
    player_id = Column(Integer)
    kit_number = Column(Integer)
    valid_from = Column(String)
    valid_to = Column(String)
    team_id = Column(Integer)

class Schedule(declarative_base()):
    __tablename__ = "schedule"
    __table_args__ = {'schema': 'SCRAPING'}

    schedule_id = Column(Integer, primary_key=True)
    date_time = Column(String)
    home = Column(String)
    away = Column(String)