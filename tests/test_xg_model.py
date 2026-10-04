import itertools
import pickle

import numpy as np
import pandas as pd
import pytest
from metrics.low_level.xg import (
    ASSIST_COLUMNS,
    ASSIST_GAP_CAP,
    FEATURE_SETS,
    XgRegressor,
    build_features,
    non_penalty_shot_mask,
    penalty_mask,
    shot_mask,
    smoothed_rate,
)
from metrics.low_level.xt import rate_shots
from socceraction.spadl import config as spadl_config
from xgboost import XGBClassifier

SHOT = spadl_config.actiontypes.index("shot")
PENALTY = spadl_config.actiontypes.index("shot_penalty")
FREEKICK = spadl_config.actiontypes.index("shot_freekick")
PASS = spadl_config.actiontypes.index("pass")
CORNER = spadl_config.actiontypes.index("corner_crossed")
FAIL = spadl_config.results.index("fail")
SUCCESS = spadl_config.results.index("success")
FOOT_RIGHT = spadl_config.bodyparts.index("foot_right")
HEAD = spadl_config.bodyparts.index("head")

GOAL_X = spadl_config.field_length
GOAL_HALF_WIDTH = 7.32 / 2


def action(
    type_id,
    team_id=1,
    player_id=10,
    x=50.0,
    y=34.0,
    end_x=None,
    end_y=None,
    result_id=FAIL,
    game_id="g1",
    period_id=1,
    time_seconds=0.0,
    bodypart_id=FOOT_RIGHT,
):
    """One SPADL row, with the defaults that keep the common case a one-liner."""
    return {
        "game_id": game_id,
        "period_id": period_id,
        "time_seconds": time_seconds,
        "team_id": team_id,
        "player_id": player_id,
        "start_x": x,
        "start_y": y,
        "end_x": x if end_x is None else end_x,
        "end_y": y if end_y is None else end_y,
        "type_id": type_id,
        "result_id": result_id,
        "bodypart_id": bodypart_id,
    }


def spadl_frame(rows):
    return pd.DataFrame(rows)


def column(frame, name):
    return frame[name].to_numpy(dtype=float)


class TestShotMasks:
    def test_the_three_shot_types_are_recognised_and_nothing_else_is(self):
        frame = spadl_frame(
            [
                action(PASS),
                action(SHOT),
                action(PENALTY),
                action(FREEKICK),
                action(spadl_config.actiontypes.index("take_on")),
            ]
        )

        assert shot_mask(frame).tolist() == [False, True, True, True, False]
        assert penalty_mask(frame).tolist() == [False, False, True, False, False]
        assert non_penalty_shot_mask(frame).tolist() == [False, True, False, True, False]

    def test_the_masks_return_plain_boolean_arrays(self):
        # Every caller indexes raw numpy positionally, so a masked pandas object would silently
        # shift each lookup by one.
        frame = spadl_frame([action(SHOT), action(PASS)])

        assert shot_mask(frame).dtype == np.bool_
        assert non_penalty_shot_mask(frame).dtype == np.bool_


