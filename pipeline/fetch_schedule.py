import sys 
print(sys.path)
from api.football_api import FApi_Handler
from database_io.db_handler import DB_handler
from datetime import datetime
from configs import NameReplacer

fapi = FApi_Handler()
dbh = DB_handler()
nr = NameReplacer()

# TODO leagues and season to and from config
league_id = [79]
season = 2024

dbh.schedule.clear_table()

batch = []
for league in league_id:
    data = fapi.get_schedule(league, season)
    schedule = [[game['fixture']['id'], 
                datetime.strptime(game["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z"),
                nr.replace_name(game["teams"]["home"]["name"]), 
                nr.replace_name(game["teams"]["away"]["name"]),
                league] 
                for game in data["response"]]
    batch.extend(schedule)

dbh.schedule.insert_batch_schedule(batch)