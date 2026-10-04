import argparse
import logging
import os
from pathlib import PosixPath

from data_retrieval.scraper.whoscored_chromeless import WhoScored
from dotenv import load_dotenv
from game.game_facts import GameFacts
from game.game_metrics import GameMetrics
from game.game_prepare import GamePrepare
from tqdm import tqdm

from database_io.connection import get_session, init_db
from database_io.repositories.metric_repo import DB_metric
from utils.date_utils import to_datetime

load_dotenv()

_DEFAULT_LEAGUES = ["GER-Bundesliga2", "GER-Bundesliga"]
_DEFAULT_SEASONS = [18, 19, 20, 21, 22]


def parse_args():
    parser = argparse.ArgumentParser(description="Compute per-game metrics for every unprocessed match")
    parser.add_argument("--leagues", nargs="+", default=_DEFAULT_LEAGUES)
    parser.add_argument("--seasons", nargs="+", type=int, default=_DEFAULT_SEASONS)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess games that already have PLAYER_GAME_METRIC rows",
    )
    parser.add_argument("--limit", type=int, default=None, help="Stop after N games (smoke tests)")
    return parser.parse_args()


def main():
    args = parse_args()

    ws = WhoScored(
        leagues=args.leagues,
        seasons=args.seasons,
        data_dir=PosixPath(os.environ.get("SOCCERDATA_DIR", "")),
    )
    schedule = ws.read_schedule().reset_index()
    schedule = schedule.sort_values("date")

    logger = logging.getLogger()
    logger.disabled = True

    metrics = DB_metric()
    init_db()
    if args.force:
        processed_game_ids = set()
        logger.warning("--force: reprocessing every game in scope, ignoring PLAYER_GAME_METRIC")
    else:
        with get_session() as session:
            processed_game_ids = metrics.get_processed_game_ids(session)

    schedule = schedule[~schedule["game_id"].isin(processed_game_ids)]
    if args.limit is not None:
        schedule = schedule.head(args.limit)

    for league, game, date, home in tqdm(
        list(
            zip(
                schedule["league"].values,
                schedule["game_id"].values,
                schedule["date"].values,
                schedule["home_team"].values,
                strict=True,
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
            GameMetrics().handle(session, facts, date, league)


if __name__ == "__main__":
    main()
