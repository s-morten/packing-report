import sys

from dotenv import load_dotenv

load_dotenv()

print(sys.path)
from datetime import datetime

from api.football_api import FApi_Handler

from configs import NameReplacer
from database_io.connection import get_session
from database_io.repositories.schedule_repo import DB_schedule

fapi = FApi_Handler()
nr = NameReplacer()

league_id = [79]
season = 2024

schedule = DB_schedule()
with get_session() as session:
    schedule.clear_table(session)

    batch = []
    for league in league_id:
        data = fapi.get_schedule(league, season)
        schedule_data = [
            [
                game["fixture"]["id"],
                datetime.strptime(game["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z"),
                nr.replace_name(game["teams"]["home"]["name"]),
                nr.replace_name(game["teams"]["away"]["name"]),
                league,
            ]
            for game in data["response"]
        ]
        batch.extend(schedule_data)

    schedule.insert_batch_schedule(session, batch)
