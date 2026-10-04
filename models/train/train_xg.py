"""Train the custom xG model used to price every shot in the xT pipeline.

What this produces
------------------
``models/model/xg_<UTC timestamp>.pkl`` -- a plain dict holding the fitted
:class:`xgboost.XGBClassifier`, the feature layout it was fitted on, and a smoothed penalty rate.
:mod:`metrics.low_level.xg.XgRegressor` loads it and satisfies the ``predict`` contract that
:func:`metrics.low_level.xt.rate_shots` calls.

How the model is judged
-----------------------
On **out-of-fold** probabilities from a ``GroupKFold`` split **by game**, never a random row split:
several shots in one match share the same tactical context, so a row-level split would let a shot
be scored against a model that had already seen its own chances from the same passage of play.

The headline metric is **log loss**, not AUC. xT subtracts the cell value from ``p_goal`` and
requires a whole possession to telescope against the goals actually scored, which only holds if the
number is a genuine probability. A model that merely *ranks* chances correctly can be badly
miscalibrated and would quietly break that identity. Brier score and AUC are reported alongside, and
so is a decile reliability table, because calibration is the property under test rather than a
formality.

The number to beat is the placeholder this model replaces: the xT model's own cell-based scoring
probability, looked up at each shot's grid cell. If the tree cannot beat that on log loss, it has
not earned its place in the pipeline.

Ablation
--------
Every feature set is fitted and scored before the final model is chosen, so the lookback block
(assist type, rebounds, pressure, workload) is kept only because it measurably pays for itself.
"""

import json
import logging
import os
import pickle
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
from data_retrieval.scraper.whoscored_chromeless import WhoScored
from dotenv import load_dotenv
from metrics.low_level.xg import (
    FEATURE_SETS,
    build_features,
    goal_mask,
    non_penalty_shot_mask,
    penalty_mask,
    shot_mask,
    smoothed_rate,
)
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from tqdm import tqdm
from xgboost import XGBClassifier

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_DEFAULT_DATA_DIR = Path.home() / "soccerdata" / "data" / "WhoScored"

