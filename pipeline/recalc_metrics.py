import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

import soccerdata as sd
from dotenv import load_dotenv

from database_io.connection import get_session, init_db
from database_io.models.metric import PlayerGameMetric

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_DEFAULT_DATA_DIR = Path.home() / "soccerdata" / "data" / "WhoScored"
_DEFAULT_LEAGUES = ["GER-Bundesliga2", "GER-Bundesliga"]


def season_game_ids(ws: sd.WhoScored, season: str) -> list[int]:
    schedule = ws.read_schedule().reset_index()
    return sorted(schedule.loc[schedule["season"] == season, "game_id"].unique().tolist())


def delete_game_metrics(session, game_ids: list[int]) -> int:
    return (
        session.query(PlayerGameMetric).filter(PlayerGameMetric.game_id.in_(game_ids)).delete(synchronize_session=False)
    )


def main():
    parser = argparse.ArgumentParser(
        description="Delete PLAYER_GAME_METRIC rows for one season so it gets recalculated by insights/gi.py"
    )
    parser.add_argument("--season", required=True, help="Season to recalculate, e.g. 1819 or 18")
    parser.add_argument(
        "--leagues",
        nargs="+",
        default=_DEFAULT_LEAGUES,
        help="Leagues to include (default: GER-Bundesliga2 GER-Bundesliga)",
    )
    parser.add_argument("--run", action="store_true", help="Run insights/gi.py after deleting the rows")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    load_dotenv()
    data_dir = Path(os.environ.get("SOCCERDATA_DIR", str(_DEFAULT_DATA_DIR)))
    ws = sd.WhoScored(leagues=args.leagues, seasons=[args.season], data_dir=data_dir)
    season = ws.seasons[0]

    game_ids = season_game_ids(ws, season)
    if not game_ids:
        raise SystemExit(f"No games found for season {season} in {args.leagues}")

    init_db()
    with get_session() as session:
        count = session.query(PlayerGameMetric).filter(PlayerGameMetric.game_id.in_(game_ids)).count()

    logger.info("Season %s: %d games, %d existing metric rows", season, len(game_ids), count)
    if not args.yes:
        answer = input(f"Delete {count} metric rows and recalculate? [y/N] ")
        if not answer.strip().lower().startswith("y"):
            raise SystemExit("Aborted")

    with get_session() as session:
        deleted = delete_game_metrics(session, game_ids)
    logger.info("Deleted %d metric rows", deleted)

    if args.run:
        logger.info("Running insights/gi.py ...")
        subprocess.run([sys.executable, "insights/gi.py"], check=True)


if __name__ == "__main__":
    main()
