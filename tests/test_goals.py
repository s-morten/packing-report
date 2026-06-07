from unittest.mock import MagicMock

import pandas as pd
import pytest
from metrics.low_level.goals import Goals


class FakeGameFacts:
    def __init__(self, players_dict, events=None, df_teams=None):
        self.players_dict = players_dict
        self.events = events if events is not None else pd.DataFrame()
        self.df_teams = df_teams if df_teams is not None else pd.DataFrame()


def make_goal_df(minutes, team_ids):
    return pd.DataFrame({"expanded_minute": minutes, "goal_team_id": team_ids})


class TestCalculate:
    def test_both_teams_score_while_all_players_on_pitch(self, monkeypatch):
        team_a_id = 10
        team_b_id = 20
        players_dict = {
            1: {"team_id": team_a_id, "on": 0, "off": 90},
            2: {"team_id": team_b_id, "on": 0, "off": 90},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([30, 50], [team_a_id, team_b_id]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 1
        assert goals.player_goal_minute_mapping[1]["goals_against"] == 1
        assert goals.player_goal_minute_mapping[2]["goals_for"] == 1
        assert goals.player_goal_minute_mapping[2]["goals_against"] == 1

    def test_multiple_goals_same_team(self, monkeypatch):
        team_a = 10
        players_dict = {
            1: {"team_id": team_a, "on": 0, "off": 90},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([10, 20, 30], [team_a, team_a, team_a]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 3
        assert goals.player_goal_minute_mapping[1]["goals_against"] == 0

    def test_goals_conceded(self, monkeypatch):
        team_a = 10
        team_b = 20
        players_dict = {
            1: {"team_id": team_a, "on": 0, "off": 90},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([15, 75], [team_b, team_b]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 0
        assert goals.player_goal_minute_mapping[1]["goals_against"] == 2

    def test_substitute_only_counts_while_on_pitch(self, monkeypatch):
        team_a = 10
        players_dict = {
            1: {"team_id": team_a, "on": 0, "off": 90},
            2: {"team_id": team_a, "on": 60, "off": 90},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([45, 70, 85], [team_a, team_a, team_a]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 3
        assert goals.player_goal_minute_mapping[2]["goals_for"] == 2

    def test_goal_at_on_boundary_not_counted(self, monkeypatch):
        team_a = 10
        players_dict = {
            1: {"team_id": team_a, "on": 30, "off": 90},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([30, 31], [team_a, team_a]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 1

    def test_goal_at_off_boundary_not_counted(self, monkeypatch):
        team_a = 10
        players_dict = {
            1: {"team_id": team_a, "on": 0, "off": 80},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([79, 80, 81], [team_a, team_a, team_a]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 1

    def test_no_goals(self, monkeypatch):
        players_dict = {
            1: {"team_id": 10, "on": 0, "off": 90},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([], []),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 0
        assert goals.player_goal_minute_mapping[1]["goals_against"] == 0

    def test_multiple_players_different_teams(self, monkeypatch):
        team_a = 10
        team_b = 20
        players_dict = {
            1: {"team_id": team_a, "on": 0, "off": 90},
            2: {"team_id": team_a, "on": 0, "off": 90},
            3: {"team_id": team_b, "on": 0, "off": 90},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([25], [team_a]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 1
        assert goals.player_goal_minute_mapping[2]["goals_for"] == 1
        assert goals.player_goal_minute_mapping[3]["goals_for"] == 0
        assert goals.player_goal_minute_mapping[3]["goals_against"] == 1

    def test_player_not_on_pitch_excluded(self, monkeypatch):
        team_a = 10
        players_dict = {
            1: {"team_id": team_a, "on": 0, "off": 90},
            2: {"team_id": team_a, "on": 0, "off": 0},
        }
        timeline = FakeGameFacts(players_dict)
        monkeypatch.setattr(
            "metrics.low_level.goals.get_score",
            lambda events, teams: make_goal_df([25], [team_a]),
        )

        goals = Goals()
        goals.calculate(timeline)

        assert goals.player_goal_minute_mapping[1]["goals_for"] == 1
        assert goals.player_goal_minute_mapping[2]["goals_for"] == 0
        assert goals.player_goal_minute_mapping[2]["minutes"] == 0


class TestWrite:
    def test_writes_goal_difference_to_db(self):
        session = MagicMock()
        repo = MagicMock()
        goals = Goals(metric_repo=repo)
        goals.player_goal_minute_mapping = {
            1: {"team_id": 10, "goals_for": 2, "goals_against": 1, "minutes": 90, "on": 0, "off": 90},
            2: {"team_id": 10, "goals_for": 0, "goals_against": 3, "minutes": 90, "on": 0, "off": 90},
        }

        goals.write(session, game_id=42)

        assert repo.insert_batch_metric.call_count == 1
        batch = repo.insert_batch_metric.call_args[0][1]
        assert [1, 42, 1, "goals"] in batch
        assert [2, 42, -3, "goals"] in batch

    def test_writes_correct_columns(self):
        session = MagicMock()
        repo = MagicMock()
        goals = Goals(metric_repo=repo)
        goals.player_goal_minute_mapping = {
            5: {"team_id": 10, "goals_for": 3, "goals_against": 0, "minutes": 90, "on": 0, "off": 90},
        }

        goals.write(session, game_id=99)

        batch = repo.insert_batch_metric.call_args[0][1]
        assert batch[0] == [5, 99, 3, "goals"]

    def test_empty_mapping_writes_empty_batch(self):
        session = MagicMock()
        repo = MagicMock()
        goals = Goals(metric_repo=repo)
        goals.player_goal_minute_mapping = {}

        goals.write(session, game_id=1)

        assert len(repo.insert_batch_metric.call_args[0][1]) == 0

    def test_negative_goal_difference(self):
        session = MagicMock()
        repo = MagicMock()
        goals = Goals(metric_repo=repo)
        goals.player_goal_minute_mapping = {
            7: {"team_id": 10, "goals_for": 0, "goals_against": 4, "minutes": 90, "on": 0, "off": 90},
        }

        goals.write(session, game_id=5)

        batch = repo.insert_batch_metric.call_args[0][1]
        assert batch[0] == [7, 5, -4, "goals"]

    def test_write_without_calculate_raises(self):
        session = MagicMock()
        goals = Goals(metric_repo=MagicMock())
        with pytest.raises(AttributeError):
            goals.write(session, game_id=1)
