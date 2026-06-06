from sqlalchemy import Column, Date, Integer, String

from database_io.models.base import Base


class Game(Base):
    __tablename__ = "GAME"
    __table_args__ = {"schema": "BASIS"}

    id = Column(Integer, primary_key=True)
    date = Column(Date)
    home_team = Column(Integer)
    away_team = Column(Integer)
    league = Column(String)
    season = Column(String)
    game_minutes = Column(Integer)
