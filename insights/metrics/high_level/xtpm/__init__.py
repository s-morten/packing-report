"""xT plus-minus: a regression-based team-differential rating with a per-game update.

The metric splits each match into segments during which the line-up is constant, regresses a
team-level dependent variable on signed player indicators over those segments, and publishes every
player's rating after every match. See :mod:`metrics.high_level.xtpm.features` for the design and
for the regularisation schemes deliberately left out, and
:mod:`metrics.high_level.xtpm.estimator` for the discounted-ridge state and its block-sparse
solve.
"""

from metrics.high_level.xtpm.estimator import XtPlusMinus
from metrics.high_level.xtpm.features import FeatureSpec, Observation, build_observation, design_row

__all__ = ["FeatureSpec", "Observation", "XtPlusMinus", "build_observation", "design_row"]
