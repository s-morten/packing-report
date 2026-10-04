"""Custom xG model: learned shot pricing for the xT pipeline.

Why this module exists
----------------------
:func:`metrics.low_level.xt.rate_shots` values every shot in a match as ``p_goal - xT[cell]``.
Until now ``p_goal`` came from the xT model's own cell-based scoring-probability surface, which
sees only *where* on the 16x12 grid a shot was taken. That surface cannot tell a well-placed
header from a hopeful thirty-yard swinger out of the same cell, and it knows nothing at all about
body part, assist type, rebounds or defensive pressure.

``XgRegressor`` replaces it with a gradient-boosted tree trained by ``models/train/train_xg.py``
and stored as ``models/model/xg_*.pkl``. It feeds three things downstream: the per-player ``xt``
metric, the xTPM dependent variable ``net_xt_per90``, and the shot component of every possession's
xT total.

The predict contract
--------------------
:meth:`XgRegressor.predict` is handed the **whole match frame**, not a pre-filtered shot subset.
That is deliberate: the lookback features below (assist type, rebound flag, defensive pressure,
actions in the possession) are only defined relative to the actions that *preceded* the shot, so
shot rows on their own cannot carry them. ``predict`` masks the shots itself and returns one
probability per shot row **in frame order**, which is the contract ``rate_shots`` validates against
``shot_mask.sum()``.

Feature tiers
-------------
``base`` is everything derivable from the shot row alone; ``full`` adds the lookback block.
``models/train/train_xg.py`` fits both and reports the difference, so the lookback features are
kept only if they measurably pay for themselves.

Ball height: not available
------------------------
There is **no ball-height data in this feed at all** -- no ``z``, no ``height``, on any event type,
verified across a full season. Nothing says whether a shot was a volley or struck off a settled ball
at ankle height, other than the body part, which only distinguishes header from foot.

What stands in for it is :data:`FEATURE_NAMES_LOOKBACK`'s ``time_since_assist``. In SPADL a shot's
``start`` *is* the previous action's ``end``, so the gap in seconds between the two rows says whether
the ball was still travelling when it was struck. The timestamps are only whole seconds, but that is
enough to separate a first-time shot from a set-up one, and the separation is dramatic: a shot struck
within one second of the assist converts at **0.7%**, at two seconds **13.0%**, at three seconds
**17.8%**. This is the single most valuable feature in the model, worth more than everything else in
the lookback block combined.

Those figures were checked for the obvious artefact -- blocked shots being timestamped at the moment
of contact rather than of the attempt, which would pile them into the zero-second bucket. They are
not: the blocked share is flat across gap buckets (53-68%), and the effect holds among on-target foot
shots from inside the box (0.0% / 13.0% / 15.9% / 23.7% / 28.3%). It also reproduces from an
independent derivation, the vendor's own ``relatedEventId`` assist link rather than the SPADL row
order.

The genuine fix would still be a height or volley flag from the feed. On other WhoScored versions the
``shotAssistType`` field carries ``Volley`` and ``Header``; it is absent from this one.

Deliberately absent
-------------------
``goalMouthY`` / ``goalMouthZ`` -- **the strongest single predictor of a goal, and the one this model
is most conspicuously missing.** Every published xG model carries them, because where the ball is
aimed inside the goalmouth dwarfs every other feature: a shot on target from the six-yard box aimed
at the top corner converts several times more often than the same shot aimed at the near post.

The raw WhoScored event feed *does* supply them (top-level ``goalMouthY`` / ``goalMouthZ`` on every
shot, mirrored by qualifiers 102 / 103), but socceraction's WhoScored-to-SPADL conversion drops
both, so they never reach ``game_facts.spadl`` and are therefore unreachable from a SPADL frame. The
route in is to read the raw events alongside SPADL in ``train_xg.py``, key the two frames on
``original_event_id`` (which SPADL does preserve), and carry the pair through as two more columns.
That is deliberately left out here rather than faked: a shot's ``end_x`` / ``end_y`` is *not* a
usable substitute, since for open-play shots it spans the entire pitch (the conversion falls back to
the next action's location) and only collapses onto the goalmouth for free kicks and penalties.
Doing this properly also unlocks the other discarded shot qualifiers -- blocked coordinates and the
defensive zone the shot was struck from.
"""

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from socceraction.spadl import config as spadl_config

logger = logging.getLogger(__name__)

