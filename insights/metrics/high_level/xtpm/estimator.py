"""Online ridge plus-minus: discounted sufficient statistics over match segments.

What this computes
------------------
A standard adjusted-plus-minus model is a ridge regression of a team-level dependent variable on
signed player indicators, one row per segment:

    y_s = sum_p x[s, p] * theta[p] + error,      x[s, p] = +1 home / -1 away / 0 absent

Because the design matrix ``X`` depends only on who was on the pitch and never on ``y``, the
normal-equation matrix ``A = X' W X`` is the same object for every choice of dependent variable.
That is why this class carries **one** ``A`` and **two** right-hand sides, ``b_xt`` and ``b_gd``,
giving an xT rating and a goal-difference rating from a single pass over the data.

How "update after every game" is satisfied
------------------------------------------
The state is the pair of accumulated sufficient statistics, discounted by a forgetting factor:

    A <- gamma * A + sum_s w_s x_s x_s'
    b <- gamma * b + sum_s w_s x_s y_s
    theta = solve(A + lambda I, b)

This is the exact solution of the discounted ridge problem at every point in the sequence. It is
the same estimator as recursive least squares with ``P_0 = I / lambda`` and the same forgetting
factor -- RLS just carries ``P`` instead of ``A``, and the two agree in the batch limit -- but
accumulating ``A`` is preferable here for two reasons: the solve is exact rather than asymptotic,
and **lambda never enters the state**, so the penalty can be re-tuned afterwards without replaying
a single match. That is what makes the lambda sweep in ``eval/eval_high_level.py`` cheap.

Block sparsity
--------------
Two players only ever have a non-zero cross-product if they shared a pitch, so ``A`` is block
diagonal over connected components (roughly: a squad that shared minutes). A dense solve of the
full matrix would cost seconds per game at full scope, so the solve is done per component instead.
That is **exact**, not an approximation: if ``A`` has a zero off-diagonal block then ``A + lambda
I`` is block diagonal and so is its inverse.

The home-advantage dummy
------------------------
``FeatureSpec`` puts a twelfth-man dummy in column 0, present in every row. That column is non-zero
against every player, so leaving it in ``A`` would merge every component into one giant block and
destroy the sparsity above. It is therefore **profiled out analytically** rather than solved for.
With ``Z = [1, X]``, ``N = sum w``, ``s = sum w x``, ``t = sum w y``, ``u = sum w x y``:

    b0 = (t - s' C^-1 u) / (N - s' C^-1 s)        theta = C^-1 (u - b0 * s)

where ``C = A + lambda I`` over player columns only. Both inner products decompose over components
because ``C^-1`` does. The result is identical to solving the full system, at component-block
cost.

Deliberately absent: see :mod:`metrics.high_level.xtpm.features` for the full list of
regularisation schemes that were considered and deferred (similarity shrinkage, FIFA-prior
Bayesian APM, lasso, offensive/defensive split) and why.
"""

import json
import logging
from pathlib import Path

import numpy as np
from metrics.high_level.xtpm.features import HOME_ADVANTAGE_COLUMN, FeatureSpec, Observation

logger = logging.getLogger(__name__)

#: Weighted total, i.e. sum of w over all absorbed segments. Doubles as the ridge prior scale.
_DVS = ("xt", "gd")


