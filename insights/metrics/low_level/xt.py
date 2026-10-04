"""Expected-threat (xT) valuation of every action in a match.

This module owns the **single** xT pricing pass per game. The pass produces one value per action,
and that single pass then feeds two consumers:

1. the per-player ``xt`` metric written to ``PLAYER_GAME_METRIC``;
2. the per-segment dependent variable written to ``METRICS.GAME_SEGMENT``, which the plus-minus
   regression (``metrics.high_level.xtpm``) consumes.

Because both consumers read the same ``xt_value`` column, the plus-minus dependent variable is
consistent with the ``xt`` metric by construction, and no action is ever priced twice.

Action coverage
---------------
``ExpectedThreat.rate()`` values only *successful* ``pass`` / ``dribble`` / ``cross``
(``socceraction.xthreat.get_successful_move_actions``) as the change in cell value,
``xT[end] - xT[start]``. Shots come back as ``NaN`` and socceraction ships no ``rate_shot``, so
:func:`rate_shots` supplies them.

Deliberately **not** valued, because the xT surface is only defined for ball progression and
shooting: throw-ins, corners, free kicks, goalkeeper passes, tackles, interceptions, aerials,
offsides and out-of-play events. Their cost (turnovers, dispossessions) is a real part of team
quality that xT does not see. VAEP is the natural alternative if that coverage is ever wanted --
see ``metrics/low_level/vaep.py``.
"""

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from game.game_segments import Segment, build_segments
from metrics.low_level.xg import XgRegressor
from socceraction.spadl import config as spadl_config
from socceraction.xthreat import ExpectedThreat, _get_cell_indexes

from database_io.repositories.metric_repo import DB_metric

logger = logging.getLogger(__name__)
_MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "model"


def _find_latest_model(model_dir, pattern="xt_*.pkl"):
    matches = sorted(model_dir.glob(pattern))
    return matches[-1] if matches else None


def match_minutes(actions: pd.DataFrame) -> pd.Series:
    """Match-absolute minute of every action.

    ``time_seconds`` in SPADL is **period-relative**, not match-cumulative: for a 93-minute match the
    second half arrives as ``3.0 .. 47.8`` minutes rather than ``48.0 .. 92.8``. Binning on the raw
    value therefore collapses the whole second half into the first segment, and makes any
    ``on < minute < off`` presence filter reject second-half actions of substitutes who came on
    after minute 48.

    Offsetting by 45 minutes per completed period recovers the convention the rest of the pipeline
    uses, because every other minute in play -- ``Minutes``, the segment boundaries, and WhoScored's
    own ``expanded_minute`` -- is match-absolute. Verified against the event feed for
    Eintracht Frankfurt 1-6 Bayern: period 2 spans 48.00-92.78 here versus 48.00-93.00 in
    ``expanded_minute``.
    """
    return (actions["period_id"] - 1) * 45 + actions["time_seconds"] / 60


def rate_shots(
    actions: pd.DataFrame,
    xt_model: ExpectedThreat,
    xg_model=None,
) -> np.ndarray:
    """Value every shot in ``actions``; ``NaN`` for every non-shot row.

    The return contract is deliberately identical to :meth:`socceraction.xthreat.ExpectedThreat.rate`
    -- one value per input row, positionally aligned -- so both pricing passes compose without
    any index juggling.

    Shots are rated by the **custom xG model** -- ``metrics.low_level.xg.XgRegressor``, trained by
    ``models/train/train_xg.py`` and stored as ``models/model/xg_*.pkl``. If no such model is
    present, this function falls back to the xT model's own cell-based scoring-probability surface,
    which knows nothing about the shot's distance, angle, body part, assist type or defensive
    context.

    The **whole** action frame is forwarded to ``xg_model.predict``, not a pre-filtered shot
    subset, because the xG features reach backwards: the assist type, the possession length and the
    bodies inside the 12 m radius around the shooter are all read off the action that preceded the
    shot and off the other players' positions at that instant. The model masks the shots out of the
    frame itself, so the only contract this function relies on is
    ``xg_model.predict(actions) -> np.ndarray`` with **one value per shot in ``actions``, in shot
    order** -- not one value per input row.

    The value assigned to a shot is ``p_goal - xT[start_cell]``. The subtraction is what makes the
    per-possession sum telescope to ``goals + delta(possession xT)``: ``p_goal`` credits the
    chance of scoring outright, and the xT of the cell the shot was taken from is removed because
    that value has already been credited by the pass or dribble that moved the ball there.
    Without it, the cell value would be counted twice. (The usual alternative,
    ``p*1 + (1-p)*xT[start] - xT[start]``, collapses to ``p*(1 - xT)`` and differs by only
    ``p*xT ~ 0.001`` on this grid, where cell xT ranges 0.0049-0.0774 -- so the two are
    numerically indistinguishable here, and the telescoping form is preferred on principle.)
    """
    ratings = np.full(len(actions), np.nan)
    if actions.empty:
        return ratings

    shot_type = spadl_config.actiontypes.index("shot")
    shot_mask = (actions["type_id"] == shot_type).values
    if not shot_mask.any():
        return ratings

    shot_actions = actions[shot_mask]

    if xg_model is not None:
        p_goal = np.asarray(xg_model.predict(actions), dtype=float)
        if len(p_goal) != int(shot_mask.sum()):
            raise ValueError(f"xg_model.predict returned {len(p_goal)} values for {int(shot_mask.sum())} shots")
    else:
        # Placeholder: cell-based scoring probability of the xT surface (xthreat.scoring_prob).
        # Returns a per-cell matrix, so index it by the shot's own cell.
        cell_x, cell_y = _shot_cells(shot_actions, xt_model)
        p_goal = xt_model.scoring_prob_matrix[cell_y, cell_x].astype(float)

    cell_x, cell_y = _shot_cells(shot_actions, xt_model)
    cell_xt = xt_model.xT[cell_y, cell_x].astype(float)

    ratings[shot_mask] = p_goal - cell_xt
    return ratings


