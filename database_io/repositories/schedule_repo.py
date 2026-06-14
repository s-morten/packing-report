from datetime import datetime

from database_io.models.legacy import Schedule


class DB_schedule:
    def insert_batch_schedule(self, session, schedule: list) -> None:
        batch = [
            Schedule(schedule_id=sid, date_time=dt, home=h, away=a, league=league) for sid, dt, h, a, league in schedule
        ]
        session.add_all(batch)
        session.commit()

    def clear_table(self, session):
        session.query(Schedule).delete()
        session.commit()

    def games_in_timeframe(self, session, time_now: datetime, time_target: datetime) -> list[int]:
        return (
            session.query(Schedule.schedule_id)
            .filter(Schedule.date_time >= time_now, Schedule.date_time <= time_target)
            .all()
        )
