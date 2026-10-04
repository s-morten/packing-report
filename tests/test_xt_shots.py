import numpy as np
import pandas as pd
import pytest
from football_data_utils import goal_mask
from metrics.low_level.xt import rate_shots
from socceraction.spadl import config as spadl_config

SHOT = spadl_config.actiontypes.index("shot")
PASS = spadl_config.actiontypes.index("pass")


def cell_of(model, x, y):
    """The (row, column) a shot at ``(x, y)`` is priced from.

    Mirrors socceraction's mapping, including the y-axis flip ``w - 1 - row`` that the xT grid
    applies so row 0 is the far touchline.
    """
    column = min(int(x / spadl_config.field_length * model.l), model.l - 1)
    raw_row = min(max(int(y / spadl_config.field_width * model.w), 0), model.w - 1)
    return model.w - 1 - raw_row, column


class FakeXt:
    """Minimal stand-in exposing only what :func:`rate_shots` touches.

    The cell values and scoring probabilities are set to unique, recognisable numbers so a test can
    assert exactly which cell a shot was priced from, rather than only that *some* finite number
    came back.
    """

    def __init__(self, n_rows=12, n_cols=8, xT=None, scoring_prob=None):
        self.l = n_rows
        self.w = n_cols
        self.xT = np.arange(n_rows * n_cols, dtype=float).reshape(n_cols, n_rows) / 100.0 if xT is None else xT
        self.scoring_prob_matrix = (
            np.linspace(0.01, 0.4, n_rows * n_cols).reshape(n_cols, n_rows) if scoring_prob is None else scoring_prob
        )


def actions_frame(rows):
    """``rows`` are ``(type_id, start_x, start_y)``; ``end_x/end_y`` mirror ``start``."""
    frame = pd.DataFrame(
        {
            "type_id": [row[0] for row in rows],
            "start_x": [row[1] for row in rows],
            "start_y": [row[2] for row in rows],
        }
    )
    frame["end_x"] = frame["start_x"]
    frame["end_y"] = frame["start_y"]
    return frame


