import dataclasses

import numpy as np
import pytest
from metrics.high_level.xtpm.features import (
    HOME_ADVANTAGE_COLUMN,
    FeatureSpec,
    Observation,
    build_observation,
    dependent_variables,
    design_row,
    segment_weight,
)


class _ColumnMapper:
    """Stand-in for ``XtPlusMinus.column_of``: first-come, first-served column assignment."""

    def __init__(self):
        self.mapping = {}
        self.calls = []

    def __call__(self, player_id):
        self.calls.append(player_id)
        if player_id not in self.mapping:
            self.mapping[player_id] = len(self.mapping) + 1  # column 0 is the home-advantage dummy
        return self.mapping[player_id]


def column_mapper():
    return _ColumnMapper()


class TestDesignRow:
    def test_home_is_plus_one_and_away_is_minus_one(self):
        indices, values = design_row([10, 11], [20, 21], column_mapper(), FeatureSpec(home_advantage_dummy=False))

        assert indices.tolist() == [1, 2, 3, 4]
        assert values.tolist() == [1.0, 1.0, -1.0, -1.0]

    def test_home_advantage_dummy_is_column_zero_with_value_one(self):
        indices, values = design_row([10], [20], column_mapper())

        assert HOME_ADVANTAGE_COLUMN == 0
        assert indices[0] == HOME_ADVANTAGE_COLUMN
        assert values[0] == 1.0
        assert indices.tolist() == sorted(indices.tolist())

    def test_absent_player_is_implicitly_zero(self):
        columns = column_mapper()
        design_row([10, 11], [20], columns, FeatureSpec(home_advantage_dummy=False))
        design_row([10, 12], [20], columns, FeatureSpec(home_advantage_dummy=False))

        # Player 11 was in the first segment only, so it has a column; no column is ever created for
        # a player who never appears, because absent means x[p] == 0 rather than a column of zero.
        assert sorted(columns.mapping) == [10, 11, 12, 20]

    def test_column_of_called_once_per_distinct_player(self):
        columns = column_mapper()

        design_row([10, 11, 10], [20, 20], columns, FeatureSpec(home_advantage_dummy=False))

        assert sorted(columns.calls) == [10, 11, 20]

    def test_repeated_player_on_one_side_collapses_to_one_entry(self):
        indices, values = design_row([10, 10], [20], column_mapper(), FeatureSpec(home_advantage_dummy=False))

        # A player cannot legitimately be listed twice within a side; the per-side de-duplication
        # makes that harmless rather than double-weighting them.
        assert len(indices) == len(set(indices.tolist()))
        assert sorted(values.tolist()) == [-1.0, 1.0]

    def test_player_on_both_sides_sums_to_zero(self):
        # Pathological input, but the column sums must stay well defined if it ever happens.
        indices, values = design_row([10], [10], column_mapper(), FeatureSpec(home_advantage_dummy=False))

        assert len(indices) == 1
        assert values.tolist() == [0.0]

    def test_empty_sides_still_yields_the_dummy(self):
        indices, values = design_row([], [], column_mapper())

        assert indices.tolist() == [HOME_ADVANTAGE_COLUMN]
        assert values.tolist() == [1.0]


class TestSegmentWeight:
    def test_duration_mode_divides_by_ninety(self):
        assert segment_weight(45, "duration") == pytest.approx(0.5)
        assert segment_weight(90, "duration") == pytest.approx(1.0)
        assert segment_weight(9, "duration") == pytest.approx(0.1)

    def test_uniform_mode_is_one(self):
        assert segment_weight(45, "uniform") == pytest.approx(1.0)
        assert segment_weight(1, "uniform") == pytest.approx(1.0)

    def test_zero_or_negative_duration_raises(self):
        with pytest.raises(ValueError, match="duration must be positive"):
            segment_weight(0, "duration")
        with pytest.raises(ValueError, match="duration must be positive"):
            segment_weight(-5, "duration")

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="unknown weight_mode"):
            segment_weight(45, "sqrt")


class TestDependentVariables:
    def test_both_arms_are_per_ninety(self):
        y_xt, y_gd = dependent_variables(net_xt_per90=2.0, goals_home=1, goals_away=0, duration_minutes=45)

        assert y_xt == pytest.approx(2.0)
        assert y_gd == pytest.approx(2.0)

    def test_goal_difference_is_signed_home_minus_away(self):
        _, y_gd = dependent_variables(0.0, goals_home=0, goals_away=2, duration_minutes=90)
        assert y_gd == pytest.approx(-2.0)

    def test_short_segment_is_scaled_up(self):
        # One goal in an 18-minute window left behind by an early red card: 5.0 per 90.
        _, y_gd = dependent_variables(0.0, goals_home=1, goals_away=0, duration_minutes=18)
        assert y_gd == pytest.approx(5.0)

    def test_no_goals_gives_zero_regardless_of_length(self):
        _, y_gd = dependent_variables(1.5, goals_home=0, goals_away=0, duration_minutes=7)
        assert y_gd == 0.0


class TestBuildObservation:
    def test_assembles_design_weight_and_both_arms(self):
        observation = build_observation(
            home=[10, 11],
            away=[20],
            net_xt_per90=1.5,
            goals_home=1,
            goals_away=0,
            duration_minutes=45,
            column_of=column_mapper(),
        )

        assert isinstance(observation, Observation)
        assert observation.weight == pytest.approx(0.5)
        assert observation.y_xt == pytest.approx(1.5)
        assert observation.y_gd == pytest.approx(2.0)
        assert len(observation.indices) == len(observation.values) == 4  # dummy + 3 players

    def test_observation_is_frozen(self):
        observation = build_observation([10], [20], 0.0, 0, 0, 90, column_mapper())
        with pytest.raises(dataclasses.FrozenInstanceError):
            observation.weight = 2.0  # type: ignore[misc]

    def test_indices_and_values_are_numpy_arrays(self):
        observation = build_observation([10], [20], 0.0, 0, 0, 90, column_mapper())

        assert isinstance(observation.indices, np.ndarray)
        assert isinstance(observation.values, np.ndarray)
