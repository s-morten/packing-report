import utils.football_data_utils as fdu
from api.football_api import FApi_Handler
from database_io.db_handler import DB_handler
from collections import defaultdict
import datetime



time_now = datetime.date.today().strftime("%Y-%m-%d")
fapi = FApi_Handler()
dbh = DB_handler("/home/morten/Develop/packing-report/gde/GDE.db")

# get ids of games in next 30 minutes


# get ids of players and match them
for id in game_list:
    formations = fapi.get_formation(id)
    start_xis = defaultdict(list)
    for team in formations["response"]:
        team_name = fdu.replace_name(team["team"]["name"])
        for player in team["startXI"]:
            wh_id = int(dbh.squads.match_players(time_now, player["player"]["number"], team_name))
            start_xis["team_name"].append(wh_id)
            dbh.player.update_player_fapi_id(wh_id, player["player"]["id"])

# predict results and do sth with them, send notification and store results


