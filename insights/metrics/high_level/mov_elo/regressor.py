import logging
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class MovRegressor:
    def __init__(self, model_path: str | Path):
        with open(model_path, "rb") as f:
            data = pickle.load(f)
        self._model = data["model"]
        self._elo_diff_max = data["elo_diff_max"]
        self._minutes_missed_max = data["minutes_missed_max"]
        logger.info(
            "Loaded MovRegressor (elo_diff_max=%.2f, minutes_missed_max=%.2f)",
            self._elo_diff_max,
            self._minutes_missed_max,
        )

    def predict(self, home: float, rating_diff: float, minutes_missed: float) -> tuple[float, float]:
        elo_diff_scaled = rating_diff / self._elo_diff_max
        min_missed_scaled = minutes_missed / self._minutes_missed_max
        x = np.array([[home, elo_diff_scaled, min_missed_scaled]], dtype=float)
        dist = self._model.pred_dist(x)
        lower = float(dist.ppf(0.25).item())
        upper = float(dist.ppf(0.75).item())
        return lower, upper
