import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from database_io.repositories.metric_repo import DB_metric

logger = logging.getLogger(__name__)
_MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "model"


def _find_latest_model(model_dir, pattern="vaep_*.pkl"):
    matches = sorted(model_dir.glob(pattern))
    return matches[-1] if matches else None


class Vaep:
    def __init__(self, metric_repo=None, model_path=None):
        self.metric_repo = metric_repo or DB_metric()
        model_path = Path(model_path) if model_path else _find_latest_model(_MODEL_DIR)

        if model_path and model_path.exists():
            self.vaep_model = joblib.load(model_path)
            logger.info("Loaded VAEP model from %s", model_path)
        else:
            self.vaep_model = None
            logger.warning("No VAEP model found at %s — skipping VAEP metric", _MODEL_DIR)

    def calculate(self, game_facts):
        if self.vaep_model is None:
            self.player_vaep_mapping = {}
            return

        actions = game_facts.spadl
        if actions.empty:
            self.player_vaep_mapping = {}
            return

        game = pd.Series({"home_team_id": game_facts.home_team_id, "game_id": game_facts.game_id})
        ratings = self.vaep_model.rate(game, actions)

        actions = actions.assign(
            vaep_value=ratings["vaep_value"].values,
            offensive_value=ratings["offensive_value"].values,
            defensive_value=ratings["defensive_value"].values,
        )

        player_vaep_mapping = {}
        for player_id, info in game_facts.players_dict.items():
            player_on = info["on"]
            player_off = info["off"]

            player_actions = actions[
                (actions["player_id"] == player_id)
                & (actions["time_seconds"] / 60 > player_on)
                & (actions["time_seconds"] / 60 < player_off)
            ]

            player_vaep_mapping[player_id] = (
                player_actions["vaep_value"].sum() if not player_actions.empty else np.float64(0.0)
            )

        self.player_vaep_mapping = player_vaep_mapping

    def write(self, session, game_id):
        metric_batch = [
            [player, game_id, float(vaep_value), "vaep"] for player, vaep_value in self.player_vaep_mapping.items()
        ]
        self.metric_repo.insert_batch_metric(session, metric_batch)
