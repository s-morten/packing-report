#from database_io.db_handler_abs import DB_handler_abs
from database_io.faks import Schedule
from datetime import datetime

class DB_schedule():
    def __init__(self, connection_item):
        self.connection = connection_item.connection
        self.session = connection_item.session
        self.engine = connection_item.engine
    def insert_batch_schedule(self, schedule: list) -> None: 
        batch = [Schedule(schedule_id=schedule_id, date_time=date_time, home=home, away=away, league=league) 
                 for schedule_id, date_time, home, away, league in schedule]
        self.session.add_all(batch)
        self.session.commit()

    def clear_table(self):
        self.session.query(Schedule).delete()
        self.session.commit()

    def games_in_timeframe(self, time_now: datetime, time_target: datetime) -> list[int]:
        return self.session.query(Schedule.schedule_id).filter(Schedule.date_time >= time_now).filter(Schedule.date_time <= time_target).all()