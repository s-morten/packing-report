from api.football_api import FApi_Handler
from database_io.faks.schedule import DB_schedule
from datetime import datetime

fapi = FApi_Handler()
dbs = DB_schedule()

# TODO leagues and season to and from config
league_id = 79
season = 2024

# TODO name replacement

data = fapi.get_schedule(league_id, season)
schedule = [[game['fixture']['id'], 
             datetime.strptime(game["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z"),
             game["teams"]["home"]["name"], 
             game["teams"]["away"]["name"]] 
             for game in data["response"]]
for game in schedule:
    dbs.insert_schedule(game[0], game[1], game[2], game[3])