def _shot_cells(actions: pd.DataFrame, xt_model: ExpectedThreat):
    """Map a shot's ``(start_x, start_y)`` to grid indices, clamped exactly as ``rate()`` does.

    Returned as pandas Series because ``rsub`` -- the clamp ``ExpectedThreat.rate`` applies to
    negative indices produced by out-of-range coordinates -- is a Series method.
    """
    x_index, y_index = _get_cell_indexes(actions["start_x"], actions["start_y"], xt_model.l, xt_model.w)
    return x_index, y_index.rsub(xt_model.w - 1)


class Xt:
    def __init__(self, metric_repo=None, model_path=None, xg_model_path=None, include_shots: bool = True):
        self.metric_repo = metric_repo or DB_metric()
        self.include_shots = include_shots
        model_path = Path(model_path) if model_path else _find_latest_model(_MODEL_DIR)

        if model_path and model_path.exists():
            with open(model_path, "rb") as f:
                self.xt_model = pickle.load(f)
            logger.info("Loaded xT model from %s", model_path)
        else:
            self.xt_model = None
            logger.warning("No xT model found at %s -- skipping xT metric", _MODEL_DIR)

        # Resolved eagerly so the call site never changes when a real custom xG model lands.
        xg_model_path = Path(xg_model_path) if xg_model_path else _find_latest_model(_MODEL_DIR, "xg_*.pkl")
        if xg_model_path and xg_model_path.exists():
            self.xg_model = XgRegressor(xg_model_path)
            logger.info("Loaded custom xG model from %s", xg_model_path)
        else:
            self.xg_model = None
            logger.info("No custom xG model found -- shots rated with the xT surface instead")

    def calculate(self, game_facts, segments: list[Segment] | None = None):
        """Price every action once, then project that pass onto players and segments.

        Sets ``player_xt_mapping`` (consumed by :meth:`write`) and, when ``segments`` is given,
        ``segment_xt`` (consumed by :meth:`segment_rows`). Both are None/empty when no xT model is
        available.
        """
        if self.xt_model is None:
            self.player_xt_mapping = {}
            self.segment_xt = None
            return

        actions = game_facts.spadl
        if actions.empty:
            self.player_xt_mapping = {}
            self.segment_xt = None
            return

        if segments is None:
            segments = build_segments(game_facts)
        self._value_actions(actions)

        self.player_xt_mapping = self._per_player_totals(game_facts)
        self.segment_xt = self._per_segment_totals(game_facts, segments)

    def _value_actions(self, actions: pd.DataFrame) -> None:
        """The single pricing pass. Attaches ``xt_value`` in place and returns self."""
        mask = actions["end_x"].notna() & actions["end_y"].notna()
        xt_values = np.full(len(actions), np.nan)
        if mask.any():
            xt_values[mask.values] = self.xt_model.rate(actions[mask])

        if self.include_shots:
            # Disjoint from the move values by construction: rate() only prices successful
            # pass/dribble/cross, and a shot has its own type_id, so the two can be merged
            # without double counting.
            shot_values = rate_shots(actions, self.xt_model, self.xg_model)
            has_shot_value = ~np.isnan(shot_values)
            xt_values[has_shot_value] = np.where(
                np.isnan(xt_values[has_shot_value]), shot_values[has_shot_value], xt_values[has_shot_value]
            )

        actions["xt_value"] = xt_values

    def _per_player_totals(self, game_facts) -> dict[int, float]:
        """Total xT per player.

        Filters on ``on < minute < off`` using :func:`match_minutes`. That is equivalent to segment
        presence (``on <= b_k and off >= b_k+1``) apart from boundary equality, where this filter
        excludes the substitution minute itself.

        NOTE: this previously filtered on the raw ``time_seconds / 60``, which is period-relative,
        so every substitute who came on after minute 48 had their entire second half discarded. The
        stored ``xt`` values therefore change, upwards, and games already scored before this fix
        need re-running -- ``uv run insights/gi.py --force --seasons ...``.
        """
        actions = game_facts.spadl
        valued = actions[actions["xt_value"].notna()]
        player_xt_mapping = {int(player_id): 0.0 for player_id in game_facts.players_dict}
        if valued.empty:
            return player_xt_mapping

        valued_minute = match_minutes(valued)
        for player_id, info in game_facts.players_dict.items():
            on = float(info["on"])
            off = float(info["off"])
            player_actions = valued[(valued["player_id"] == player_id) & (valued_minute > on) & (valued_minute < off)]
            player_xt_mapping[int(player_id)] = float(player_actions["xt_value"].sum())
        return player_xt_mapping

    def _per_segment_totals(self, game_facts, segments: list[Segment]) -> list[dict]:
        """xT summed per side within each segment, plus the net and per-90 dependent variables."""
        actions = game_facts.spadl
        valued = actions[actions["xt_value"].notna()]
        home_team_id = int(game_facts.home_team_id)

        rows = []
        for segment in segments:
            in_segment = valued[
                (match_minutes(valued) >= segment.start_minute) & (match_minutes(valued) < segment.end_minute)
            ]
            if in_segment.empty:
                xt_home = 0.0
                xt_away = 0.0
            else:
                is_home_action = in_segment["team_id"] == home_team_id
                xt_home = float(in_segment.loc[is_home_action, "xt_value"].sum())
                xt_away = float(in_segment.loc[~is_home_action, "xt_value"].sum())

            duration = segment.duration_minutes
            scale = 90.0 / duration if duration > 0 else 0.0
            rows.append({"xt_home": xt_home, "xt_away": xt_away, "net_xt": xt_home - xt_away})
            rows[-1]["net_xt_per90"] = (xt_home - xt_away) * scale
        return rows

    def segment_rows(self, game_id: int, segments: list[Segment], segment_goals) -> list[dict]:
        """Assemble the ``METRICS.GAME_SEGMENT`` rows for one game.

        The goal-difference arm of the dependent variable is filled in here from the segment goal
        counts, so both arms are persisted from a single pass and stage 2 never has to re-read raw
        events.
        """
        if self.segment_xt is None:
            return []

        rows = []
        for segment in segments:
            duration = segment.duration_minutes
            scale = 90.0 / duration if duration > 0 else 0.0
            goals_home = int(segment_goals.home[segment.index])
            goals_away = int(segment_goals.away[segment.index])
            rows.append(
                {
                    "game_id": int(game_id),
                    "segment_index": int(segment.index),
                    "start_minute": float(segment.start_minute),
                    "end_minute": float(segment.end_minute),
                    "duration_minutes": float(duration),
                    "n_players_home": len(segment.home),
                    "n_players_away": len(segment.away),
                    "xt_home": float(self.segment_xt[segment.index]["xt_home"]),
                    "xt_away": float(self.segment_xt[segment.index]["xt_away"]),
                    "net_xt": float(self.segment_xt[segment.index]["net_xt"]),
                    "net_xt_per90": float(self.segment_xt[segment.index]["net_xt_per90"]),
                    "goals_home": goals_home,
                    "goals_away": goals_away,
                    "gd90": float((goals_home - goals_away) * scale),
                }
            )
        return rows

    def write(self, session, game_id):
        metric_batch = [[player, game_id, float(xt_value), "xt"] for player, xt_value in self.player_xt_mapping.items()]
        self.metric_repo.insert_batch_metric(session, metric_batch)
