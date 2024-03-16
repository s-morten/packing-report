from sqlalchemy import create_engine, Column, Integer, String, MetaData, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

class Player(declarative_base()):
    __tablename__ = "player"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    birthday = Column(String)

class Birthday_Footballsquads(declarative_base()):
    __tablename__ = "birthday_footballsquads"

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