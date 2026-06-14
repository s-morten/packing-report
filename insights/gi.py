import os
from pathlib import PosixPath

from dotenv import load_dotenv

load_dotenv()
from data_retrieval.scraper.whoscored_chromeless import WhoScored
from tqdm import tqdm

ws = WhoScored(
    leagues=["GER-Bundesliga2", "GER-Bundesliga"],
    seasons=[18, 19, 20, 21, 22],
    data_dir=PosixPath(os.environ.get("SOCCERDATA_DIR", "")),
)
schedule = ws.read_schedule().reset_index()
schedule = schedule.sort_values("date")

import logging

from database_io.connection import get_session, init_db
from database_io.repositories.metric_repo import DB_metric
from game.game_facts import GameFacts
from game.game_metrics import GameMetrics
from game.game_prepare import GamePrepare
from utils.date_utils import to_datetime

logger = logging.getLogger()
logger.disabled = True

metrics = DB_metric()
init_db()
with get_session() as session:
    processed_game_ids = metrics.get_processed_game_ids(session)

schedule = schedule[~schedule["game_id"].isin(processed_game_ids)]

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

    facts = GameFacts(ws, game, home)
    with get_session() as session:
        facts.handle(session)
        GameMetrics().handle(session)
