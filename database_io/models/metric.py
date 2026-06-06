from sqlalchemy import Column, Float, Integer, String

from database_io.models.base import Base


class PlayerGameMetric(Base):
    __tablename__ = "PLAYER_GAME_METRIC"
    __table_args__ = {"schema": "METRICS"}

    player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, primary_key=True)
    metric = Column(String, primary_key=True)
    value = Column(Float)
