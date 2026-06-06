from sqlalchemy import Column, Date, Integer, String

from database_io.models.base import Base


class Player(Base):
    __tablename__ = "PLAYER"
    __table_args__ = {"schema": "BASIS"}

    id = Column(Integer, primary_key=True)
    name = Column(String)
    birthday = Column(Date)
    fapi_id = Column(Integer)


class PlayerAlias(Base):
    __tablename__ = "PLAYER_ALIAS"
    __table_args__ = {"schema": "BASIS"}

    player_id = Column(Integer, primary_key=True)
    source = Column(String, primary_key=True)
    source_id = Column(String)