class TestRateShots:
    def test_empty_frame_returns_an_empty_all_nan_array(self):
        ratings = rate_shots(actions_frame([]), FakeXt())
        assert ratings.shape == (0,)
        assert np.isnan(ratings).all()

    def test_non_shot_rows_are_nan(self):
        frame = actions_frame([(PASS, 40.0, 20.0), (PASS, 60.0, 30.0)])

        ratings = rate_shots(frame, FakeXt())

        assert np.isnan(ratings).all()

    def test_a_shot_is_priced_as_scoring_probability_minus_its_own_cell_value(self):
        model = FakeXt()
        # 60/105 of the field length, 40/68 of the width -> cell (7, 4) at l=12, w=8.
        frame = actions_frame([(SHOT, 60.0, 40.0)])

        ratings = rate_shots(frame, model)

        row, column = cell_of(model, 60.0, 40.0)
        p_goal = model.scoring_prob_matrix[row, column]
        assert ratings[0] == pytest.approx(p_goal - model.xT[row, column])
        # The cell value is genuinely subtracted, not merely added somewhere else.
        assert ratings[0] < p_goal

    def test_values_stay_positionally_aligned_with_the_input_frame(self):
        model = FakeXt()
        frame = actions_frame(
            [
                (PASS, 30.0, 20.0),
                (SHOT, 60.0, 40.0),
                (PASS, 50.0, 10.0),
                (SHOT, 90.0, 34.0),
            ]
        )

        ratings = rate_shots(frame, model)

        assert np.isnan(ratings[[0, 2]]).all()
        for row, (x, y) in ((1, (60.0, 40.0)), (3, (90.0, 34.0))):
            cell_y, cell_x = cell_of(model, x, y)
            assert ratings[row] == pytest.approx(model.scoring_prob_matrix[cell_y, cell_x] - model.xT[cell_y, cell_x])

    def test_out_of_range_coordinates_are_clamped_rather_than_wrapping(self):
        model = FakeXt()
        # start_x beyond the field must clamp to the last column, not wrap to column 0.
        frame = actions_frame([(SHOT, 500.0, -40.0)])

        ratings = rate_shots(frame, model)

        row, column = cell_of(model, 500.0, -40.0)
        assert (row, column) == (model.w - 1, model.l - 1)
        assert ratings[0] == pytest.approx(model.scoring_prob_matrix[row, column] - model.xT[row, column])

    def test_the_xg_model_overrides_the_placeholder_probability(self):
        model = FakeXt()
        frame = actions_frame([(SHOT, 60.0, 40.0), (PASS, 10.0, 10.0), (SHOT, 90.0, 34.0)])

        class StubXg:
            def predict(self, actions):
                # The whole frame, not the shot rows: the xG features read backwards from the shot.
                assert len(actions) == 3, "predict must receive the whole action frame"
                return np.array([0.42, 0.07])

        ratings = rate_shots(frame, model, StubXg())

        for row, (x, y, p_goal) in ((0, (60.0, 40.0, 0.42)), (2, (90.0, 34.0, 0.07))):
            cell_y, cell_x = cell_of(model, x, y)
            assert ratings[row] == pytest.approx(p_goal - model.xT[cell_y, cell_x])
        assert np.isnan(ratings[1])

    def test_a_wrong_length_prediction_raises(self):
        frame = actions_frame([(SHOT, 60.0, 40.0), (SHOT, 90.0, 34.0)])

        class ShortXg:
            def predict(self, actions):
                return np.array([0.5])

        with pytest.raises(ValueError, match="returned 1 values for 2 shots"):
            rate_shots(frame, FakeXt(), ShortXg())

    def test_subtracting_the_cell_value_is_what_makes_a_possession_telescope(self):
        """``p - xT`` rather than ``p``, so the cell is not credited twice.

        A chance built from two moves into the same cell must score the end-cell xT once: the pass
        that entered the cell contributes the xT difference between cells, and the shot from inside
        it must contribute only its scoring probability.
        """
        model = FakeXt()
        start_x, start_y = 60.0, 40.0
        # The move that carried the ball into the shot's cell, starting one cell back.
        origin_x, origin_y = 30.0, 20.0

        end_row, end_col = cell_of(model, start_x, start_y)
        from_row, from_col = cell_of(model, origin_x, origin_y)
        # ExpectedThreat.rate prices a move as the xT of the cell it ends in minus the cell it
        # starts in; the shot then supplies only the scoring probability.
        move_value = model.xT[end_row, end_col] - model.xT[from_row, from_col]
        shot_value = rate_shots(actions_frame([(SHOT, start_x, start_y)]), model)[0]

        assert move_value == pytest.approx(model.xT[end_row, end_col] - model.xT[from_row, from_col])
        assert shot_value == pytest.approx(model.scoring_prob_matrix[end_row, end_col] - model.xT[end_row, end_col])
        # The end cell's xT is paid exactly once, by the move that entered it.
        assert move_value + shot_value == pytest.approx(
            model.scoring_prob_matrix[end_row, end_col] - model.xT[from_row, from_col]
        )


class TestGoalMask:
    def test_nan_entries_do_not_make_the_mask_raise(self):
        events = pd.DataFrame({"is_goal": [True, np.nan, np.nan, True]}, dtype=object)

        mask = goal_mask(events)

        assert mask.dtype == bool
        assert mask.tolist() == [True, False, False, True]

    def test_an_all_nan_column_masks_everything_out(self):
        events = pd.DataFrame({"is_goal": [np.nan] * 3}, dtype=object)

        assert goal_mask(events).tolist() == [False, False, False]

    def test_plain_boolean_columns_are_unchanged(self):
        events = pd.DataFrame({"is_goal": [True, False, True]})

        assert goal_mask(events).tolist() == [True, False, True]

    def test_numeric_one_and_zero_are_read_as_goal_flags(self):
        # 1 == True in Python, so a 1/0 column masks correctly as well as a True/NaN one.
        events = pd.DataFrame({"is_goal": [1, 0, 1]}, dtype=object)

        assert goal_mask(events).tolist() == [True, False, True]