# Pitch geometry. socceraction exposes the pitch but not the goal, so the posts are derived here.
FIELD_LENGTH = float(spadl_config.field_length)
FIELD_WIDTH = float(spadl_config.field_width)
GOAL_CENTRE_X = FIELD_LENGTH
GOAL_CENTRE_Y = FIELD_WIDTH / 2
GOAL_HALF_WIDTH = 7.32 / 2

# A defender is treated as "pressing" the shot if the ball was within this radius of it in the
# handful of actions leading up to it. 12 m is roughly the radius a keeper would sweep.
PRESSURE_RADIUS = 12.0
# How many actions back to look. Set to the possession cap so the window is, in effect, "the
# current spell": the SPADL frame interleaves both teams chronologically, so this is a handful of
# seconds of play rather than twenty actions of one side.
PRESSURE_LOOKBACK = 20
# Possession length is capped so a long spell of sterile possession cannot dominate the axis.
POSSESSION_CAP = 20
# Seconds between the assist and the shot, capped. A gap of zero or one second means the ball was
# still travelling when it was struck -- a volley or a first-time shot. See
# :data:`FEATURE_NAMES_LOOKBACK` for why this is the strongest lookback feature in the model.
ASSIST_GAP_CAP = 10.0
# A player whose first recorded touch is later than this came on as a substitute.
SUBSTITUTE_THRESHOLD_MINUTES = 15.0

SHOT_TYPE_ID = spadl_config.actiontypes.index("shot")
PENALTY_TYPE_ID = spadl_config.actiontypes.index("shot_penalty")
FREEKICK_TYPE_ID = spadl_config.actiontypes.index("shot_freekick")
GOAL_RESULT_ID = spadl_config.results.index("success")

SHOT_TYPE_IDS = (SHOT_TYPE_ID, PENALTY_TYPE_ID, FREEKICK_TYPE_ID)

# ``assist_type`` is a categorical, one-hot encoded. The vocabulary is fixed in code rather than
# learned from the data so that training and inference cannot drift, and deliberately spans every
# action type (even types that essentially never precede a shot) so that no category is chosen by
# looking at which ones happen to correlate with goals in the training sample.
ASSIST_LOOSE_BALL = "loose_ball"
ASSIST_NONE = "none"
ASSIST_VOCABULARY = tuple(spadl_config.actiontypes) + (ASSIST_LOOSE_BALL, ASSIST_NONE)
ASSIST_COLUMNS = tuple(f"assist_{name}" for name in ASSIST_VOCABULARY)

# ``loose_ball`` means the action immediately before the shot belonged to the *other* team: a
# keeper save, a blocked shot, or a turnover the event feed never recorded. It is a real, sizeable
# category (roughly a fifth of open-play shots) and a genuinely harder chance, so it is labelled
# rather than papered over by inventing an assist further back.
FEATURE_NAMES_BASE = (
    "start_x",
    "start_y",
    "dist_to_goal_centre",
    "dist_to_near_post",
    "dist_to_far_post",
    "angle_to_goal",
    "abs_y_from_centre",
    "bodypart_id",
    "is_free_kick",
)
FEATURE_NAMES_LOOKBACK = (
    *ASSIST_COLUMNS,
    "assist_travel_dist",
    "assist_failed",
    # The strongest lookback feature by a wide margin, and the closest this model comes to knowing
    # the ball's height at the moment of the shot -- see the module docstring. A shot struck within
    # a second of the assist was taken on the move, with the ball still in flight; one struck three
    # or four seconds later was set up. Over the 2021/22 Bundesliga that single column moves the
    # out-of-fold log loss from 0.3037 to 0.2695 -- thirteen times what the entire rest of this block
    # is worth. The effect survives restricting to on-target foot shots from inside the box
    # (0.0% / 13.0% / 15.9% / 23.7% / 28.3% by gap bucket), so it is not an artefact of how blocked
    # shots are timestamped.
    "time_since_assist",
    "actions_since_team_change",
    "defenders_within_radius",
    "teammates_within_radius",
    "minutes_on_pitch",
    "is_substitute",
)
FEATURE_SETS = {
    "base": FEATURE_NAMES_BASE,
    "full": FEATURE_NAMES_BASE + FEATURE_NAMES_LOOKBACK,
}

_REQUIRED_COLUMNS = (
    "game_id",
    "period_id",
    "time_seconds",
    "team_id",
    "player_id",
    "start_x",
    "start_y",
    "end_x",
    "end_y",
    "type_id",
    "result_id",
    "bodypart_id",
)


