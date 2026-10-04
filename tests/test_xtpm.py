import numpy as np
import pytest
from metrics.high_level.xtpm import FeatureSpec, XtPlusMinus, build_observation

_DVS = ("xt", "gd")


class Fixture:
    """Feeds observations to an estimator while independently recording the raw inputs.

    The recorded rows are what :meth:`dense_solve` rebuilds a design matrix from, so the reference
    never reads the estimator's internals -- otherwise it would only be checking that the
    block-decomposed solve equals itself.
    """

    def __init__(self, ridge=1.0, forgetting=1.0, dummy=True, weight_mode="duration", state=None):
        self.state = state or XtPlusMinus(
            spec=FeatureSpec(home_advantage_dummy=dummy),
            forgetting=forgetting,
            ridge=ridge,
            weight_mode=weight_mode,
        )
        self.ridge = ridge
        self.dummy = dummy
        self.weight_mode = weight_mode
        self.rows = []
        self.players = set()

    def game(self, game_id, home, away, y_xt, goals_home=0, goals_away=0, minutes=90.0):
        """Absorb one segment.

        The goal-difference arm is driven by ``goals_home`` / ``goals_away`` rather than by a
        pre-computed DV, so the recorded rows and the estimator derive ``y_gd`` the same way.
        """
        home = [int(player) for player in home]
        away = [int(player) for player in away]
        self.players.update(home)
        self.players.update(away)
        weight = minutes / 90.0 if self.weight_mode == "duration" else 1.0
        y_gd = (goals_home - goals_away) * 90.0 / minutes
        self.rows.append((home, away, weight, y_xt, y_gd))
        return self.state.observe(
            game_id,
            [
                build_observation(
                    home=home,
                    away=away,
                    net_xt_per90=y_xt,
                    goals_home=goals_home,
                    goals_away=goals_away,
                    duration_minutes=minutes,
                    column_of=self.state.column_of,
                    spec=self.state.spec,
                    weight_mode=self.weight_mode,
                )
            ],
        )

    def dense_solve(self, dv):
        """Weighted ridge of the segment DV on player indicators, solved as one dense system.

        Built from the raw line-ups rather than from the estimator, and with the home-advantage
        dummy as a genuine intercept column that carries no penalty -- which is what profiling the
        dummy out of the estimator's block solve is algebraically equivalent to.
        """
        y_index = 3 if dv == "xt" else 4
        players = sorted(self.players)
        position = {player: index for index, player in enumerate(players)}
        width = len(players) + (1 if self.dummy else 0)

        design = np.zeros((len(self.rows), width))
        target = np.zeros(len(self.rows))
        weights = np.zeros(len(self.rows))
        for index, (home, away, weight, y_xt, y_gd) in enumerate(self.rows):
            offset = 1 if self.dummy else 0
            if self.dummy:
                design[index, 0] = 1.0
            for player in home:
                design[index, offset + position[player]] += 1.0
            for player in away:
                design[index, offset + position[player]] -= 1.0
            target[index] = (y_xt, y_gd)[y_index - 3]
            weights[index] = weight

        penalty = np.zeros(width)
        penalty[1 if self.dummy else 0 :] = self.ridge
        weighted = design * np.sqrt(weights)[:, None]
        solution = np.linalg.solve(
            weighted.T @ weighted + np.diag(penalty),
            weighted.T @ (target * np.sqrt(weights)),
        )
        offset = 1 if self.dummy else 0
        return {player: float(solution[offset + position[player]]) for player in players}


def random_games(fixture, count, pool, per_side, seed, minutes=None):
    rng = np.random.default_rng(seed)
    for game_id in range(1, count + 1):
        home = sorted(rng.choice(pool, per_side, replace=False).tolist())
        away = sorted(rng.choice(pool, per_side, replace=False).tolist())
        fixture.game(
            game_id,
            home=home,
            away=away,
            y_xt=float(rng.normal()),
            goals_home=int(rng.integers(0, 2)),
            goals_away=int(rng.integers(0, 2)),
            minutes=float(minutes if minutes is not None else rng.uniform(5, 90)),
        )
    return fixture


