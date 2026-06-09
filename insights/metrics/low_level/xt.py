import logging
import pickle
from pathlib import Path

import numpy as np

from database_io.repositories.metric_repo import DB_metric

logger = logging.getLogger(__name__)
_MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "model"


def _find_latest_model(model_dir, pattern="xt_*.pkl"):
    matches = sorted(model_dir.glob(pattern))
    return matches[-1] if matches else None


class Xt:
    def __init__(self, metric_repo=None, model_path=None):
        self.metric_repo = metric_repo or DB_metric()
        if model_path:
            model_path = Path(model_path)
        else:
            model_path = _find_latest_model(_MODEL_DIR)

        if model_path and model_path.exists():
            with open(model_path, "rb") as f:
                self.xt_model = pickle.load(f)
            logger.info("Loaded xT model from %s", model_path)
        else:
            self.xt_model = None
            logger.warning("No xT model found at %s -- skipping xT metric", _MODEL_DIR)

    def calculate(self, game_facts):
        if self.xt_model is None:
            self.player_xt_mapping = {}
            return

        actions = game_facts.spadl
        if actions.empty:
            self.player_xt_mapping = {}
            return

        xt_values = self.xt_model.rate(actions)
        actions = actions.assign(xt_value=xt_values)

        player_xt_mapping = {}
        for player_id, info in game_facts.players_dict.items():
            player_on = info["on"]
            player_off = info["off"]

            player_actions = actions[
                (actions["player_id"] == player_id)
                & (actions["time_seconds"] / 60 > player_on)
                & (actions["time_seconds"] / 60 < player_off)
                & actions["xt_value"].notna()
            ]

            player_xt_mapping[player_id] = (
                player_actions["xt_value"].sum() if not player_actions.empty else np.float64(0.0)
            )

        self.player_xt_mapping = player_xt_mapping

    def write(self, session, game_id):
        metric_batch = [
            [player, game_id, float(xt_value), "xt"]
            for player, xt_value in self.player_xt_mapping.items()
        ]
        self.metric_repo.insert_batch_metric(session, metric_batch)
