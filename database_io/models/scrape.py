from sqlalchemy import Column, Integer, String

from database_io.models.base import Base


class FootballsquadsRaw(Base):
    __tablename__ = "FOOTBALLSQUADS_RAW"
    __table_args__ = {"schema": "SCRAPING"}

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


class ScrapeLog(Base):
    __tablename__ = "SCRAPE_LOG"
    __table_args__ = {"schema": "SCRAPING"}

    file = Column(String, primary_key=True)
