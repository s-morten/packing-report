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

from database_io.connection import get_session
from database_io.repositories.game_repo import DB_games
from game.game_facts import GameFacts
from game.game_metrics import GameMetrics
from game.game_prepare import GamePrepare
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
    prepare = GamePrepare(ws, game, date, league, home)
    prepare.sync()

    facts = GameFacts(ws, game)
    with get_session() as session:
        facts.handle(session)
        GameMetrics().handle(session)
