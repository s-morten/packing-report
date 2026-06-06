from sqlalchemy import Column, Date, Float, Integer, String

from database_io.models.base import Base


class Games(Base):
    __tablename__ = "GAMES"
    __table_args__ = {"schema": "BASIS"}

    game_id = Column(Integer, primary_key=True)
    player_id = Column(Integer, primary_key=True)
    minutes = Column(Integer)
    starter = Column(Integer)
    opposition_team_id = Column(Integer)
    result = Column(String)
    elo = Column(Float)
    opposition_elo = Column(Float)
    game_date = Column(Date)
    team_id = Column(Integer)
    expected_game_result_lower = Column(Float)
    expected_game_result_upper = Column(Float)
    league = Column(String)
    version = Column(Float)
    home = Column(Integer)
    game_minutes = Column(Integer)
    valid = Column(Integer)


class Metric(Base):
    __tablename__ = "BASE_METRIC"
    __table_args__ = {"schema": "METRICS"}

    player_id = Column(Integer, primary_key=True)
    game_id = Column(Integer, primary_key=True)
    game_date = Column(Date, primary_key=True)
    version = Column(Float, primary_key=True)
    metric = Column(String, primary_key=True)
    metric_value = Column(Float)


class Squads(Base):
    __tablename__ = "SQUADS"
    __table_args__ = {"schema": "BASIS"}

    player_id = Column(Integer, primary_key=True)
    kit_number = Column(Integer, primary_key=True)
    team_id = Column(Integer, primary_key=True)
    valid_from = Column(Date, primary_key=True)
    valid_to = Column(Date, primary_key=True)


class Schedule(Base):
    __tablename__ = "SCHEDULE"
    __table_args__ = {"schema": "BASIS"}

    schedule_id = Column(Integer, primary_key=True)
    date_time = Column(Date)
    home = Column(Integer)
    away = Column(Integer)
    league = Column(Integer)


class Prediction(Base):
    __tablename__ = "PREDICTION"
    __table_args__ = {"schema": "BASIS"}

    game_id = Column(Integer, primary_key=True)
    home_elo = Column(Float)
    away_elo = Column(Float)
    prediction_low = Column(Float)
    prediction_high = Column(Float)
    result = Column(String)


class Birthday_Footballsquads(Base):
    __tablename__ = "BIRTHDAY_FOOTBALLSQUADS"
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


class Processed_Footballsquads(Base):
    __tablename__ = "PROCESSED_FOOTBALLSQUADS"
    __table_args__ = {"schema": "SCRAPING"}

    processed = Column(String, primary_key=True)
