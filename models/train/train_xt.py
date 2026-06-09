import json
import logging
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

from data_retrieval.scraper.whoscored_chromeless import WhoScored
from socceraction.xthreat import ExpectedThreat

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_DEFAULT_DATA_DIR = Path.home() / "soccerdata" / "data" / "WhoScored"


def _build_team_name_to_id(data_dir: Path, schedule: pd.DataFrame) -> dict[str, int]:
    mapping = {}
    for team_name, group in tqdm(
        schedule.groupby("home_team"),
        desc="Building team mapping",
    ):
        row = group.iloc[0]
        json_path = data_dir / "events" / f"{row['league']}_{row['season']}" / f"{row['game_id']}.json"
        try:
            with open(json_path) as f:
                data = json.load(f)
            mapping[team_name] = int(data["home"]["teamId"])
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            logger.warning("Could not read team ID for %s: %s", team_name, e)
    return mapping


def train_xt_model(
    leagues: list[str] | None = None,
    seasons: list[int] | None = None,
    data_dir: Path | str | None = None,
    output_prefix: str = "models/model/xt",
    grid_size: tuple[int, int] = (16, 12),
) -> ExpectedThreat:
    if leagues is None:
        # leagues = ["GER-Bundesliga", "GER-Bundesliga2"]
        leagues = ["GER-Bundesliga"]
    if seasons is None:
        # seasons = [18, 19, 20, 21]
        seasons = [21]

    if data_dir is None:
        data_dir = os.environ.get("SOCCERDATA_DIR", "")
        if data_dir == "":
            data_dir = _DEFAULT_DATA_DIR

    data_dir = Path(data_dir)
    tiers_file = data_dir / "tiers.json"
    if not tiers_file.exists():
        raise FileNotFoundError(
            f"WhoScored cache not found at {data_dir}. "
            "Set SOCCERDATA_DIR to your WhoScored cache directory, "
            "or run pipeline/fetch_data.py first to populate it."
        )

    logger.info("Loading WhoScored data (leagues=%s, seasons=%s)", leagues, seasons)
    ws = WhoScored(leagues=leagues, seasons=seasons, data_dir=data_dir)

    schedule = ws.read_schedule().reset_index()
    logger.info("Schedule: %d games", len(schedule))

    team_name_to_id = _build_team_name_to_id(data_dir, schedule)
    logger.info("Resolved %d team name->ID mappings", len(team_name_to_id))

    logger.info("Fetching SPADL actions ...")
    spadl_all = ws.read_events(output_fmt="spadl")
    game_ids = spadl_all["game_id"].unique()
    logger.info("Loaded %d games, %d actions", len(game_ids), len(spadl_all))

    spadl_clean = spadl_all[spadl_all["end_x"].notna() & spadl_all["end_y"].notna()]
    logger.info("After filtering NaN coordinates: %d actions", len(spadl_clean))

    logger.info("Training xT model (grid=%dx%d, eps=1e-5) ...", *grid_size)
    model = ExpectedThreat(l=grid_size[0], w=grid_size[1])
    model.fit(spadl_clean)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_path = Path(output_prefix + f"_{timestamp}.pkl")
    metadata_path = Path("models/meta") / f"xt_{timestamp}.json"

    os.makedirs(model_path.parent, exist_ok=True)
    os.makedirs(metadata_path.parent, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    metadata = {
        "model": "xt",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "leagues": leagues,
        "seasons": seasons,
        "n_games": len(game_ids),
        "n_actions": len(spadl_all),
        "grid_l": grid_size[0],
        "grid_w": grid_size[1],
        "eps": 1e-5,
        "n_teams": len(team_name_to_id),
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info("Model saved to %s", model_path)
    logger.info("Metadata saved to %s", metadata_path)

    return model


if __name__ == "__main__":
    train_xt_model()
