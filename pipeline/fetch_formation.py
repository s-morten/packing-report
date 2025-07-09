from api.football_api import FApi_Handler
from database_io.db_handler import DB_handler
from collections import defaultdict
from datetime import datetime, timedelta
import pytz
from configs import NameReplacer

nr = NameReplacer()

berlin_tz = pytz.timezone('Europe/Berlin')
time_now = datetime.now(berlin_tz)
time_target = time_now + timedelta(minutes=30)

fapi = FApi_Handler()
dbh = DB_handler()
# TODO get from config
elo_version = 0.1

# get ids of games in next 30 minutes
game_id_list = dbh.schedule.games_in_timeframe(time_now, time_target)

# get ids of players and match them
for id in game_id_list:
    formations = fapi.get_formation(id)
    start_xis = defaultdict(list)
    for team in formations["response"]:
        team_name = nr.replace_name(team["team"]["name"])
        for player in team["startXI"]:
            if wh_id := dbh.player.player_by_fapi_id(player) is not None:
                elo = dbh.metric.extract_latest_elo(wh_id[0], elo_version)
                start_xis["team_name"].append(elo)
            else:
                wh_id = dbh.squads.match_players(time_now, player["player"]["number"], team_name)
                if wh_id is None:
                    start_xis["team_name"].append(wh_id)
                else:    
                    elo = dbh.metric.extract_latest_elo(wh_id, elo_version)
                    start_xis["team_name"].append(elo)
                    dbh.player.update_player_fapi_id(wh_id, player["player"]["id"])
    
    # id, home, away, league, season, home_elo, away_elo, n_home_miss, n_away_miss, prediction_home, prediction_away, home_goals, away_goals

# predict results and do sth with them, send notification and store results