# ~8,000 shots and ~850 goals. A grid this shallow and this heavily regularised is the honest search
# space at that sample size: deeper trees memorise, and LightGBM/CatBoost would not change the fact
# that the binding constraint here is data, not learner capacity.
_SHARED_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "learning_rate": 0.05,
    "n_estimators": 2000,
    "early_stopping_rounds": 50,
    "random_state": 42,
    "n_jobs": -1,
}
_PARAM_GRID = (
    {"max_depth": 2, "min_child_weight": 20.0, "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 5.0},
    {"max_depth": 3, "min_child_weight": 20.0, "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 5.0},
    {"max_depth": 3, "min_child_weight": 40.0, "subsample": 0.7, "colsample_bytree": 0.7, "reg_lambda": 10.0},
    {"max_depth": 4, "min_child_weight": 40.0, "subsample": 0.7, "colsample_bytree": 0.7, "reg_lambda": 15.0},
)


def _score(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    return {
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "brier": float(brier_score_loss(labels, probabilities)),
        "auc": float(roc_auc_score(labels, probabilities)),
    }


def _reliability_table(labels: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> list[dict]:
    """Mean predicted vs observed rate per equal-width probability decile."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    which = np.clip(np.digitize(probabilities, edges[1:-1], right=False), 0, bins - 1)
    rows = []
    for b in range(bins):
        member = which == b
        if not member.any():
            continue
        rows.append(
            {
                "bin": b,
                "n": int(member.sum()),
                "mean_predicted": float(probabilities[member].mean()),
                "observed_rate": float(labels[member].mean()),
            }
        )
    return rows


def _cross_validate(
    features: pd.DataFrame,
    labels: np.ndarray,
    groups: np.ndarray,
    params: dict,
    n_splits: int,
) -> tuple[np.ndarray, list[int]]:
    """Out-of-fold probabilities, with early stopping held clear of the scored fold.

    Early stopping needs a validation set, and using the scored fold for it would leak the answer
    into the number being reported. Each outer training fold is therefore split again *by game* to
    carve out a validation slice, so no game contributes to both.
    """
    out_of_fold = np.full(len(features), np.nan)
    best_iterations: list[int] = []

    for train_idx, test_idx in GroupKFold(n_splits=n_splits).split(features, labels, groups):
        inner = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
        fit_idx, stop_idx = next(inner.split(features.iloc[train_idx], labels[train_idx], groups[train_idx]))
        model = XGBClassifier(**_SHARED_PARAMS, **params)
        model.fit(
            features.iloc[train_idx[fit_idx]],
            labels[train_idx[fit_idx]],
            eval_set=[(features.iloc[train_idx[stop_idx]], labels[train_idx[stop_idx]])],
            verbose=False,
        )
        out_of_fold[test_idx] = model.predict_proba(features.iloc[test_idx])[:, 1]
        best_iterations.append(int(model.best_iteration) + 1)

    if np.isnan(out_of_fold).any():
        raise RuntimeError("cross-validation left some rows without an out-of-fold probability")
    return out_of_fold, best_iterations


def _xt_surface_probability(spadl: pd.DataFrame, positions: np.ndarray, xt_model) -> np.ndarray:
    """The placeholder this model replaces: xT's own scoring probability at the shot's grid cell.

    Cell mapping mirrors :func:`metrics.low_level.xt._shot_cells`, including the row flip that puts
    row 0 at the far touchline.
    """
    from socceraction.spadl import config as spadl_config

    start_x = spadl["start_x"].to_numpy(dtype=float)[positions]
    start_y = spadl["start_y"].to_numpy(dtype=float)[positions]
    column = np.clip((start_x / spadl_config.field_length * xt_model.l).astype(int), 0, xt_model.l - 1)
    row = np.clip((start_y / spadl_config.field_width * xt_model.w).astype(int), 0, xt_model.w - 1)
    return np.asarray(xt_model.scoring_prob_matrix, dtype=float)[xt_model.w - 1 - row, column]


def _load_latest_xt_model(model_dir: Path):
    matches = sorted(model_dir.glob("xt_*.pkl"))
    if not matches:
        return None
    with open(matches[-1], "rb") as f:
        return pickle.load(f)


def _assemble_samples(
    spadl_all: pd.DataFrame, xt_model
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray | None, dict]:
    """Feature matrix, labels, game groups and the xT-surface baseline for every non-penalty shot.

    Features are built **one game at a time**. A single concatenated frame would let the lookback
    window of a shot early in a match reach back into the previous match, and the pressure counts
    would be silently meaningless. :func:`metrics.low_level.xg.build_features` indexes
    positionally, so a per-game sub-frame is safe even though its labels are not a ``RangeIndex``.

    The xT-surface baseline is gathered in the same loop, off each game's own frame, so it cannot
    drift out of alignment with the labels no matter how the games are ordered in ``spadl_all``.
    """
    frames = []
    labels = []
    groups = []
    surface = [] if xt_model is not None else None
    for _, game_frame in tqdm(spadl_all.groupby("game_id", sort=False), desc="Building shot features"):
        selected = non_penalty_shot_mask(game_frame)
        if not selected.any():
            continue
        frames.append(build_features(game_frame, "full"))
        labels.append(goal_mask(game_frame)[selected])
        groups.append(np.full(int(selected.sum()), int(game_frame["game_id"].iloc[0])))
        if surface is not None:
            cell_probability = _xt_surface_probability(game_frame, np.flatnonzero(selected), xt_model)
            surface.append(np.clip(cell_probability, 1e-6, 1 - 1e-6))

    if not frames:
        raise RuntimeError("No shots found in the requested scope -- check the leagues/seasons arguments")

    features = pd.concat(frames)
    return (
        features,
        np.concatenate(labels).astype(int),
        np.concatenate(groups).astype(int),
        None if surface is None else np.concatenate(surface),
        {
            "n_games": int(spadl_all["game_id"].nunique()),
            "n_shots_total": int(shot_mask(spadl_all).sum()),
            "n_penalties": int(penalty_mask(spadl_all).sum()),
        },
    )


def train_xg_model(
    leagues: list[str] | None = None,
    seasons: list[int] | None = None,
    data_dir: Path | str | None = None,
    output_prefix: str = "models/model/xg",
    n_splits: int = 5,
    feature_sets: tuple[str, ...] = ("base", "full"),
) -> XGBClassifier:
    if leagues is None:
        leagues = ["GER-Bundesliga"]
    if seasons is None:
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
    spadl_all = ws.read_events(output_fmt="spadl")
    logger.info("Loaded %d games, %d actions", spadl_all["game_id"].nunique(), len(spadl_all))

    model_dir = Path(output_prefix).parent
    features, labels, groups, surface, counts = _assemble_samples(spadl_all, _load_latest_xt_model(model_dir))
    logger.info(
        "Shot sample: %d non-penalty shots (%d goals) from %d games; %d penalties excluded",
        len(features),
        int(labels.sum()),
        len(set(groups)),
        counts["n_penalties"],
    )

    # The ablation is nested rather than separate: "full" is a strict superset of "base", so scoring
    # a column subset of the same matrix isolates the lookback block exactly.
    evaluated: dict[str, dict] = {}
    for name in feature_sets:
        columns = list(FEATURE_SETS[name])
        subset = features[columns]
        logger.info(
            "Fitting feature_set=%r (%d features) over %d configurations ...",
            name,
            len(columns),
            len(_PARAM_GRID),
        )
        trials = []
        for params in _PARAM_GRID:
            oof, best_iterations = _cross_validate(subset, labels, groups, params, n_splits)
            trial = {"params": params, "n_rounds": int(np.median(best_iterations)), **_score(labels, oof)}
            logger.info(
                "  depth=%d child_weight=%.0f lambda=%.0f -> log_loss=%.5f brier=%.5f auc=%.4f rounds=%d",
                params["max_depth"],
                params["min_child_weight"],
                params["reg_lambda"],
                trial["log_loss"],
                trial["brier"],
                trial["auc"],
                trial["n_rounds"],
            )
            trials.append({"params": params, "oof": oof, **trial})
        best = min(trials, key=lambda trial: trial["log_loss"])
        evaluated[name] = {
            "features": subset,
            "oof": best["oof"],
            "params": best["params"],
            "n_rounds": best["n_rounds"],
            "score": _score(labels, best["oof"]),
        }
        logger.info("  -> best %r: log_loss=%.5f", name, best["log_loss"])

    if "base" in evaluated and "full" in evaluated:
        delta = evaluated["base"]["score"]["log_loss"] - evaluated["full"]["score"]["log_loss"]
        verdict = "earns its place" if delta > 0 else "does NOT earn its place"
        logger.info("Ablation: lookback features change log loss by %+.5f -- %s", delta, verdict)

    # The winner is the best feature set that actually won; ties go to the smaller feature set.
    chosen = min(evaluated, key=lambda name: (evaluated[name]["score"]["log_loss"], len(FEATURE_SETS[name])))
    winner = evaluated[chosen]
    logger.info(
        "Selected feature_set=%r (log_loss=%.5f, auc=%.4f)", chosen, winner["score"]["log_loss"], winner["score"]["auc"]
    )

    baseline_scores = {"league_constant": _score(labels, np.full(len(labels), labels.mean()))}
    if surface is not None:
        baseline_scores["xt_surface"] = _score(labels, surface)
        logger.info(
            "Baseline xT surface: log_loss=%.5f (tree %+.5f)",
            baseline_scores["xt_surface"]["log_loss"],
            baseline_scores["xt_surface"]["log_loss"] - winner["score"]["log_loss"],
        )
    else:
        logger.warning("No xT model found -- skipping the xT-surface baseline")

    final = XGBClassifier(
        **{**_SHARED_PARAMS, **winner["params"], "n_estimators": winner["n_rounds"], "early_stopping_rounds": None}
    )
    final.fit(winner["features"], labels, verbose=False)

    penalty_mask_all = penalty_mask(spadl_all)
    penalty_goals = int(goal_mask(spadl_all)[penalty_mask_all].sum())
    penalty_p_goal = smoothed_rate(penalty_goals, int(penalty_mask_all.sum()))
    logger.info("Penalties: %d/%d -> p_goal=%.4f", penalty_goals, int(penalty_mask_all.sum()), penalty_p_goal)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    model_path = Path(output_prefix + f"_{timestamp}.pkl")
    metadata_path = Path("models/meta") / f"xg_{timestamp}.json"

    os.makedirs(model_path.parent, exist_ok=True)
    os.makedirs(metadata_path.parent, exist_ok=True)
    artifact = {
        "model": final,
        "feature_set": chosen,
        "feature_names": list(FEATURE_SETS[chosen]),
        "penalty_p_goal": penalty_p_goal,
        "n_train": int(len(features)),
    }
    with open(model_path, "wb") as f:
        pickle.dump(artifact, f)

    metadata = {
        "model": "xg",
        "created_utc": datetime.now(UTC).isoformat(),
        "leagues": leagues,
        "seasons": seasons,
        "n_games": counts["n_games"],
        "n_actions": len(spadl_all),
        "n_shots_total": counts["n_shots_total"],
        "n_shots_trained": int(len(features)),
        "n_goals_trained": int(labels.sum()),
        "feature_set": chosen,
        "feature_names": list(FEATURE_SETS[chosen]),
        "hyperparameters": {**_SHARED_PARAMS, **winner["params"], "n_estimators": winner["n_rounds"]},
        "out_of_fold": winner["score"],
        "baselines": baseline_scores,
        "ablation": {name: evaluated[name]["score"] for name in evaluated},
        "reliability": _reliability_table(labels, winner["oof"]),
        "penalty": {
            "n_shots": int(penalty_mask_all.sum()),
            "n_goals": penalty_goals,
            "p_goal": penalty_p_goal,
        },
        "xgboost_version": xgb.__version__,
        "sklearn_version": sklearn.__version__,
        "note": (
            "goalMouthY / goalMouthZ are the strongest known shot predictors and are absent here: the raw "
            "WhoScored feed carries them but socceraction's SPADL conversion drops them. See the module "
            "docstring of metrics/low_level/xg.py for the route in."
        ),
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info("Model saved to %s", model_path)
    logger.info("Metadata saved to %s", metadata_path)

    return final


if __name__ == "__main__":
    train_xg_model()
