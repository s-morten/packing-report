from database_io.db_handler_abs import DB_handler_abs
from database_io.faks import Schedule

class DB_schedule(DB_handler_abs):
    def insert_schedule(self, schedule_id: int, date_time: str, home: str, away: str):
        schedule = Schedule(schedule_id=schedule_id, date_time=date_time, home=home, away=away)
        self.session.add(schedule)
        self.session.commit()