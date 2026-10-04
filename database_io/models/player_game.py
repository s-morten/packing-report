from sqlalchemy import Column, Float, Integer

from database_io.models.base import Base


class PlayerGame(Base):
    __tablename__ = "PLAYER_GAME"
    __table_args__ = {"schema": "BASIS"}

    player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, primary_key=True)
    team_id = Column(Integer)
    minutes = Column(Integer)
    # Presence interval, both already clipped to the end of the match (which itself stops at the
    # first red card). A player is on the pitch for segment [b_k, b_k+1) iff
    # on_minute <= b_k and off_minute >= b_k+1, so these two columns are all that is needed to
    # rebuild the plus-minus design matrix without a per-segment player table.
    on_minute = Column(Float)
    off_minute = Column(Float)
    starter = Column(Integer)
    goals_for = Column(Integer)
    goals_against = Column(Integer)
    kit_number = Column(Integer)
    is_home = Column(Integer)
