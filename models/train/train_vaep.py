import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd
from data_retrieval.scraper.whoscored_chromeless import WhoScored
from dotenv import load_dotenv
from socceraction.vaep import VAEP
from tqdm import tqdm

load_dotenv()

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


def _build_game_home_team(schedule: pd.DataFrame, team_name_to_id: dict[str, int]) -> dict[int, int]:
    game_home = {}
    for _, row in schedule.iterrows():
        home_id = team_name_to_id.get(row["home_team"], 0)
        game_home[row["game_id"]] = home_id
    return game_home


def train_vaep_model(
    leagues: list[str] | None = None,
    seasons: list[int] | None = None,
    data_dir: Path | str | None = None,
    output_prefix: str = "models/model/vaep",
) -> VAEP:
    if leagues is None:
        leagues = ["GER-Bundesliga"]
        # leagues = ["GER-Bundesliga", "GER-Bundesliga2"]
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
    logger.info("Resolved %d team name→ID mappings", len(team_name_to_id))

    game_home_team = _build_game_home_team(schedule, team_name_to_id)

    logger.info("Fetching SPADL actions ...")
    spadl_all = ws.read_events(output_fmt="spadl")

    game_ids = spadl_all["game_id"].unique()
    logger.info("Loaded %d games, %d actions", len(game_ids), len(spadl_all))

    model = VAEP(nb_prev_actions=3)

    X_list = []
    Y_list = []
    for game_id, actions in tqdm(
        spadl_all.groupby("game_id"),
        total=len(game_ids),
        desc="Preparing features",
    ):
        if actions.empty:
            continue
        game = pd.Series({"home_team_id": game_home_team.get(game_id, 0), "game_id": game_id})
        X = model.compute_features(game, actions)
        Y = model.compute_labels(game, actions)
        X_list.append(X)
        Y_list.append(Y)

    X_all = pd.concat(X_list)
    Y_all = pd.concat(Y_list)
    logger.info("Feature matrix: %s, label matrix: %s", X_all.shape, Y_all.shape)

    logger.info("Training VAEP model (learner=xgboost, val_size=0.25) ...")
    model.fit(X_all, Y_all, learner="xgboost", val_size=0.25)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    model_path = Path(output_prefix + f"_{timestamp}.pkl")
    metadata_path = Path("models/meta") / f"vaep_{timestamp}.json"

    os.makedirs(model_path.parent, exist_ok=True)
    joblib.dump(model, model_path)

    metadata = {
        "model": "vaep",
        "created_utc": datetime.now(UTC).isoformat(),
        "leagues": leagues,
        "seasons": seasons,
        "n_games": len(game_ids),
        "n_actions": len(spadl_all),
        "feature_shape": list(X_all.shape),
        "label_shape": list(Y_all.shape),
        "nb_prev_actions": model.nb_prev_actions,
        "learner": "xgboost",
        "val_size": 0.25,
        "features": [fn.__name__ for fn in model.xfns],
        "labels": [fn.__name__ for fn in model.yfns],
        "n_teams": len(team_name_to_id),
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info("Model saved to %s", model_path)
    logger.info("Metadata saved to %s", metadata_path)

    return model


if __name__ == "__main__":
    train_vaep_model()
