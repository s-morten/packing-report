from sqlalchemy import Column, Integer, String

from database_io.models.base import Base


class Team(Base):
    __tablename__ = "TEAMS"
    __table_args__ = {"schema": "BASIS"}

    id = Column(Integer, primary_key=True)
    name = Column(String)