class XtPlusMinus:
    """Discounted-ridge plus-minus state, updated one game at a time.

    Parameters
    ----------
    spec
        Which non-player columns the design carries. See :class:`~...features.FeatureSpec`.
    forgetting
        Discount factor ``gamma`` applied to the accumulated state once per game. ``1.0`` weights
        all matches equally; ``< 1.0`` is the exponential recency weighting of Saebo & Hvattum
        (2015), who weight observation ``i`` by ``exp(-k t)``.
    ridge
        Penalty ``lambda``. Held here for convenience only -- it is applied at solve time, never
        accumulated, so changing it re-scores history without a replay.
    weight_mode
        Segment weight: ``"duration"`` (w = duration / 90) or ``"uniform"``.
    """

    def __init__(
        self,
        spec: FeatureSpec | None = None,
        forgetting: float = 1.0,
        ridge: float = 1.0,
        weight_mode: str = "duration",
    ):
        self.spec = spec or FeatureSpec()
        self.forgetting = float(forgetting)
        self.weight_mode = weight_mode
        if self.forgetting <= 0:
            raise ValueError(f"forgetting must be in (0, 1], got {forgetting}")

        # Assigned before ``ridge`` because the setter invalidates the factor cache, which must
        # already exist for the first assignment.
        self._factors: dict[int, np.ndarray] = {}
        self._factorised: set[int] = set()
        self.ridge = ridge

        self._first_player_column = self.spec.n_fixed_columns

        self._player_columns: dict[int, int] = {}  # player id -> column
        self._column_player: list[int] = [-1] * self._first_player_column  # column -> player id
        self._column_parent: list[int] = list(range(self._first_player_column))
        self._column_position: list[int] = [0] * self._first_player_column

        self._blocks: dict[int, np.ndarray] = {}  # root -> dense player-player block
        self._block_columns: dict[int, list[int]] = {}  # root -> its columns, in row order

        self._n = 0.0  # sum of w
        self._t = dict.fromkeys(_DVS, 0.0)  # sum of w * y, per dependent variable
        self._s = np.zeros(self._first_player_column, dtype=np.float64)  # sum of w * x
        self._rhs = {dv: np.zeros(self._first_player_column, dtype=np.float64) for dv in _DVS}  # sum w x y

        self._absorbed: set[int] = set()
        self._solution: dict[str, dict[int, float]] = {dv: {} for dv in _DVS}

    # ------------------------------------------------------------------ columns

    @property
    def player_ids(self) -> list[int]:
        return sorted(self._player_columns)

    @property
    def n_players(self) -> int:
        return len(self._player_columns)

    @property
    def n_columns(self) -> int:
        return len(self._column_player)

    @property
    def absorbed_game_ids(self) -> set[int]:
        return set(self._absorbed)

    def column_of(self, player_id: int) -> int:
        """Column index for ``player_id``, assigning one if this is the player's first appearance.

        This is the ``column_of`` callable that :func:`...features.design_row` needs, so a design
        vector can be built for a match containing players the state has never seen.
        """
        column = self._player_columns.get(player_id)
        if column is None:
            column = len(self._column_player)
            self._player_columns[player_id] = column
            self._column_player.append(player_id)
            self._column_parent.append(column)
            self._column_position.append(0)
            self._s = np.append(self._s, 0.0)
            for dv in _DVS:
                self._rhs[dv] = np.append(self._rhs[dv], 0.0)
            self._blocks[column] = np.zeros((1, 1), dtype=np.float64)
            self._block_columns[column] = [column]
            self._factorised.discard(column)
        return column

    def _find(self, column: int) -> int:
        parent = self._column_parent[column]
        while parent != self._column_parent[parent]:
            self._column_parent[parent] = self._column_parent[self._column_parent[parent]]
            parent = self._column_parent[column]
        return parent

    def _union(self, columns: list[int]) -> int:
        """Merge the components containing ``columns`` and return the surviving root.

        Every pair of players that appears in one segment is therefore in one block, which is what
        makes solving blocks independently equivalent to solving the whole system.
        """
        # The root of each column is resolved inside the loop, not up front: merging two blocks
        # deletes the loser from ``_block_columns`` and reparents its columns, so a root captured
        # earlier in the list can already be stale by the time the loop reaches it. Two players of
        # the same segment routinely share a block, which is what makes ``[a, b, b, ...]`` arise.
        root = self._find(columns[0])
        for column in columns[1:]:
            other = self._find(column)
            if other == root:
                continue
            root = self._merge(root, other)
        return root

    def _merge(self, keep: int, drop: int) -> int:
        keep_columns = self._block_columns[keep]
        drop_columns = self._block_columns[drop]
        offset = len(keep_columns)
        size = offset + len(drop_columns)

        merged = np.zeros((size, size), dtype=np.float64)
        merged[:offset, :offset] = self._blocks[keep]
        merged[offset:, offset:] = self._blocks[drop]
        self._blocks[keep] = merged
        self._block_columns[keep] = keep_columns + drop_columns
        for position, column in enumerate(keep_columns):
            self._column_position[column] = position
        for position, column in enumerate(drop_columns, start=offset):
            self._column_parent[column] = keep
            self._column_position[column] = position
        del self._blocks[drop]
        del self._block_columns[drop]
        self._factorised.discard(keep)
        self._factorised.discard(drop)
        return keep

    # ------------------------------------------------------------------ absorbing

    def observe(self, game_id: int, observations: list[Observation]) -> dict[int, dict[str, float]] | None:
        """Absorb one game's segments and return that game's ratings.

        Returns, for every player who appeared in this game, their rating *after* it was absorbed
        under both dependent variables plus the increment the game contributed. Rows for players
        who did not play are never written, so the caller can insert this mapping verbatim.

        Re-observing a game id already absorbed returns ``None``. That makes stage 1 idempotent --
        re-running a match after ``pipeline/recalc_metrics.py --run`` must not double count it --
        and it is also the only correct answer for the rating *history*: the rating stored for a
        game is "the rating at the end of that game", which is settled once written. Returning the
        current state instead would silently overwrite an early game's row with the final rating
        of a resumed run. To re-score games that were already absorbed -- which is what happens
        when ``ridge`` changes, since the penalty is applied at solve time and is deliberately not
        part of the state -- rebuild from scratch instead.
        """
        game_id = int(game_id)
        if game_id in self._absorbed:
            logger.warning("Game %s already absorbed into the plus-minus state -- skipping", game_id)
            return None

        players = {
            int(self._column_player[column])
            for observation in observations
            for column in observation.indices
            if column >= self._first_player_column
        }

        before = self._solution

        if self.forgetting != 1.0:
            self._n *= self.forgetting
            for dv in _DVS:
                self._t[dv] *= self.forgetting
            self._s *= self.forgetting
            for dv in _DVS:
                self._rhs[dv] *= self.forgetting
            for root in list(self._blocks):
                self._blocks[root] *= self.forgetting
                self._factorised.discard(root)

        for observation in observations:
            self._absorb_observation(observation)

        self._absorbed.add(game_id)
        self._solution = self._solve()
        return self._ratings_for(players, self._solution, before)

    def _absorb_observation(self, observation: Observation) -> None:
        indices = observation.indices
        values = observation.values
        if self._first_player_column:
            keep = indices >= self._first_player_column
            indices = indices[keep]
            values = values[keep]
        if indices.size == 0:
            return

        weight = observation.weight
        columns = [int(index) for index in indices]

        # Accumulate the scalar / vector parts first; they are indexed by column and so are
        # unaffected by the block merge below.
        self._n += weight
        np.add.at(self._s, indices, weight * values)
        for dv, y in (("xt", observation.y_xt), ("gd", observation.y_gd)):
            self._t[dv] += weight * y
            np.add.at(self._rhs[dv], indices, weight * values * y)

        root = self._union(columns)
        positions = [self._column_position[column] for column in columns]
        outer = weight * np.outer(values, values)
        block = self._blocks[root]
        block[np.ix_(positions, positions)] += outer
        self._factorised.discard(root)

    # ------------------------------------------------------------------ solving

    @property
    def ridge(self) -> float:
        return self._ridge

    @ridge.setter
    def ridge(self, value: float) -> None:
        """Set the penalty, dropping cached factors.

        The penalty enters only at solve time, so lambda is deliberately not persisted: it can be
        swept against a saved state without replaying any events. That is only true if the cached
        Cholesky factors -- which bake lambda into the diagonal -- are dropped when it changes.
        """
        value = float(value)
        if value <= 0:
            raise ValueError(f"ridge must be positive, got {value}")
        self._ridge = value
        self._factors.clear()
        self._factorised.clear()

    def _block_solutions(self, dv: str) -> dict[int, np.ndarray]:
        """``C^-1 u`` for one dependent variable, as a positionally-indexed array per root.

        The player-player block matrix ``C = A + lambda I`` never contains the home-advantage
        column, so this is only the *player* part of the solve; :meth:`_solve` combines it with the
        profiled-out dummy coefficient.
        """
        rhs = self._rhs[dv]
        return {root: self._cho_solve(root, rhs[columns]) for root, columns in self._block_columns.items()}

    def _cho_solve(self, root: int, rhs: np.ndarray) -> np.ndarray:
        """Solve ``(A_block + lambda I) z = rhs`` using a cached Cholesky factor."""
        if root not in self._factorised:
            self._factors[root] = self._cholesky(self._blocks[root])
            self._factorised.add(root)
        return _cho_solve_with(self._factors[root], rhs)

    def _cholesky(self, block: np.ndarray) -> np.ndarray:
        size = block.shape[0]
        # lambda I on the diagonal makes the block positive definite; the jitter is a guard for
        # blocks that are numerically singular (very few players who never shared a pitch twice).
        for scale in (0.0, 1e-10 * size, 1e-6 * size):
            try:
                return np.linalg.cholesky(block + (self.ridge + scale) * np.eye(size))
            except np.linalg.LinAlgError:
                continue
        raise np.linalg.LinAlgError("plus-minus block is not positive definite; raise --ridge")

    def _solve(self) -> dict[str, np.ndarray]:
        """Ratings for both dependent variables, keyed by column, from the current state.

        The home-advantage dummy is profiled out analytically rather than being solved for inside
        the matrix. With ``Z = [1, X]`` the normal equations ``[N s'; s C][b0; theta] = [t; u]``
        give ``theta = C^-1 (u - b0 s)`` and, substituting back,
        ``b0 = (t - s' C^-1 u) / (N - s' C^-1 s)``. Both inner products decompose over components
        because ``C^-1`` does, so this costs component-block work rather than a full solve -- and
        it is the same answer, since ``1`` is in every row and so ``C`` stays block diagonal.
        """
        use_dummy = self.spec.home_advantage_dummy
        solution = {}
        for dv in _DVS:
            player_part = self._block_solutions(dv)
            theta = np.zeros(self.n_columns, dtype=np.float64)

            if use_dummy:
                # C^-1 s does not depend on the dependent variable, so it is shared.
                cross = {root: self._cho_solve(root, self._s[columns]) for root, columns in self._block_columns.items()}
                # The denominator is the residual weight left after projecting the player columns
                # out, so it is judged relative to the total weight. An absolute floor would fire
                # on small states; the exact-zero case means the dummy is collinear with the
                # player columns (degenerate: identical line-ups throughout), and the coefficient
                # is then genuinely unidentified, so 0 is the only defensible answer.
                denominator = self._n
                numerator = self._t[dv]
                for root, columns in self._block_columns.items():
                    weights = self._s[columns]
                    denominator -= float(weights @ cross[root])
                    numerator -= float(weights @ player_part[root])
                unidentified = abs(denominator) <= 1e-9 * abs(self._n)
                if unidentified:
                    logger.warning(
                        "Home-advantage dummy is collinear with the player columns; setting its "
                        "coefficient to 0. This happens when line-ups never change."
                    )
                home_advantage = 0.0 if unidentified else numerator / denominator
                theta[HOME_ADVANTAGE_COLUMN] = home_advantage

            for root, columns in self._block_columns.items():
                if use_dummy:
                    theta[columns] = player_part[root] - home_advantage * cross[root]
                else:
                    theta[columns] = player_part[root]
            solution[dv] = theta
        return solution

    def _ratings_for(
        self, players: set[int], solution: dict[str, np.ndarray], before: dict[str, np.ndarray]
    ) -> dict[int, dict[str, float]]:
        """Ratings and per-game credits for the players who appeared, keyed by player id."""
        out = {}
        for player_id in sorted(players):
            column = self._player_columns[player_id]
            entry = {}
            for dv in _DVS:
                current = float(solution[dv][column])
                previous = float(before[dv][column]) if column < len(before[dv]) else 0.0
                entry[dv] = current
                entry[f"{dv}_credit"] = current - previous
            out[player_id] = entry
        return out

    # ------------------------------------------------------------------ reading

    def ratings(self, dv: str = "xt") -> dict[int, float]:
        """Every player's current rating. Solves the state, so it is not free to call in a loop."""
        if dv not in _DVS:
            raise ValueError(f"unknown dependent variable {dv!r}, expected one of {_DVS}")
        solution = self._solve()
        self._solution = solution
        return {player_id: float(solution[dv][column]) for player_id, column in self._player_columns.items()}

    def predict_goal_diff(self, home, away, minutes: float = 90.0, dv: str = "xt") -> float:
        """Predicted net quality for a match between two line-ups, scaled to ``minutes``.

        The sum of the eleven home ratings minus the sum of the eleven away ratings is the
        regression's own prediction of the dependent variable; dividing by 90 and multiplying by
        ``minutes`` puts it back on the per-90 scale the ratings live on.
        """
        home_total = sum(self.ratings(dv).get(int(player_id), 0.0) for player_id in home)
        away_total = sum(self.ratings(dv).get(int(player_id), 0.0) for player_id in away)
        return (home_total - away_total) * (minutes / 90.0)

    # ------------------------------------------------------------------ persistence

    def save(self, path) -> Path:
        """Write the state to ``path`` (``.npz``).

        The state is small: one dense square per component plus the accumulators. Storing ``A``
        rather than a recursive-least-squares ``P`` is what keeps this file readable by anything
        that can load numpy, and keeps lambda out of it.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        roots = sorted(self._blocks)
        block_list = [self._blocks[root] for root in roots]
        flat = np.concatenate([block.ravel() for block in block_list]) if block_list else np.zeros(0)
        shapes = np.asarray([block.shape[0] for block in block_list], dtype=np.int64)

        meta = {
            "spec": {"home_advantage_dummy": self.spec.home_advantage_dummy},
            "forgetting": self.forgetting,
            "ridge": self.ridge,
            "weight_mode": self.weight_mode,
            "player_columns": self._player_columns,
            "column_player": self._column_player,
            "column_parent": self._column_parent,
            "block_columns": {str(root): self._block_columns[root] for root in roots},
            "n": self._n,
            "t": self._t,
            "absorbed_game_ids": sorted(self._absorbed),
        }
        np.savez_compressed(
            path,
            meta=json.dumps(meta),
            blocks=flat,
            shapes=shapes,
            s=self._s,
            rhs_xt=self._rhs["xt"],
            rhs_gd=self._rhs["gd"],
        )
        return path

    @classmethod
    def load(cls, path) -> "XtPlusMinus":
        """Restore a state written by :meth:`save`. Rebuilds the factorisation cache as empty."""
        path = Path(path)
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            state = cls(
                spec=FeatureSpec(**meta["spec"]),
                forgetting=meta["forgetting"],
                ridge=meta["ridge"],
                weight_mode=meta["weight_mode"],
            )
            state._player_columns = {int(k): int(v) for k, v in meta["player_columns"].items()}
            state._column_player = [int(value) for value in meta["column_player"]]
            state._column_parent = [int(value) for value in meta["column_parent"]]
            state._n = float(meta["n"])
            state._t = {dv: float(value) for dv, value in meta["t"].items()}
            state._absorbed = {int(game_id) for game_id in meta["absorbed_game_ids"]}

            shapes = [int(size) for size in data["shapes"]]
            flat = data["blocks"]
            state._s = data["s"].astype(np.float64)
            state._rhs = {"xt": data["rhs_xt"].astype(np.float64), "gd": data["rhs_gd"].astype(np.float64)}
            state._factors = {}

            offset = 0
            for root_text, size in zip(meta["block_columns"], shapes, strict=True):
                root = int(root_text)
                block = flat[offset : offset + size * size].reshape(size, size)
                offset += size * size
                state._blocks[root] = block
                state._block_columns[root] = [int(column) for column in meta["block_columns"][root_text]]
            state._column_position = [0] * len(state._column_player)
            for columns in state._block_columns.values():
                for position, column in enumerate(columns):
                    state._column_position[column] = position
        state._solution = state._solve()
        return state


def _cho_solve_with(factor: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Solve ``L L' z = rhs`` given the lower Cholesky factor ``L``."""
    intermediate = np.linalg.solve(factor, rhs)
    return np.linalg.solve(factor.T, intermediate)