def shot_mask(actions: pd.DataFrame) -> np.ndarray:
    """Boolean mask over ``actions`` selecting every shot row, penalties included."""
    return actions["type_id"].isin(SHOT_TYPE_IDS).to_numpy()


def penalty_mask(actions: pd.DataFrame) -> np.ndarray:
    """Boolean mask over ``actions`` selecting penalty shots only."""
    return (actions["type_id"] == PENALTY_TYPE_ID).to_numpy()


def non_penalty_shot_mask(actions: pd.DataFrame) -> np.ndarray:
    """Boolean mask over ``actions`` selecting the shots the tree is trained on.

    Penalties are excluded by design. A conversion rate of 83% over 84 observations cannot be
    learned by a tree that sees ~850 goals in total, and letting it try costs calibration across
    every other shot. :class:`XgRegressor` emits a separately smoothed constant for them instead.
    """
    return shot_mask(actions) & ~penalty_mask(actions)


def goal_mask(actions: pd.DataFrame) -> np.ndarray:
    """Boolean mask over ``actions`` selecting rows that resulted in a goal."""
    return (actions["result_id"] == GOAL_RESULT_ID).to_numpy()


def match_minutes(actions: pd.DataFrame) -> pd.Series:
    """Match-absolute minute of every action. Same convention as :func:`metrics.low_level.xt.match_minutes`."""
    return (actions["period_id"] - 1) * 45 + actions["time_seconds"] / 60


def _empty_features(feature_set: str) -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=float) for name in FEATURE_SETS[feature_set]})


def _geometry(start_x: np.ndarray, start_y: np.ndarray) -> dict[str, np.ndarray]:
    to_centre_x = GOAL_CENTRE_X - start_x
    to_centre_y = np.abs(start_y - GOAL_CENTRE_Y)
    return {
        "start_x": start_x,
        "start_y": start_y,
        "dist_to_goal_centre": np.hypot(to_centre_x, to_centre_y),
        # Which corner matters as much as how far away it is, so both posts get their own column
        # rather than being collapsed into a single distance.
        "dist_to_near_post": np.hypot(to_centre_x, np.abs(start_y - (GOAL_CENTRE_Y - GOAL_HALF_WIDTH))),
        "dist_to_far_post": np.hypot(to_centre_x, np.abs(start_y - (GOAL_CENTRE_Y + GOAL_HALF_WIDTH))),
        # The angle a keeper has to cover. Saturates to pi/2 on the byline, which is correct: from
        # there the goalmouth fills the whole field of view.
        "angle_to_goal": np.arctan2(2 * GOAL_HALF_WIDTH, np.maximum(to_centre_x, 1e-6)),
        "abs_y_from_centre": to_centre_y,
    }


