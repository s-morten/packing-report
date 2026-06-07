import os
from pathlib import PosixPath

from dotenv import load_dotenv

load_dotenv()
from scraper.whoscored_chromeless import WhoScored
from tqdm import tqdm

ws = WhoScored(
    leagues=["GER-Bundesliga2", "GER-Bundesliga"],
    seasons=[18, 19, 20, 21, 22],
    data_dir=PosixPath(os.environ.get("SOCCERDATA_DIR", "")),
)
schedule = ws.read_schedule().reset_index()
schedule = schedule.sort_values("date")

import logging

from game.game_timeline import GameTimeline

from database_io.connection import get_session
from database_io.repositories.game_repo import DB_games
from utils.date_utils import to_datetime

logger = logging.getLogger()
logger.disabled = True

games = DB_games()
with get_session() as session:
    processed_games = games.get_all_games(session, 0.1)

schedule = schedule[~schedule["game_id"].isin(processed_games.id)]

for league, game, date, home in tqdm(
    list(
        zip(
            schedule["league"].values, schedule["game_id"].values, schedule["date"].values, schedule["home_team"].values
        )
    ),
    desc="Processing games",
):
    date = to_datetime(date)
    game_timeline = GameTimeline(ws, game, date, league, 0.1, home)
    game_timeline.handle()
