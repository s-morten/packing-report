"""Design matrix and dependent variables for the xT plus-minus regression.

One segment of one match is one observation: a sparse design vector ``x`` over player columns
(plus one fixed column for home advantage), a weight ``w``, and two dependent variables -- net xT
per 90 and goal difference per 90.

Why two dependent variables
---------------------------
The design matrix depends **only on who was on the pitch**, never on the dependent variable, so
the normal-equation matrix ``A = sum(w x x^T)`` is identical for both. Only the right-hand side
``b = sum(w x y)`` differs. That makes the goal-difference baseline arm free, and it is worth
having: it is the only way to check whether the xT arm measures anything goal difference does not.

This matters because of Hvattum & Gelade (2021), *"Comparing bottom-up and top-down ratings for
individual soccer players"*. They tried to improve plus-minus by using VAEP as the dependent
variable, and measured a per-segment correlation of **r = 0.93** between aggregated VAEP and goal
difference -- because a goal is worth 1.0 to VAEP by construction, VAEP-per-segment is mostly a
noisy re-encoding of "goals scored in this 15-minute window". Their hybrid was statistically
indistinguishable from plain goal-difference plus-minus (paired t-tests p >= 0.48). A bottom-up
dependent variable is therefore not automatically an improvement, and shipping both arms makes
that measurable instead of assumed.

Segments and the home-advantage dummy
-------------------------------------
A segment boundary is created by a substitution, and the match **ends at the first red card**
(see :mod:`game.game_segments`). Every surviving segment is 11-v-11.

Because every segment therefore contains exactly eleven home players and eleven away players, the
home-advantage effect is estimated with a **twelfth-man dummy column** that is 1 in every row,
rather than with a separate home-advantage covariate that the player columns could not be
identified against. This is the trick from Saebo & Hvattum (2015). It has a structural consequence
in the estimator: a column that is 1 in every row is non-zero against every player, so it destroys
the block-sparse structure the solver relies on. :class:`~metrics.high_level.xtpm.estimator.XtPlusMinus`
therefore profiles that single column out analytically instead of putting it in the matrix.

Regularisation alternatives -- what is *not* implemented, and why
----------------------------------------------------------------
The estimator uses **plain ridge** (Tikhonov), ``theta = (A + lambda I)^-1 b``. This is the choice
of Kharrat, Lopez Pena & McHale (EJOR 2020, "Individual player's contribution to the team
performance in soccer", the three-variant PM / xGPM / xPPM paper) and of Klaiber & Rossle
(J. Big Data 2026). The alternatives below were considered and deliberately deferred.

**Similarity shrinkage** -- Hvattum (Applied Sciences 2020, "An alternative approach to
plus-minus for football"). Plain L2 shrinks every player toward zero. Hvattum shrinks each player
toward the *weighted average of the most similar players* -- those sharing the most minutes with
them -- so that two players who always appear together are judged as similar rather than both
being pulled to zero. The offensive-minus-defensive gap is shrunk toward the average for the same
position, and age effects toward neighbouring ages. This requires a minutes-overlap similarity
matrix over all players (O(p^2) memory, and a nearest-neighbour pass whenever a new player
appears) plus position labels, which the project does not currently carry. It is the single most
promising upgrade here.

**Augmented APM / FIFA prior** -- Matano (2018, arXiv:1810.08032), Bayesian. Standard APM puts
``beta ~ N(0, tau^2)``, i.e. shrinks to the average player, which is wrong for two centre-backs who
always play together. Matano moves the prior off zero: ``beta | alpha ~ N(alpha * rating, tau^2)``
with ``alpha ~ N(mu_alpha, sigma_alpha^2)``, where ``rating`` is the (mean-shifted) EA SPORTS FIFA
overall rating. Collinear players are then decorrelated by giving more of the credit to the
better-rated one while keeping the "effect relative to an average player" interpretation. Requires
a FIFA ratings data source, which the project does not have (``FootballSquads`` carries only
birthday, height and weight).

**Lasso (L1)** -- explicitly rejected by Kharrat et al. for this problem: L1 shrinks a group of
correlated predictors to *exactly zero* except one, whereas ridge shrinks them to *equal*
coefficients, which is the correct behaviour when two players genuinely share every minute. With
soccer's low substitution count the design matrix is near-singular and identical centre-back
pairings recur all season, so this distinction decides whether the second centre-back is rated at
all.

**Offensive / defensive split** -- Hvattum (2020). Replace the single net rating with two ratings
per player, fitted as an unconstrained quadratic program: sum of home offence minus sum of away
defence should reproduce home goals, and symmetrically for away. Identifiable because each segment
yields two observations, one per perspective. Deferred by decision -- the single net rating comes
first. Note that the split needs *both* home goals and home xT as separate targets per segment,
not the net difference stored today, so ``GAME_SEGMENT`` would need per-side, per-type columns
rather than just ``net_xt``.

**Exponential discounting** -- Saebo & Hvattum (2015) weight old observations by ``exp(-k*t)``
rather than uniformly. Implemented, not merely documented: the ``forgetting`` factor ``gamma``
multiplies ``A`` and ``b`` each game, so ``gamma = 1`` is uniform weighting and ``gamma < 1`` is
the geometric decay they use (their ``alpha_ij = +-e^{-kt}``, ``beta_i = 90*(H-A)*e^{-kt}/D_i``).
Hvattum & Gelade found that extra seasons barely help goal-difference plus-minus (0.576 ->
0.574) and that dropping ~8 seasons still left it ahead of VAEP, so ``gamma = 1`` is the default
here and discounting is available rather than assumed.

**Rejected outright: non-regression** -- Pelechrinis & Winston ("eLPAR", arXiv:1807.07536)
criticise ridge for assigning near-identical ratings to players who share the pitch, credit
Matano's FIFA prior as analogous to ESPN's Real Plus-Minus box-score prior, and reject APM
entirely in favour of a Skellam regression on (position, FIFA rating) interaction terms. Also
considered and not implemented: ordered-probit on match outcome (Kharrat's tuning criterion, used
in ``eval/eval_high_level.py`` to pick lambda rather than to fit the ratings), and win-probability
change as the dependent variable (Deshpande & Jensen), which needs a goal-time hazard model this
project does not have.

Weighting
---------
``w = duration / 90`` by default, following Hvattum's ``w_DURATION``: a short segment carries less
information about a per-90 rate than a long one. Hvattum additionally multiplies in a recency
term and a term that up-weights segments where the scoreline swings by two or more goals at both
the start and the end; the recency idea is available through ``forgetting``, and the scoreline
term is not implemented.

References
----------
* Rosenbaum (2004), basketball APM -- the origin of the method.
* Saebo & Hvattum (2015), Norsk Int. Økon. Tidsskr., "Separating out-of-play from in-play: a
  simple method to measure home advantage in Norwegian football" -- twelfth-man dummy, red-card
  dummies, exponential discounting.
* Kharrat, Lopez Pena & McHale (2020), EJOR 320(3) -- PM / xGPM / xPPM, ridge over lasso.
* Matano (2018), arXiv:1810.08032 -- augmented APM with a FIFA prior.
* Hvattum (2020), Applied Sciences 10:7345 -- offensive/defensive split, similarity shrinkage.
* Hvattum & Gelade (2021), Int. J. Computer Science in Sport -- top-down vs bottom-up, the 0.93
  correlation.
* Klaiber & Rossle (2026), J. Big Data -- ridge plus a home dummy, combined with bottom-up ratings
  via PCA.
* Pelechrinis & Winston, arXiv:1807.07536 -- the critique.
"""