def _predecessor(actions: pd.DataFrame, positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The action that put the ball where each shot was struck from.

    In SPADL a shot's ``start`` **is** the previous action's ``end``, so the immediately preceding
    row is the ball carrier: measured over 1,476 open-play shots in the 2021/22 Bundesliga, 98.9% of
    shots chain to the row directly above them. The exception is a genuine possession change the
    feed does not record (keeper save, blocked shot, deflection), which is why the same-team test
    matters more than the distance.

    Returns the predecessor's ``type_id`` (``-1`` where the shot is the first row of the frame) and
    whether that predecessor was on the shooting team's side.
    """
    types = actions["type_id"].to_numpy()
    teams = actions["team_id"].to_numpy()
    has_predecessor = positions > 0
    previous = np.where(has_predecessor, positions - 1, 0)
    predecessor_types = np.where(has_predecessor, types[previous], -1)
    same_team = has_predecessor & (teams[previous] == teams[positions])
    return predecessor_types.astype(int), same_team


def _actions_since_team_change(actions: pd.DataFrame, positions: np.ndarray) -> np.ndarray:
    """Actions by the shooting side since any other side last touched the ball, capped.

    A cheap possession-length proxy: the frame interleaves both teams, so the most recent row
    belonging to a different side marks where the current spell began.
    """
    teams = actions["team_id"].to_numpy()
    change = np.empty(len(teams), dtype=bool)
    change[0] = True
    change[1:] = teams[1:] != teams[:-1]
    last_change = np.maximum.accumulate(np.where(change, np.arange(len(teams)), 0))
    return np.minimum(positions - last_change[positions], POSSESSION_CAP).astype(float)


def _pressure_counts(
    actions: pd.DataFrame,
    positions: np.ndarray,
    shot_x: np.ndarray,
    shot_y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Opponents and teammates whose last known ball position was within :data:`PRESSURE_RADIUS`.

    Counted over the :data:`PRESSURE_LOOKBACK` actions before the shot, using each action's ``end``
    coordinate as the best available estimate of where the ball actually was. Actions with an
    unrecorded end position are skipped rather than counted as zero.
    """
    teams = actions["team_id"].to_numpy()
    end_x = actions["end_x"].to_numpy(dtype=float)
    end_y = actions["end_y"].to_numpy(dtype=float)

    defenders = np.zeros(len(positions), dtype=float)
    teammates = np.zeros(len(positions), dtype=float)
    for k, i in enumerate(positions):
        window = slice(max(0, i - PRESSURE_LOOKBACK), i)
        if window.start >= window.stop:
            continue
        distance = np.hypot(end_x[window] - shot_x[k], end_y[window] - shot_y[k])
        usable = np.isfinite(distance)
        near = usable & (distance < PRESSURE_RADIUS)
        same_side = teams[window] == teams[i]
        defenders[k] = np.count_nonzero(near & ~same_side)
        teammates[k] = np.count_nonzero(near & same_side)
    return defenders, teammates


def build_features(actions: pd.DataFrame, feature_set: str = "full") -> pd.DataFrame:
    """One feature row per non-penalty shot in ``actions``.

    ``actions`` is the **whole match frame**, not a shot subset -- the lookback features need it.
    The result is indexed like ``actions``, contains only non-penalty shots, and has exactly the
    columns of ``FEATURE_SETS[feature_set]`` in that order, so the trainer and
    :meth:`XgRegressor.predict` cannot disagree about the feature layout.
    """
    if feature_set not in FEATURE_SETS:
        raise ValueError(f"Unknown feature_set {feature_set!r}; expected one of {sorted(FEATURE_SETS)}")
    missing = [column for column in _REQUIRED_COLUMNS if column not in actions.columns]
    if missing:
        raise ValueError(f"build_features needs these SPADL columns, missing: {missing}")

    selected = non_penalty_shot_mask(actions)
    if not selected.any():
        return _empty_features(feature_set)

    shots = actions[selected]
    # Positional, not the frame's own labels: every lookup below indexes raw numpy arrays, so a
    # non-RangeIndex frame (a concat, a groupby tail) must not be able to shift them.
    positions = np.flatnonzero(selected)
    start_x = shots["start_x"].to_numpy(dtype=float)
    start_y = shots["start_y"].to_numpy(dtype=float)

    data = _geometry(start_x, start_y)
    data["bodypart_id"] = shots["bodypart_id"].to_numpy(dtype=float)
    data["is_free_kick"] = (shots["type_id"] == FREEKICK_TYPE_ID).to_numpy().astype(float)

    if feature_set != "base":
        predecessor_types, same_team = _predecessor(actions, positions)
        assist_names = np.array(
            [spadl_config.actiontypes[t] if t >= 0 else ASSIST_NONE for t in predecessor_types],
            dtype=object,
        )
        assist_names = np.where(same_team, assist_names, ASSIST_LOOSE_BALL)
        assist_names = np.where(predecessor_types < 0, ASSIST_NONE, assist_names)

        one_hot = pd.get_dummies(pd.Series(assist_names, name="assist_type"), dtype=float)
        for name in ASSIST_VOCABULARY:
            if name not in one_hot.columns:
                one_hot[name] = 0.0
        one_hot = one_hot.reindex(columns=list(ASSIST_VOCABULARY), fill_value=0.0)
        one_hot.columns = list(ASSIST_COLUMNS)
        for name in ASSIST_COLUMNS:
            data[name] = one_hot[name].to_numpy()

        previous = np.where(positions > 0, positions - 1, 0)
        travel = np.hypot(
            actions["end_x"].to_numpy(dtype=float)[previous] - actions["start_x"].to_numpy(dtype=float)[previous],
            actions["end_y"].to_numpy(dtype=float)[previous] - actions["start_y"].to_numpy(dtype=float)[previous],
        )
        travel = np.where(np.isfinite(travel) & same_team, travel, 0.0)
        data["assist_travel_dist"] = travel
        data["assist_failed"] = np.where(
            same_team & (actions["result_id"].to_numpy()[previous] != GOAL_RESULT_ID), 1.0, 0.0
        )
        data["actions_since_team_change"] = _actions_since_team_change(actions, positions)

        defenders, teammates = _pressure_counts(actions, positions, start_x, start_y)
        data["defenders_within_radius"] = defenders
        data["teammates_within_radius"] = teammates

        minutes = match_minutes(actions)
        minute = minutes.to_numpy(dtype=float)

        # Seconds between the assist and the shot, from match-absolute minutes so a possession that
        # spans the break still measures correctly. Left as NaN for a shot with no same-team
        # predecessor -- a rebound off a save, or the opening row of the frame -- because there is
        # no assist to measure against, and the assist one-hots already say so. XGBoost routes NaN to
        # a learned default branch rather than pretending the gap was zero.
        seconds = (minute[positions] - minute[previous]) * 60.0
        seconds = np.where(same_team & np.isfinite(seconds), np.minimum(seconds, ASSIST_GAP_CAP), np.nan)
        data["time_since_assist"] = seconds

        first_touch = minutes.groupby([actions["game_id"], actions["player_id"]], dropna=True).transform("min")
        on_pitch = (minutes - first_touch).to_numpy(dtype=float)[positions]
        data["minutes_on_pitch"] = np.nan_to_num(on_pitch, nan=0.0)
        data["is_substitute"] = (on_pitch < SUBSTITUTE_THRESHOLD_MINUTES).astype(float)

    features = pd.DataFrame({name: data[name] for name in FEATURE_SETS[feature_set]}, index=shots.index)
    return features


def smoothed_rate(goals: int, shots: int, strength: float = 1.0) -> float:
    """Empirical goal rate pulled towards the league mean by ``strength`` pseudo-shots.

    Used for penalties, where the sample is small enough that the raw rate is a noisy estimate:
    70 goals from 84 penalties is 83.3% raw, but 70.5 from 85 pulls it to 82.9%.
    """
    return float((goals + strength * 0.11) / (shots + strength))


class XgRegressor:
    """:class:`XgRegressor` loads an ``xg_*.pkl`` artifact and prices shots.

    The artifact is a plain dict rather than a pickled estimator instance, matching
    ``models/train/train_mov.py`` -> :class:`metrics.high_level.mov_elo.regressor.MovRegressor``:
    the pickle then holds no reference to the code that wrote it, so artifacts survive the feature
    code being edited, and the class below can be re-pointed at a newer model without a re-pickle.
    """

    def __init__(self, model_path: str | Path):
        with open(model_path, "rb") as f:
            data = pickle.load(f)
        self._model = data["model"]
        self._feature_set = data["feature_set"]
        self._feature_names = list(data["feature_names"])
        self._penalty_p_goal = float(data["penalty_p_goal"])
        if self._feature_names != list(FEATURE_SETS[self._feature_set]):
            raise ValueError(
                f"xg artifact {model_path} was trained on a {len(self._feature_names)}-feature layout that no longer "
                f"matches FEATURE_SETS[{self._feature_set!r}]. Retrain it with models/train/train_xg.py."
            )
        logger.info(
            "Loaded custom xG model from %s (feature_set=%s, %d features, penalty_p_goal=%.4f)",
            model_path,
            self._feature_set,
            len(self._feature_names),
            self._penalty_p_goal,
        )

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    def predict(self, actions: pd.DataFrame) -> np.ndarray:
        """One goal probability per shot row of ``actions``, in frame order.

        ``actions`` is the whole match frame. Penalties short-circuit to the stored smoothed rate;
        everything else goes through the tree.
        """
        shots = shot_mask(actions)
        n_shots = int(shots.sum())
        if n_shots == 0:
            return np.empty(0, dtype=float)

        is_penalty = penalty_mask(actions)
        probabilities = np.empty(n_shots, dtype=float)
        probabilities[is_penalty[shots]] = self._penalty_p_goal

        open_play = ~is_penalty[shots]
        if open_play.any():
            features = build_features(actions, self._feature_set)
            probabilities[open_play] = self._model.predict_proba(features[self._feature_names])[:, 1]

        # Clipped rather than trusted: xT subtracts the cell value from this number and telescopes
        # a whole possession against the goals actually scored, so a probability outside (0, 1)
        # would break that identity outright.
        return np.clip(probabilities, 1e-6, 1 - 1e-6)
