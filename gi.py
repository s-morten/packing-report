from scraper.whoscored_chromeless import WhoScored
from metrics.mov_elo.regressor import MOV_Regressor
from pathlib import PosixPath
import pandas as pd
import numpy as np

import os
import cProfile
from tqdm import tqdm
# profiler = Profiler()


ws = WhoScored(
    leagues=["GER-Bundesliga2", "GER-Bundesliga"], # "GER-Bundesliga2", "ENG-Premier League", "ESP-La Liga", 
    seasons=[18, 19, 20, 21, 22], # 15, 16, 17, 18, 19, 20, 21, 22, 23
    #no_cache=False,
    #no_store=False,
    data_dir=PosixPath("/home/morten/Develop/Open-Data/soccerdata"),
    # path_to_browser="/usr/bin/chromium",
    #headless=True,
)
schedule = ws.read_schedule().reset_index()

schedule = schedule.sort_values("date")

from utils.date_utils import to_datetime
from database_io.db_handler import DB_handler
from game.game_timeline import GameTimeline

import logging
logger = logging.getLogger()
logger.disabled = True
dbh = DB_handler()
schedule = ws.read_schedule().reset_index()
schedule = schedule.sort_values("date")
mov_regressor = MOV_Regressor()

# profiler.start()
# code you want to profile
processed_games = dbh.games.get_all_games(0.1)

schedule = schedule[~schedule["game_id"].isin(processed_games.id)]

for league, game, date, home in tqdm(list(zip(schedule["league"].values, 
                                              schedule["game_id"].values, 
                                              schedule["date"].values, 
                                              schedule["home_team"].values)), 
                                     desc="Processing games"):
    date = to_datetime(date)
    game_timeline = GameTimeline(ws, game, date, league, dbh, 0.1, home, mov_regressor)
    # game_timeline.predict()
    game_timeline.handle()

# profiler.stop()
# profiler.print()