class TestUnionIsIdempotentPerRoot:
    """Regression: a root resolved before an earlier merge in the same call can be stale.

    Two players of one segment routinely share a block, so the resolved roots contain duplicates.
    Merging deletes the losing block, so a duplicate appearing *after* the merge used to raise
    ``KeyError`` from ``_merge``. That is what broke stage 2 on the second run over the data.
    """

    def test_three_blocks_with_two_players_already_co_rooted(self):
        fixture = Fixture()
        fixture.game(1, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
        # A segment spanning three blocks where the co-rooted pair is not first in column order.
        result = fixture.game(2, home=[3, 1, 2], away=[13, 14], y_xt=1.0, goals_home=1.0)

        assert result is not None
        assert fixture.state.n_players == 7
        for dv in _DVS:
            assert all(np.isfinite(value) for value in fixture.state.ratings(dv).values())

    def test_co_rooted_pair_in_the_middle_of_three_fresh_blocks(self):
        fixture = Fixture()
        fixture.game(1, home=[1, 2], away=[11, 12], y_xt=0.5, goals_home=0.5)
        fixture.game(2, home=[5, 6], away=[11, 12], y_xt=0.5, goals_home=0.5)
        result = fixture.game(3, home=[7, 1, 8], away=[11, 12], y_xt=0.5, goals_home=0.5)

        assert result is not None
        assert fixture.state.n_players == 8

    def test_repeated_roots_stay_exact(self):
        fixture = Fixture(ridge=0.4)
        fixture.game(1, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
        fixture.game(2, home=[1, 2], away=[11, 12], y_xt=-2.0, goals_home=0.5)
        fixture.game(3, home=[3, 1, 2], away=[13, 14], y_xt=1.5, goals_home=-1.0)

        for dv in _DVS:
            expected = fixture.dense_solve(dv)
            for player_id, value in expected.items():
                assert fixture.state.ratings(dv)[player_id] == pytest.approx(value, abs=1e-9)


class TestAlreadyAbsorbed:
    def test_second_observe_returns_none_and_leaves_state_untouched(self):
        fixture = Fixture()
        first = fixture.game(7, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
        snapshot = {dv: fixture.state.ratings(dv) for dv in _DVS}

        second = fixture.game(7, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)

        assert first is not None
        assert second is None
        assert list(fixture.state.absorbed_game_ids) == [7]
        for dv in _DVS:
            assert fixture.state.ratings(dv) == snapshot[dv]

    def test_a_skipped_game_does_not_advance_later_ratings(self):
        fixture = Fixture()
        fixture.game(1, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
        fixture.game(2, home=[1, 2], away=[11, 12], y_xt=5.0, goals_home=5.0)
        fixture.game(2, home=[1, 2], away=[11, 12], y_xt=5.0, goals_home=5.0)
        fixture.game(3, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)

        replay = Fixture()
        replay.game(1, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
        replay.game(3, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)

        for dv in _DVS:
            assert fixture.state.ratings(dv) == pytest.approx(replay.state.ratings(dv))


class TestExactnessAgainstDenseSolve:
    @pytest.mark.parametrize("dummy", [True, False])
    @pytest.mark.parametrize("ridge", [0.1, 1.0, 5.0])
    def test_matches_an_independently_built_dense_solve(self, dummy, ridge):
        fixture = random_games(Fixture(ridge=ridge, dummy=dummy), 30, list(range(1, 13)), 4, seed=7)

        for dv in _DVS:
            expected = fixture.dense_solve(dv)
            actual = fixture.state.ratings(dv)
            assert set(actual) == set(expected)
            for player_id, value in expected.items():
                assert actual[player_id] == pytest.approx(value, abs=1e-9)

    def test_uniform_weights_also_match(self):
        fixture = random_games(Fixture(ridge=0.3, weight_mode="uniform"), 20, list(range(1, 11)), 3, seed=13)

        for dv in _DVS:
            for player_id, value in fixture.dense_solve(dv).items():
                assert fixture.state.ratings(dv)[player_id] == pytest.approx(value, abs=1e-9)


class TestPlantedCoefficients:
    def test_recovers_known_effects_relative_to_the_average_player(self):
        true_thetas = {1: 0.30, 2: -0.20, 3: 0.10, 11: 0.05, 12: -0.05, 13: 0.15, 14: 0.0, 15: -0.10}
        fixture = Fixture(ridge=1e-6, dummy=False)
        rng = np.random.default_rng(11)
        pool = list(true_thetas)
        for game_id in range(1, 401):
            home = sorted(rng.choice(pool, 4, replace=False).tolist())
            away = sorted(rng.choice(pool, 4, replace=False).tolist())
            y = sum(true_thetas[player] for player in home) - sum(true_thetas[player] for player in away)
            fixture.game(game_id, home=home, away=away, y_xt=y, goals_home=y)

        ratings = fixture.state.ratings("xt")
        average = sum(true_thetas.values()) / len(true_thetas)
        for player_id, truth in true_thetas.items():
            assert ratings[player_id] == pytest.approx(truth - average, abs=0.02)


class TestBlockDecomposition:
    def test_disjoint_pools_stay_separate(self):
        fixture = Fixture()
        for game_id in range(1, 6):
            fixture.game(game_id, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
            fixture.game(100 + game_id, home=[3, 4], away=[13, 14], y_xt=-1.0, goals_home=-1.0)

        assert len(fixture.state._blocks) == 2
        assert set(fixture.state.ratings("xt")) == {1, 2, 3, 4, 11, 12, 13, 14}

    def test_separate_blocks_still_match_the_dense_solve(self):
        fixture = Fixture(ridge=0.7)
        for game_id in range(1, 8):
            fixture.game(game_id, home=[1, 2, 3], away=[11, 12], y_xt=float(game_id), goals_home=0.5)
            fixture.game(100 + game_id, home=[4, 5], away=[13], y_xt=-1.0, goals_home=-0.5)

        assert len(fixture.state._blocks) == 2
        for dv in _DVS:
            for player_id, value in fixture.dense_solve(dv).items():
                assert fixture.state.ratings(dv)[player_id] == pytest.approx(value, abs=1e-9)


class TestForgetting:
    def test_total_weight_follows_the_geometric_sum(self):
        fixture = random_games(Fixture(forgetting=0.9), 40, list(range(1, 9)), 4, seed=3)
        forever = random_games(Fixture(forgetting=1.0), 40, list(range(1, 9)), 4, seed=3)

        # Each game discounts the previous state by gamma, so the total is sum(w_i * gamma^(N-i)).
        expected = sum(row[2] * 0.9 ** (len(fixture.rows) - 1 - index) for index, row in enumerate(fixture.rows))
        assert float(fixture.state._n) == pytest.approx(expected, rel=1e-9)
        assert float(fixture.state._n) < float(forever.state._n)

    def test_discounting_lets_a_recent_outlier_move_the_rating_further(self):
        def rating_after_outlier(forgetting):
            fixture = random_games(Fixture(forgetting=forgetting), 30, list(range(1, 9)), 4, seed=5)
            fixture.game(999, home=[1, 2, 3, 4], away=[5, 6, 7, 8], y_xt=50.0, goals_home=1, goals_away=0)
            return fixture.state.ratings("xt")[1]

        assert rating_after_outlier(0.9) > rating_after_outlier(1.0)

    def test_discounting_keeps_every_player_solved(self):
        fixture = random_games(Fixture(ridge=0.5, forgetting=0.85), 25, list(range(1, 11)), 3, seed=17)

        for dv in _DVS:
            assert set(fixture.state.ratings(dv)) == fixture.players


class TestPersistence:
    def test_round_trip_is_exact_and_preserves_absorbed_games(self, tmp_path):
        fixture = random_games(Fixture(ridge=0.8), 15, list(range(1, 9)), 3, seed=23)

        loaded = XtPlusMinus.load(fixture.state.save(tmp_path / "state.npz"))

        assert loaded.n_players == fixture.state.n_players
        assert set(loaded.absorbed_game_ids) == set(fixture.state.absorbed_game_ids)
        for dv in _DVS:
            expected = fixture.state.ratings(dv)
            actual = loaded.ratings(dv)
            assert set(actual) == set(expected)
            for player_id, value in expected.items():
                assert actual[player_id] == value

    def test_loaded_state_keeps_absorbing_without_replaying(self, tmp_path):
        source = random_games(Fixture(), 5, list(range(1, 9)), 3, seed=29)
        loaded = Fixture(state=XtPlusMinus.load(source.state.save(tmp_path / "state.npz")))
        replay = random_games(Fixture(), 5, list(range(1, 9)), 3, seed=29)

        loaded.game(6, home=[1, 2], away=[11, 12], y_xt=2.0, goals_home=1.0)
        replay.game(6, home=[1, 2], away=[11, 12], y_xt=2.0, goals_home=1.0)

        for dv in _DVS:
            assert loaded.state.ratings(dv) == pytest.approx(replay.state.ratings(dv))

        for dv in _DVS:
            assert loaded.state.ratings(dv) == pytest.approx(replay.state.ratings(dv))

    def test_ridge_is_applied_at_solve_time_so_it_can_change_afterwards(self, tmp_path):
        fixture = random_games(Fixture(ridge=0.01), 20, list(range(1, 11)), 4, seed=31)

        loaded = XtPlusMinus.load(fixture.state.save(tmp_path / "state.npz"))
        assert loaded.ridge == 0.01

        original = fixture.state.ratings("xt")
        loaded.ridge = 500.0
        shrunk = loaded.ratings("xt")

        assert shrunk != original
        assert sum(value * value for value in shrunk.values()) < sum(value * value for value in original.values())

    def test_raising_the_ridge_pulls_every_rating_towards_zero(self, tmp_path):
        fixture = random_games(Fixture(ridge=0.01), 20, list(range(1, 11)), 4, seed=31)
        loaded = XtPlusMinus.load(fixture.state.save(tmp_path / "state.npz"))

        wide = loaded.ratings("xt")
        loaded.ridge = 10_000.0
        narrow = loaded.ratings("xt")

        assert max(abs(value) for value in narrow.values()) < max(abs(value) for value in wide.values())


class TestPrediction:
    def test_predicted_value_matches_the_rating_sums(self):
        fixture = random_games(Fixture(), 20, list(range(1, 9)), 3, seed=37)

        for dv in _DVS:
            ratings = fixture.state.ratings(dv)
            expected = ratings[1] + ratings[2] - ratings[3] - ratings[4]
            assert fixture.state.predict_goal_diff([1, 2], [3, 4], 90.0, dv) == pytest.approx(expected)

    def test_minutes_scale_the_prediction(self):
        fixture = random_games(Fixture(), 20, list(range(1, 9)), 3, seed=41)

        full = fixture.state.predict_goal_diff([1, 2], [3, 4], 90.0, "xt")
        assert fixture.state.predict_goal_diff([1, 2], [3, 4], 45.0, "xt") == pytest.approx(full * 0.5)


class TestRatingsApi:
    def test_unknown_dependent_variable_raises(self):
        fixture = Fixture()
        with pytest.raises(ValueError, match="unknown dependent variable"):
            fixture.state.ratings("nonsense")

    def test_column_of_is_stable_and_sequential(self):
        fixture = Fixture()
        assert fixture.state.column_of(42) == fixture.state.column_of(42)
        first = fixture.state.column_of(1)
        assert fixture.state.column_of(2) == first + 1

    def test_ratings_cover_every_player_seen_so_far(self):
        fixture = Fixture()
        fixture.game(1, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
        fixture.game(2, home=[3, 4], away=[13, 14], y_xt=1.0, goals_home=1.0)

        assert set(fixture.state.ratings("xt")) == {1, 2, 3, 4, 11, 12, 13, 14}

    def test_observe_reports_only_players_who_appeared_in_that_game(self):
        fixture = Fixture()
        fixture.game(1, home=[1, 2], away=[11, 12], y_xt=1.0, goals_home=1.0)
        result = fixture.game(2, home=[3, 4], away=[13, 14], y_xt=1.0, goals_home=1.0)

        assert set(result) == {3, 4, 13, 14}
        assert set(result[3]) >= {"xt", "gd", "xt_credit", "gd_credit"}