class TestBuildFeatures:
    def test_one_row_per_non_penalty_shot_in_frame_order(self):
        frame = spadl_frame(
            [
                action(PASS, x=10.0, y=10.0),
                action(PENALTY, x=101.0, y=34.0),
                action(SHOT, x=90.0, y=34.0, player_id=11),
                action(FREEKICK, x=95.0, y=30.0, player_id=12),
                action(PASS, x=20.0, y=20.0),
                action(SHOT, x=60.0, y=34.0, player_id=13),
            ]
        )

        features = build_features(frame, "full")

        assert features["start_x"].tolist() == [90.0, 95.0, 60.0]

    def test_columns_and_order_are_exactly_the_declared_feature_set(self):
        frame = spadl_frame([action(PASS, end_x=90.0, end_y=34.0), action(SHOT, x=90.0, y=34.0)])

        for name, expected in FEATURE_SETS.items():
            assert list(build_features(frame, name).columns) == list(expected)

    def test_the_full_set_is_the_base_set_plus_the_lookback_block(self):
        extra = set(FEATURE_SETS["full"]) - set(FEATURE_SETS["base"])

        assert extra == set(ASSIST_COLUMNS) | {
            "assist_travel_dist",
            "assist_failed",
            "time_since_assist",
            "actions_since_team_change",
            "defenders_within_radius",
            "teammates_within_radius",
            "minutes_on_pitch",
            "is_substitute",
        }
        assert not [name for name in FEATURE_SETS["base"] if name.startswith("assist_")]

    def test_the_two_feature_sets_agree_on_their_shared_columns(self):
        frame = spadl_frame(
            [
                action(PASS, x=20.0, y=20.0, end_x=88.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, x=88.0, y=30.0),
                action(SHOT, x=55.0, y=12.0, player_id=11),
            ]
        )

        base = build_features(frame, "base")
        full = build_features(frame, "full")

        pd.testing.assert_frame_equal(base, full[list(FEATURE_SETS["base"])])

    def test_a_frame_without_shots_yields_an_empty_but_correctly_shaped_frame(self):
        features = build_features(spadl_frame([action(PASS), action(PASS)]), "full")

        assert features.empty
        assert list(features.columns) == list(FEATURE_SETS["full"])

    def test_a_frame_containing_only_penalties_yields_no_rows(self):
        features = build_features(spadl_frame([action(PENALTY), action(PENALTY)]), "full")

        assert features.empty

    def test_an_unknown_feature_set_is_rejected_by_name(self):
        with pytest.raises(ValueError, match="Unknown feature_set 'rich'"):
            build_features(spadl_frame([action(SHOT)]), "rich")

    def test_missing_spadl_columns_are_named_in_the_error(self):
        frame = spadl_frame([action(SHOT)]).drop(columns=["period_id", "bodypart_id"])

        with pytest.raises(ValueError, match=r"missing: \['period_id', 'bodypart_id'\]"):
            build_features(frame, "full")

    def test_the_output_is_indexed_like_its_own_shot_rows(self):
        frame = spadl_frame(
            [action(PASS, x=10.0, y=10.0), action(SHOT, x=88.0, y=30.0), action(SHOT, x=60.0, player_id=11)]
        )

        assert build_features(frame, "full").index.tolist() == [1, 2]

    def test_unrecorded_end_coordinates_do_not_leak_nan_into_the_lookback_features(self):
        # A shot's own location is always recorded, but the *assist's* is routinely not: throw-ins,
        # clearances and goalkeeper distributions leave ``end_x``/``end_y`` empty, and an action with
        # no known end position must count as "not nearby" rather than poison the row with a NaN.
        frame = spadl_frame(
            [
                action(PASS, x=10.0, y=10.0, end_x=np.nan, end_y=np.nan),
                action(PASS, x=20.0, y=20.0, end_x=np.nan, end_y=np.nan, player_id=11),
                action(SHOT, x=88.0, y=30.0, player_id=20),
            ]
        )

        features = build_features(frame, "full")

        assert np.isfinite(features.to_numpy(dtype=float)).all()
        assert column(features, "assist_travel_dist") == pytest.approx([0.0])
        assert column(features, "defenders_within_radius") == pytest.approx([0.0])

    def test_the_gap_to_the_assist_is_nan_when_there_is_no_assist_to_measure(self):
        # A rebound off a save, and the opening row of a frame, have no assist. Encoding that as a
        # zero-second gap would read as "struck on the move", so the column stays missing instead and
        # the assist one-hots say what happened instead.
        frame = spadl_frame(
            [
                action(PASS, team_id=2, x=20.0, y=20.0, end_x=88.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, team_id=1, x=88.0, y=30.0),
                action(SHOT, team_id=1, x=70.0, y=30.0, player_id=11),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "assist_loose_ball") == pytest.approx([1.0, 0.0])
        assert np.isnan(column(features, "time_since_assist")[0])
        assert np.isfinite(column(features, "time_since_assist")[1])

    def test_the_gap_is_measured_in_seconds_between_the_two_rows(self):
        frame = spadl_frame(
            [
                # 2 s before the shot.
                action(PASS, x=60.0, y=34.0, end_x=88.0, end_y=30.0, result_id=SUCCESS, time_seconds=100.0),
                action(SHOT, x=88.0, y=30.0, time_seconds=102.0),
            ]
        )

        assert column(build_features(frame, "full"), "time_since_assist") == pytest.approx([2.0])

    def test_the_gap_is_measured_across_the_period_break(self):
        # ``time_seconds`` restarts at 0 in the second half, so the gap has to come from match-absolute
        # minutes or a first-half-to-second-half possession reads as a huge negative.
        frame = spadl_frame(
            [
                action(
                    PASS, x=60.0, y=34.0, end_x=88.0, end_y=30.0, result_id=SUCCESS, period_id=1, time_seconds=2695.0
                ),
                action(SHOT, x=88.0, y=30.0, period_id=2, time_seconds=5.0),
            ]
        )

        assert column(build_features(frame, "full"), "time_since_assist") == pytest.approx([10.0])

    def test_the_gap_is_capped(self):
        frame = spadl_frame(
            [
                action(PASS, x=60.0, y=34.0, end_x=88.0, end_y=30.0, result_id=SUCCESS, time_seconds=0.0),
                action(SHOT, x=88.0, y=30.0, time_seconds=900.0),
            ]
        )

        assert column(build_features(frame, "full"), "time_since_assist") == pytest.approx([ASSIST_GAP_CAP])

    def test_a_shot_struck_in_the_same_second_reads_as_zero_not_missing(self):
        frame = spadl_frame(
            [
                action(PASS, x=60.0, y=34.0, end_x=88.0, end_y=30.0, result_id=SUCCESS, time_seconds=100.0),
                action(SHOT, x=88.0, y=30.0, time_seconds=100.0),
            ]
        )

        gap = column(build_features(frame, "full"), "time_since_assist")

        assert gap[0] == pytest.approx(0.0)
        assert np.isfinite(gap[0])

    def test_a_relabelled_index_does_not_shift_the_lookback_window(self):
        # Lookups are positional, so a frame that arrived from a concat or a filter -- and therefore
        # carries someone else's index labels -- must still read the action that really preceded it.
        frame = spadl_frame(
            [
                action(PASS, x=10.0, y=10.0, end_x=88.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, x=88.0, y=30.0),
                action(SHOT, x=60.0, y=34.0, player_id=11),
            ]
        )
        relabelled = frame.copy()
        relabelled.index = [91, 3, 7]

        expected = build_features(frame, "full")
        actual = build_features(relabelled, "full")

        assert np.allclose(actual.to_numpy(dtype=float), expected.to_numpy(dtype=float))


class TestGeometry:
    def test_distances_measure_to_each_post_as_well_as_to_the_centre(self):
        frame = spadl_frame([action(SHOT, x=98.0, y=34.0)])

        features = build_features(frame, "base")

        assert column(features, "dist_to_goal_centre") == pytest.approx(7.0)
        assert column(features, "dist_to_near_post") == pytest.approx(np.hypot(7.0, GOAL_HALF_WIDTH))
        assert column(features, "dist_to_far_post") == pytest.approx(np.hypot(7.0, GOAL_HALF_WIDTH))

    def test_the_two_post_columns_separate_the_near_side_from_the_far_side(self):
        # A shot from the left of the goalmouth is close to the left post and far from the right one.
        # Collapsing them into a single "distance to goal" is exactly the signal that gets lost.
        frame = spadl_frame([action(SHOT, x=99.0, y=31.0)])

        features = build_features(frame, "base")

        assert column(features, "dist_to_near_post") < column(features, "dist_to_far_post")
        assert column(features, "abs_y_from_centre") == pytest.approx(3.0)

    def test_the_angle_saturates_on_the_byline(self):
        frame = spadl_frame([action(SHOT, x=GOAL_X, y=34.0), action(SHOT, x=90.0, y=34.0, player_id=11)])

        angles = column(build_features(frame, "base"), "angle_to_goal")

        assert angles[0] == pytest.approx(np.pi / 2)
        assert angles[1] < angles[0]

    def test_distance_falls_monotonically_further_from_goal(self):
        frame = spadl_frame(
            [
                action(SHOT, x=GOAL_X, y=34.0),
                action(SHOT, x=95.0, y=34.0, player_id=11),
                action(SHOT, x=50.0, y=34.0, player_id=12),
                action(SHOT, x=10.0, y=34.0, player_id=13),
            ]
        )

        distances = column(build_features(frame, "base"), "dist_to_goal_centre")

        assert distances.tolist() == sorted(distances)

    def test_the_body_part_and_the_free_kick_flag_are_carried_through(self):
        frame = spadl_frame(
            [
                action(SHOT, x=90.0, y=34.0, bodypart_id=HEAD),
                action(FREEKICK, x=80.0, y=40.0, player_id=11, bodypart_id=FOOT_RIGHT),
            ]
        )

        features = build_features(frame, "base")

        assert column(features, "bodypart_id") == pytest.approx([float(HEAD), float(FOOT_RIGHT)])
        assert column(features, "is_free_kick") == pytest.approx([0.0, 1.0])


class TestLookback:
    def test_the_assist_type_is_read_off_the_preceding_action(self):
        # Each shot is preceded by its own assist: in SPADL a shot's ``start`` *is* the previous
        # action's ``end``, so the row directly above is the ball carrier.
        frame = spadl_frame(
            [
                action(PASS, x=20.0, y=20.0, end_x=88.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, x=88.0, y=30.0),
                action(CORNER, x=10.0, y=5.0, end_x=80.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, x=80.0, y=30.0, player_id=11),
                action(PASS, x=30.0, y=30.0, end_x=70.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, x=70.0, y=30.0, player_id=12),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "assist_pass") == pytest.approx([1.0, 0.0, 1.0])
        assert column(features, "assist_corner_crossed") == pytest.approx([0.0, 1.0, 0.0])

    def test_a_change_of_possession_is_labelled_a_loose_ball_rather_than_back_walked(self):
        # The keeper save or blocked shot that precedes a rebound is a real category, not a gap to be
        # papered over by reaching further back for an assist the shot never had.
        frame = spadl_frame(
            [
                action(PASS, team_id=2, x=20.0, y=20.0, end_x=88.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, team_id=1, x=88.0, y=30.0),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "assist_loose_ball") == pytest.approx([1.0])
        assert column(features, "assist_pass") == pytest.approx([0.0])

    def test_a_shot_that_opens_the_frame_has_no_assist_at_all(self):
        frame = spadl_frame([action(SHOT, x=88.0, y=30.0)])

        features = build_features(frame, "full")

        assert column(features, "assist_none") == pytest.approx([1.0])
        assert column(features, "assist_loose_ball") == pytest.approx([0.0])
        assert column(features, "assist_travel_dist") == pytest.approx([0.0])

    def test_an_unsuccessful_assist_is_flagged(self):
        # The strongest lookback signal in the 2021/22 sample: a rebound converts at roughly twice the
        # rate of a chance built on a completed pass.
        frame = spadl_frame(
            [
                action(PASS, x=20.0, y=20.0, end_x=88.0, end_y=30.0, result_id=FAIL),
                action(SHOT, x=88.0, y=30.0),
                action(PASS, x=30.0, y=30.0, end_x=70.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, x=70.0, y=30.0, player_id=11),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "assist_failed") == pytest.approx([1.0, 0.0])

    def test_the_assists_travel_distance_comes_from_the_predecessors_end_coordinates(self):
        frame = spadl_frame(
            [
                action(PASS, x=60.0, y=34.0, end_x=88.0, end_y=30.0, result_id=SUCCESS),
                action(SHOT, x=88.0, y=30.0),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "assist_travel_dist") == pytest.approx([np.hypot(28.0, -4.0)])

    def test_possession_length_is_capped(self):
        # A long sterile spell must not dominate the axis.
        rows = [action(PASS, x=10.0 + i, y=34.0, player_id=10 + i) for i in range(30)]
        rows.append(action(SHOT, x=95.0, y=34.0, player_id=99))

        features = build_features(spadl_frame(rows), "full")

        assert column(features, "actions_since_team_change") == pytest.approx([20.0])

    def test_possession_length_restarts_when_the_other_side_wins_the_ball(self):
        frame = spadl_frame(
            [
                action(PASS, team_id=1, x=10.0, y=34.0),
                action(PASS, team_id=1, x=20.0, y=34.0, player_id=11),
                action(PASS, team_id=2, x=5.0, y=10.0, player_id=12),
                action(SHOT, team_id=2, x=95.0, y=34.0, player_id=13),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "actions_since_team_change") == pytest.approx([1.0])

    def test_nearby_opponents_and_teammates_are_counted_separately(self):
        # Every action here ends within a few metres of the shot except the last opponent, who is on
        # the halfway line -- pressure must count only the ones actually in range.
        frame = spadl_frame(
            [
                action(PASS, team_id=2, x=90.0, y=20.0, end_x=100.0, end_y=34.0),
                action(PASS, team_id=2, x=92.0, y=25.0, end_x=101.0, end_y=35.0, player_id=11),
                action(PASS, team_id=1, x=88.0, y=28.0, end_x=99.0, end_y=33.0, player_id=12),
                action(PASS, team_id=1, x=95.0, y=40.0, end_x=100.0, end_y=36.0, player_id=13),
                action(PASS, team_id=2, x=20.0, y=20.0, end_x=30.0, end_y=30.0, player_id=14),
                action(SHOT, team_id=1, x=100.0, y=34.0, player_id=15),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "defenders_within_radius") == pytest.approx([2.0])
        assert column(features, "teammates_within_radius") == pytest.approx([2.0])

    def test_actions_beyond_the_lookback_window_do_not_count(self):
        rows = [
            action(PASS, team_id=2, x=10.0 + i, y=34.0, end_x=100.0, end_y=34.0, player_id=20 + i) for i in range(25)
        ]
        rows.append(action(SHOT, team_id=1, x=100.0, y=34.0, player_id=1))

        features = build_features(spadl_frame(rows), "full")

        assert column(features, "defenders_within_radius") == pytest.approx([20.0])

    def test_a_player_seen_only_late_in_the_match_is_flagged_as_a_substitute(self):
        # Minutes are measured from the player's own first recorded touch in that game, which is all
        # the signal there is: a substitute is simply someone whose first touch arrives late.
        frame = spadl_frame(
            [
                action(PASS, player_id=10, x=10.0, y=34.0, time_seconds=120.0),
                action(PASS, player_id=20, x=12.0, y=34.0, time_seconds=126.0),
                action(SHOT, player_id=20, x=88.0, y=34.0, time_seconds=2400.0),
                action(SHOT, player_id=30, x=70.0, y=34.0, time_seconds=2460.0),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "minutes_on_pitch") == pytest.approx([37.9, 0.0])
        assert column(features, "is_substitute") == pytest.approx([0.0, 1.0])

    def test_first_touch_is_tracked_per_game_not_across_the_season(self):
        # Same player, same minute of the match, two different games: the second appearance must not
        # look like it carries forty minutes of prior workload.
        frame = spadl_frame(
            [
                action(PASS, game_id="a", player_id=10, x=10.0, y=34.0, time_seconds=2400.0),
                action(SHOT, game_id="b", player_id=10, x=88.0, y=34.0, time_seconds=2400.0),
            ]
        )

        features = build_features(frame, "full")

        assert column(features, "minutes_on_pitch") == pytest.approx([0.0])


class TestSmoothedRate:
    def test_an_empty_sample_falls_back_to_the_league_mean(self):
        assert smoothed_rate(0, 0) == pytest.approx(0.11)

    def test_a_large_sample_moves_the_rate_only_slightly(self):
        # 70 from 84 is 83.3% raw; the smoothed estimate must land just inside it, never outside.
        assert smoothed_rate(70, 84, strength=1.0) == pytest.approx(70.11 / 85)
        assert smoothed_rate(70, 84, strength=1.0) < 70 / 84

    def test_a_stronger_prior_pulls_further_towards_the_mean(self):
        assert smoothed_rate(70, 84, strength=50.0) < smoothed_rate(70, 84, strength=1.0)


def training_frame(n=80, game_id="train"):
    """``n`` completed passes each finished by a shot, a quarter of which are goals."""
    rows = []
    for i in range(n):
        x = 40.0 + (i % 20) * 2.0
        y = 34.0 + ((i * 7) % 30) - 15.0
        rows.append(action(PASS, game_id=game_id, x=5.0, y=34.0, end_x=x, end_y=y, result_id=SUCCESS, player_id=1 + i))
        rows.append(
            action(
                SHOT,
                game_id=game_id,
                x=x,
                y=y,
                result_id=SUCCESS if i % 4 == 0 else FAIL,
                player_id=100 + i,
            )
        )
    return spadl_frame(rows)


def write_artifact(path, *, feature_set="full", penalty_p_goal=0.79, feature_names=None):
    """Write an ``xg_*.pkl`` in exactly the shape ``models/train/train_xg.py`` produces."""
    frame = training_frame()
    features = build_features(frame, feature_set)
    goals = non_penalty_shot_mask(frame) & (frame["result_id"] == SUCCESS).to_numpy()
    model = XGBClassifier(n_estimators=5, max_depth=2, random_state=0)
    model.fit(features, goals.astype(int))
    path.write_bytes(
        pickle.dumps(
            {
                "model": model,
                "feature_set": feature_set,
                "feature_names": list(FEATURE_SETS[feature_set]) if feature_names is None else feature_names,
                "penalty_p_goal": penalty_p_goal,
                "n_train": int(goals.sum()),
            }
        )
    )
    return path


@pytest.fixture
def artifact(tmp_path):
    """A fully trained, if tiny, xG model over the full feature set."""
    return write_artifact(tmp_path / "xg_20260101_000000.pkl")


@pytest.fixture
def build_artifact(tmp_path):
    """Write a deliberately misshapen artifact, for the cases the happy path cannot reach."""
    names = itertools.count()

    def _build(**kwargs):
        return write_artifact(tmp_path / f"xg_{next(names):06d}.pkl", **kwargs)

    return _build


class TestXgRegressor:
    def test_predict_returns_one_probability_per_shot_including_penalties(self, artifact):
        frame = spadl_frame(
            [
                action(PASS, x=20.0, y=20.0, end_x=90.0, end_y=34.0, result_id=SUCCESS),
                action(SHOT, x=90.0, y=34.0, player_id=20),
                action(PENALTY, x=101.0, y=34.0, player_id=21),
                action(FREEKICK, x=85.0, y=40.0, player_id=22),
                action(SHOT, x=60.0, y=34.0, player_id=23),
            ]
        )

        assert XgRegressor(artifact).predict(frame).shape == (4,)

    def test_penalties_use_the_stored_smoothed_rate_and_never_reach_the_tree(self, artifact):
        frame = spadl_frame(
            [
                action(PENALTY, x=101.0, y=34.0),
                action(PENALTY, x=101.0, y=34.0, player_id=11),
                action(SHOT, x=60.0, y=34.0, player_id=12),
            ]
        )

        probabilities = XgRegressor(artifact).predict(frame)

        assert probabilities[:2] == pytest.approx([0.79, 0.79])
        assert probabilities[2] != pytest.approx(0.79)

    def test_a_frame_without_shots_predicts_an_empty_array(self, artifact):
        frame = spadl_frame([action(PASS), action(PASS, player_id=11)])

        assert XgRegressor(artifact).predict(frame).shape == (0,)

    def test_probabilities_stay_strictly_inside_the_open_unit_interval(self, artifact):
        # xT subtracts the cell value from this number and telescopes a possession against the goals
        # actually scored, so anything outside (0, 1) breaks that identity outright.
        probabilities = XgRegressor(artifact).predict(training_frame())

        assert probabilities.size == 80
        assert np.all(probabilities > 0.0) and np.all(probabilities < 1.0)

    def test_the_feature_names_are_reported_for_inspection(self, build_artifact):
        path = build_artifact(feature_set="base")

        assert XgRegressor(path).feature_names == list(FEATURE_SETS["base"])

    def test_a_base_only_artifact_ignores_the_lookback_block(self, build_artifact):
        path = build_artifact(feature_set="base")
        frame = spadl_frame([action(PASS, x=20.0, y=20.0, end_x=90.0, end_y=34.0), action(SHOT, x=90.0, y=34.0)])

        assert XgRegressor(path).predict(frame).shape == (1,)

    def test_an_artifact_whose_feature_layout_has_drifted_is_rejected(self, build_artifact):
        path = build_artifact(feature_names=["start_x", "something_else"])

        with pytest.raises(ValueError, match="Retrain it with models/train/train_xg.py"):
            XgRegressor(path)


class FakeXt:
    """The little of the xT surface :func:`rate_shots` touches, with recognisable cell values."""

    def __init__(self, n_cols=8, n_rows=12):
        self.l = n_rows
        self.w = n_cols
        self.xT = np.arange(n_cols * n_rows, dtype=float).reshape(n_cols, n_rows) / 100.0
        self.scoring_prob_matrix = np.linspace(0.01, 0.4, n_cols * n_rows).reshape(n_cols, n_rows)


def cell_of(model, x, y):
    column_index = min(int(x / spadl_config.field_length * model.l), model.l - 1)
    row = min(max(int(y / spadl_config.field_width * model.w), 0), model.w - 1)
    return model.w - 1 - row, column_index


class TestRateShotsIntegration:
    def test_the_learned_probability_replaces_the_placeholder_and_is_still_net_of_the_cell(self, artifact):
        model = FakeXt()
        frame = spadl_frame(
            [
                action(PASS, x=20.0, y=20.0, end_x=90.0, end_y=34.0, result_id=SUCCESS),
                action(SHOT, x=90.0, y=34.0, player_id=20),
                action(SHOT, x=60.0, y=34.0, player_id=21),
            ]
        )

        xg = XgRegressor(artifact)
        probabilities = xg.predict(frame)
        ratings = rate_shots(frame, model, xg)

        assert np.isnan(ratings[0])
        for row, p_goal in ((1, probabilities[0]), (2, probabilities[1])):
            cell_y, cell_x = cell_of(model, frame["start_x"][row], frame["start_y"][row])
            assert ratings[row] == pytest.approx(p_goal - model.xT[cell_y, cell_x])

    def test_the_predictions_differ_from_the_placeholder_they_replace(self, artifact):
        # Otherwise there is no reason to prefer the learned model over the surface.
        frame = training_frame()
        model = FakeXt()

        learned = rate_shots(frame, model, XgRegressor(artifact))
        placeholder = rate_shots(frame, model, None)

        rated = ~np.isnan(learned)
        assert rated.sum() == 80
        assert not np.allclose(learned[rated], placeholder[rated], atol=1e-3)
