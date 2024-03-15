from sqlalchemy import create_engine, Column, Integer, String, MetaData, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

class Player(declarative_base()):
    __tablename__ = "player"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    birthday = Column(String)