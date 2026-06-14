import os
from collections import defaultdict
from datetime import datetime, timedelta

import pytz
from api.football_api import FApi_Handler
from dotenv import load_dotenv

from configs import NameReplacer
from database_io.connection import get_session
from database_io.repositories.metric_repo import DB_metric
from database_io.repositories.player_repo import DB_player
from database_io.repositories.schedule_repo import DB_schedule
from database_io.repositories.squads_repo import DB_squads

load_dotenv()

nr = NameReplacer()

berlin_tz = pytz.timezone("Europe/Berlin")
time_now = datetime.now(berlin_tz)
time_target = time_now + timedelta(minutes=30)

fapi = FApi_Handler()
elo_version = float(os.environ.get("ELO_VERSION", "0.1"))

player = DB_player()
schedule = DB_schedule()
squads = DB_squads()
metric = DB_metric()

with get_session() as session:
    game_id_list = schedule.games_in_timeframe(session, time_now, time_target)

    for id in game_id_list:
        formations = fapi.get_formation(id)
        start_xis = defaultdict(list)
        for team in formations["response"]:
            team_name = nr.replace_name(team["team"]["name"])
            for p in team["startXI"]:
                if wh_id := player.player_by_fapi_id(session, p) is not None:
                    elo = metric.extract_latest_elo(session, wh_id[0], elo_version)
                    start_xis["team_name"].append(elo)
                else:
                    wh_id = squads.match_players(session, time_now, p["player"]["number"], team_name)
                    if wh_id is None:
                        start_xis["team_name"].append(wh_id)
                    else:
                        elo = metric.extract_latest_elo(session, wh_id, elo_version)
                        start_xis["team_name"].append(elo)
                        player.update_player_fapi_id(session, wh_id, p["player"]["id"])