from dataclasses import dataclass

import numpy as np

#: Column 0 is reserved for the twelfth-man home-advantage dummy.
HOME_ADVANTAGE_COLUMN = 0


@dataclass(frozen=True)
class FeatureSpec:
    """Which non-player columns the design carries."""

    home_advantage_dummy: bool = True

    @property
    def n_fixed_columns(self) -> int:
        return 1 if self.home_advantage_dummy else 0


@dataclass(frozen=True)
class Observation:
    """One regression row.

    ``indices`` / ``values`` are the sparse design vector over columns; ``weight`` is ``w``;
    ``y_xt`` and ``y_gd`` are the two dependent variables. Both are passed for every row because
    they share one design vector, which is what makes the second arm free.
    """

    indices: np.ndarray
    values: np.ndarray
    weight: float
    y_xt: float
    y_gd: float


def design_row(home, away, column_of, spec: FeatureSpec | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Build the sparse design vector for one segment.

    ``x[p] = +1`` when player ``p`` is on the home side, ``-1`` on the away side, and implicitly 0
    when absent. Indices come back sorted and de-duplicated so repeated players cannot accumulate
    weight.

    ``column_of`` is called exactly once per distinct player id and must return a stable column
    index for it; the estimator owns that mapping because it is also what grows the state.
    """
    spec = spec or FeatureSpec()
    indices: list[int] = []
    values: list[float] = []

    if spec.home_advantage_dummy:
        indices.append(HOME_ADVANTAGE_COLUMN)
        values.append(1.0)

    for player_ids, sign in ((home, 1.0), (away, -1.0)):
        # Deduplicated per side so that ``column_of`` is consulted once per distinct player even if
        # the caller passes a repeated id. A player cannot legitimately appear twice, but summing
        # (rather than taking the last sign) keeps the column sums well defined if it ever does.
        for player_id in sorted({int(player_id) for player_id in player_ids}):
            indices.append(column_of(player_id))
            values.append(sign)

    index_array = np.asarray(indices, dtype=np.int64)
    value_array = np.asarray(values, dtype=np.float64)

    # A player id can never be on both sides, but de-duplicating defensively keeps the column
    # sums well defined if that invariant is ever violated upstream.
    unique, inverse = np.unique(index_array, return_inverse=True)
    summed = np.zeros(len(unique), dtype=np.float64)
    np.add.at(summed, inverse, value_array)
    return unique, summed


def segment_weight(duration_minutes: float, weight_mode: str = "duration") -> float:
    """Weight of a segment. ``duration`` gives ``duration / 90``; ``uniform`` gives 1."""
    if duration_minutes <= 0:
        raise ValueError(f"segment duration must be positive, got {duration_minutes}")
    if weight_mode == "duration":
        return duration_minutes / 90.0
    if weight_mode == "uniform":
        return 1.0
    raise ValueError(f"unknown weight_mode {weight_mode!r}, expected 'duration' or 'uniform'")


def dependent_variables(net_xt_per90: float, goals_home: int, goals_away: int, duration_minutes: float):
    """The two per-90 dependent variables for a segment.

    Both are normalised to 90 minutes so that a truncated 18-minute segment sits on the same scale
    as a full one. Without this the short segments left behind by an early red card would dominate
    the fit purely through their raw magnitude.
    """
    scale = 90.0 / duration_minutes
    return float(net_xt_per90), float((goals_home - goals_away) * scale)


def build_observation(
    home,
    away,
    net_xt_per90: float,
    goals_home: int,
    goals_away: int,
    duration_minutes: float,
    column_of,
    spec: FeatureSpec | None = None,
    weight_mode: str = "duration",
) -> Observation:
    """Assemble the full observation for one segment."""
    spec = spec or FeatureSpec()
    indices, values = design_row(home, away, column_of, spec)
    y_xt, y_gd = dependent_variables(net_xt_per90, goals_home, goals_away, duration_minutes)
    return Observation(
        indices=indices,
        values=values,
        weight=segment_weight(duration_minutes, weight_mode),
        y_xt=y_xt,
        y_gd=y_gd,
    )
