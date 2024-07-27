from api.football_api import FApi_Handler
from database_io.faks.schedule import DB_schedule

fapi = FApi_Handler()
dbs = DB_schedule("/home/morten/Develop/packing-report/GDE.db")

league_id = 79
season = 2024

data = fapi.get_schedule(league_id, season)
schedule = [[game['fixture']['id'], 
             game["fixture"]["date"], 
             game["teams"]["home"]["name"], 
             game["teams"]["away"]["name"]] 
             for game in data["response"]]
for game in schedule:
    dbs.insert_schedule(game[0], game[1], game[2], game[3])