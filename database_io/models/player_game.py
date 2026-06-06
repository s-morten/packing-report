from sqlalchemy import Column, Integer

from database_io.models.base import Base


class PlayerGame(Base):
    __tablename__ = "PLAYER_GAME"
    __table_args__ = {"schema": "BASIS"}

    player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, primary_key=True)
    team_id = Column(Integer)
    minutes = Column(Integer)
    starter = Column(Integer)
    goals_for = Column(Integer)
    goals_against = Column(Integer)
    kit_number = Column(Integer)
    is_home = Column(Integer)
