import numpy as np
import pandas as pd
import pytest

from utils.football_data_utils import (
    get_opposition_team,
    get_score,
    is_own_goal,
)


def own_goal() -> list[dict]:
    return [{"type": {"displayName": "OwnGoal"}}]


def other_qualifier() -> list[dict]:
    return [{"type": {"displayName": "SomeOther"}}]


class TestIsOwnGoal:
    def test_own_goal_qualifier_returns_true(self):
        assert is_own_goal([own_goal()]) == [True]

    def test_other_qualifier_returns_false(self):
        assert is_own_goal([other_qualifier()]) == [False]

    def test_empty_qualifiers_returns_false(self):
        assert is_own_goal([[]]) == [False]

    def test_mixed_events_aligns_with_input(self):
        result = is_own_goal([own_goal(), other_qualifier(), own_goal()])

        assert result == [True, False, True]

    def test_multiple_qualifiers_with_own_goal_returns_true(self):
        qualifiers = [other_qualifier() + own_goal()]

        assert is_own_goal(qualifiers) == [True]

    def test_none_cell_returns_false(self):
        assert is_own_goal([None]) == [False]

    def test_nan_cell_returns_false(self):
        assert is_own_goal([np.nan]) == [False]


def make_teams_df(team_ids):
    return pd.DataFrame({"team_id": team_ids, "team_name": ["A", "B"]})


class TestGetOppositionTeam:
    def test_swaps_the_two_team_ids(self):
        series = pd.Series([10, 20, 10])
        df_teams = make_teams_df([10, 20])

        result = get_opposition_team(series, df_teams)

        assert result.tolist() == [20, 10, 20]

    def test_returns_series_aligned_with_input(self):
        series = pd.Series([20, 10], index=["a", "b"])
        df_teams = make_teams_df([10, 20])

        result = get_opposition_team(series, df_teams)

        assert result.index.tolist() == ["a", "b"]
        assert result.tolist() == [10, 20]

    def test_single_value_input_is_swapped(self):
        series = pd.Series([10])
        df_teams = make_teams_df([10, 20])

        assert get_opposition_team(series, df_teams).tolist() == [20]

    def test_one_team_in_df_raises_value_error(self):
        series = pd.Series([10])
        df_teams = pd.DataFrame({"team_id": [10]})

        with pytest.raises(ValueError):
            get_opposition_team(series, df_teams)

    def test_empty_teams_df_raises_value_error(self):
        series = pd.Series([10])
        df_teams = pd.DataFrame()

        with pytest.raises(ValueError):
            get_opposition_team(series, df_teams)


class TestGetScore:
    def make_events_df(self, events):
        return pd.DataFrame(events)

    def test_regular_goals_count_to_own_team(self):
        events = self.make_events_df(
            [
                {"is_goal": True, "team_id": 10, "expanded_minute": 30, "qualifiers": other_qualifier()},
                {"is_goal": True, "team_id": 20, "expanded_minute": 50, "qualifiers": []},
            ]
        )
        df_teams = make_teams_df([10, 20])

        result = get_score(events, df_teams)

        assert result["goal_team_id"].tolist() == [10, 20]
        assert result["expanded_minute"].tolist() == [30, 50]

    def test_own_goal_count_to_opposition(self):
        events = self.make_events_df(
            [
                {"is_goal": True, "team_id": 10, "expanded_minute": 30, "qualifiers": own_goal()},
            ]
        )
        df_teams = make_teams_df([10, 20])

        result = get_score(events, df_teams)

        assert result["goal_team_id"].tolist() == [20]

    def test_mixed_own_and_regular_goals(self):
        events = self.make_events_df(
            [
                {"is_goal": True, "team_id": 10, "expanded_minute": 10, "qualifiers": other_qualifier()},
                {"is_goal": True, "team_id": 20, "expanded_minute": 40, "qualifiers": own_goal()},
                {"is_goal": True, "team_id": 10, "expanded_minute": 70, "qualifiers": own_goal()},
            ]
        )
        df_teams = make_teams_df([10, 20])

        result = get_score(events, df_teams)

        assert result["goal_team_id"].tolist() == [10, 10, 20]

    def test_non_goal_events_excluded(self):
        events = self.make_events_df(
            [
                {"is_goal": False, "team_id": 10, "expanded_minute": 5, "qualifiers": []},
                {"is_goal": True, "team_id": 10, "expanded_minute": 30, "qualifiers": []},
                {"is_goal": False, "team_id": 20, "expanded_minute": 60, "qualifiers": []},
            ]
        )
        df_teams = make_teams_df([10, 20])

        result = get_score(events, df_teams)

        assert result["expanded_minute"].tolist() == [30]

    def test_no_goals_returns_empty_df_with_columns(self):
        events = self.make_events_df(
            [
                {"is_goal": False, "team_id": 10, "expanded_minute": 5, "qualifiers": []},
            ]
        )
        df_teams = make_teams_df([10, 20])

        result = get_score(events, df_teams)

        assert result.empty
        assert result.columns.tolist() == ["expanded_minute", "goal_team_id"]

    def test_returns_only_minute_and_team_columns(self):
        events = self.make_events_df(
            [
                {"is_goal": True, "team_id": 10, "expanded_minute": 30, "qualifiers": []},
            ]
        )
        df_teams = make_teams_df([10, 20])

        result = get_score(events, df_teams)

        assert result.columns.tolist() == ["expanded_minute", "goal_team_id"]

    def test_missing_is_goal_column_raises_key_error(self):
        events = pd.DataFrame({"team_id": [10], "expanded_minute": [30]})
        df_teams = make_teams_df([10, 20])

        with pytest.raises(KeyError):
            get_score(events, df_teams)

    def test_invalid_teams_df_with_own_goal_raises_value_error(self):
        events = self.make_events_df(
            [
                {"is_goal": True, "team_id": 10, "expanded_minute": 30, "qualifiers": own_goal()},
            ]
        )
        df_teams = pd.DataFrame({"team_id": [10]})

        with pytest.raises(ValueError):
            get_score(events, df_teams)
