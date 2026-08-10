from unittest.mock import MagicMock

import pandas as pd
import pytest
from metrics.low_level.time_to_recovery import TimeToRecovery


def make_events_df(events):
    return pd.DataFrame(events)


def touch(team_id, minute, second):
    return {"type": "Pass", "team_id": team_id, "expanded_minute": minute, "second": second}


def recovery(team_id, minute, second):
    return {"type": "BallRecovery", "team_id": team_id, "expanded_minute": minute, "second": second}


class FakeGameFacts:
    def __init__(self, events_df, players_dict):
        self.events = events_df
        self.players_dict = players_dict


class TestCalculate:
    def test_average_time_to_recovery_user_example(self):
        events = [
            touch(20, 10, 0),
            recovery(10, 10, 10),
            touch(20, 20, 0),
            recovery(10, 20, 12),
            touch(20, 30, 0),
            recovery(10, 30, 5),
        ]
        game_facts = FakeGameFacts(make_events_df(events), {1: {"team_id": 10, "on": 0, "off": 70}})

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert time_to_recovery.player_recovery_mapping == {1: 9.0}

    def test_two_players_same_team_same_average(self):
        events = [
            touch(20, 10, 0),
            recovery(10, 10, 10),
            touch(20, 20, 0),
            recovery(10, 20, 12),
            touch(20, 30, 0),
            recovery(10, 30, 5),
        ]
        players = {1: {"team_id": 10, "on": 0, "off": 90}, 2: {"team_id": 10, "on": 0, "off": 90}}
        game_facts = FakeGameFacts(make_events_df(events), players)

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert time_to_recovery.player_recovery_mapping == {1: 9.0, 2: 9.0}

    def test_recovery_after_substitution_excluded(self):
        events = [
            touch(20, 10, 0),
            recovery(10, 10, 5),
            touch(20, 50, 0),
            recovery(10, 50, 8),
        ]
        game_facts = FakeGameFacts(make_events_df(events), {1: {"team_id": 10, "on": 0, "off": 45}})

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert time_to_recovery.player_recovery_mapping == {1: 5.0}

    def test_recovery_before_player_on_excluded(self):
        events = [
            touch(20, 10, 0),
            recovery(10, 10, 7),
            touch(20, 40, 0),
            recovery(10, 40, 3),
        ]
        game_facts = FakeGameFacts(make_events_df(events), {1: {"team_id": 10, "on": 30, "off": 90}})

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert time_to_recovery.player_recovery_mapping == {1: 3.0}

    def test_opponent_team_recoveries_excluded(self):
        events = [
            touch(20, 10, 0),
            recovery(10, 10, 10),
            touch(10, 20, 0),
            recovery(20, 20, 4),
            touch(10, 30, 0),
            recovery(20, 30, 2),
        ]
        game_facts = FakeGameFacts(make_events_df(events), {1: {"team_id": 10, "on": 0, "off": 90}})

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert time_to_recovery.player_recovery_mapping == {1: 10.0}

    def test_player_without_qualifying_recoveries_omitted(self):
        events = [
            touch(20, 10, 0),
            recovery(10, 50, 5),
            touch(10, 20, 0),
            recovery(20, 20, 4),
        ]
        players = {1: {"team_id": 10, "on": 0, "off": 45}, 2: {"team_id": 20, "on": 0, "off": 90}}
        game_facts = FakeGameFacts(make_events_df(events), players)

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert 1 not in time_to_recovery.player_recovery_mapping
        assert time_to_recovery.player_recovery_mapping[2] == 4.0

    def test_recovery_at_exact_off_minute_excluded(self):
        events = [
            touch(20, 44, 0),
            recovery(10, 44, 6),
            touch(20, 45, 0),
            recovery(10, 45, 8),
        ]
        game_facts = FakeGameFacts(make_events_df(events), {1: {"team_id": 10, "on": 0, "off": 45}})

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert time_to_recovery.player_recovery_mapping == {1: 6.0}

    def test_recovery_without_prior_opponent_touch_skipped(self):
        events = [
            recovery(10, 5, 0),
            touch(20, 10, 0),
            recovery(10, 10, 9),
        ]
        game_facts = FakeGameFacts(make_events_df(events), {1: {"team_id": 10, "on": 0, "off": 90}})

        time_to_recovery = TimeToRecovery()
        time_to_recovery.calculate(game_facts)

        assert time_to_recovery.player_recovery_mapping == {1: 9.0}

    def test_missing_required_column_raises_key_error(self):
        df = pd.DataFrame({"type": ["BallRecovery"], "expanded_minute": [10], "second": [0]})
        game_facts = FakeGameFacts(df, {1: {"team_id": 10, "on": 0, "off": 90}})

        time_to_recovery = TimeToRecovery()
        with pytest.raises(KeyError):
            time_to_recovery.calculate(game_facts)


class TestWrite:
    def test_writes_time_to_recovery_to_db(self):
        session = MagicMock()
        repo = MagicMock()
        time_to_recovery = TimeToRecovery(metric_repo=repo)
        time_to_recovery.player_recovery_mapping = {1: 9.0, 2: 3.0}

        time_to_recovery.write(session, game_id=42)

        assert repo.insert_batch_metric.call_count == 1
        batch = repo.insert_batch_metric.call_args[0][1]
        assert [1, 42, 9.0, "time_to_recovery"] in batch
        assert [2, 42, 3.0, "time_to_recovery"] in batch

    def test_empty_mapping_writes_empty_batch(self):
        session = MagicMock()
        repo = MagicMock()
        time_to_recovery = TimeToRecovery(metric_repo=repo)
        time_to_recovery.player_recovery_mapping = {}

        time_to_recovery.write(session, game_id=1)

        assert repo.insert_batch_metric.call_args[0][1] == []

    def test_write_without_calculate_raises(self):
        session = MagicMock()
        time_to_recovery = TimeToRecovery(metric_repo=MagicMock())
        with pytest.raises(AttributeError):
            time_to_recovery.write(session, game_id=1)
