import pandas as pd
import pytest
from metrics.high_level.xtpm import FeatureSpec, XtPlusMinus

import pipeline.update_metrics as um

HOME = [1, 2, 3]
AWAY = [11, 12, 13]


def segment_rows(game_id, index=0, start=0.0, end=90.0, net_xt=0.3, goals=(1, 0)):
    duration = end - start
    return {
        "game_id": game_id,
        "segment_index": index,
        "start_minute": start,
        "end_minute": end,
        "duration_minutes": duration,
        "n_players_home": len(HOME),
        "n_players_away": len(AWAY),
        "xt_home": net_xt / 2,
        "xt_away": -net_xt / 2,
        "net_xt": net_xt * duration / 90.0,
        "net_xt_per90": net_xt,
        "goals_home": goals[0],
        "goals_away": goals[1],
        "gd90": (goals[0] - goals[1]) * 90.0 / duration,
    }


def player_rows(game_id, home=HOME, away=AWAY, on=0.0, off=90.0):
    return [
        {"player_id": player, "game_id": game_id, "on_minute": on, "off_minute": off, "is_home": True}
        for player in home
    ] + [
        {"player_id": player, "game_id": game_id, "on_minute": on, "off_minute": off, "is_home": False}
        for player in away
    ]


class FakeSegmentRepo:
    def __init__(self, rows):
        self.rows = rows
        self.requested = None

    def get_segments(self, session, game_ids=None):
        self.requested = list(game_ids)
        return pd.DataFrame(self.rows) if self.rows else pd.DataFrame(columns=["game_id"])


class FakePlayerGameRepo:
    def __init__(self, rows):
        self.rows = rows

    def get_player_games(self, session, game_ids=None):
        return pd.DataFrame(self.rows) if self.rows else pd.DataFrame(columns=["game_id"])


class FakeMetricRepo:
    def __init__(self):
        self.deleted = []
        self.inserted = []
        self.calls = []

    def delete_metrics(self, session, game_ids, metric_names):
        self.calls.append(("delete", list(game_ids), tuple(metric_names)))
        self.deleted.append((tuple(game_ids), tuple(metric_names)))

    def insert_batch_metric(self, session, batch):
        self.calls.append(("insert", len(batch)))
        self.inserted.extend([tuple(row) for row in batch])


class Harness:
    def __init__(self):
        self.metrics = None


@pytest.fixture
def wired(monkeypatch):
    """Install the three repository fakes; call it with the rows and read ``.metrics``."""
    harness = Harness()

    def build(segments, players):
        harness.metrics = FakeMetricRepo()
        monkeypatch.setattr(um, "DB_segment", lambda: FakeSegmentRepo(segments))
        monkeypatch.setattr(um, "DB_player_game", lambda: FakePlayerGameRepo(players))
        monkeypatch.setattr(um, "DB_metric", lambda: harness.metrics)
        return harness.metrics

    return build


def new_state():
    return XtPlusMinus(spec=FeatureSpec(home_advantage_dummy=True))


class TestScoreGames:
    def test_a_fresh_game_writes_a_rating_and_a_credit_row_per_player(self, wired):
        wired([segment_rows(1)], player_rows(1))

        stats = um.score_games(None, new_state(), [1], weight_mode="duration")

        assert stats == {"games": 1, "segments": 1, "rows": 18, "skipped": 0}

    def test_the_three_plus_minus_metrics_are_written(self, wired):
        metric_repo = wired([segment_rows(1)], player_rows(1))

        um.score_games(None, new_state(), [1], weight_mode="duration")

        assert {row[3] for row in metric_repo.inserted} == {"xtpm_rating", "gdpm_rating", "xtpm_credit"}

    def test_every_player_appearing_in_the_game_gets_a_row(self, wired):
        metric_repo = wired([segment_rows(1)], player_rows(1))

        um.score_games(None, new_state(), [1], weight_mode="duration")

        for _player_id, game_id, _value, name in metric_repo.inserted:
            assert game_id == 1
            assert name.startswith(("xtpm", "gdpm"))
        assert {row[0] for row in metric_repo.inserted} == set(HOME + AWAY)

    def test_existing_rows_are_deleted_before_the_new_ones_are_inserted(self, wired):
        metric_repo = wired([segment_rows(1)], player_rows(1))

        um.score_games(None, new_state(), [1], weight_mode="duration")

        assert [call[0] for call in metric_repo.calls] == ["delete", "insert"]
        assert metric_repo.deleted[0][0] == (1,)
        assert set(metric_repo.deleted[0][1]) == {"xtpm_rating", "gdpm_rating", "xtpm_credit"}

    def test_a_game_with_no_segments_is_skipped(self, wired):
        metric_repo = wired([], [])

        stats = um.score_games(None, new_state(), [1], weight_mode="duration")

        assert stats == {"games": 0, "segments": 0, "rows": 0, "skipped": 0}
        assert metric_repo.calls == []

    def test_a_game_absent_from_the_segment_frame_is_skipped(self, wired):
        metric_repo = wired([segment_rows(1)], player_rows(1))

        stats = um.score_games(None, new_state(), [1, 2], weight_mode="duration")

        assert stats["skipped"] == 1
        assert stats["games"] == 1
        assert metric_repo.deleted[0][0] == (1,)


class TestReplayingIsIdempotent:
    def test_an_already_absorbed_game_is_skipped_without_rewriting_its_rows(self, wired):
        metric_repo = wired([segment_rows(1)], player_rows(1))
        state = new_state()

        first = um.score_games(None, state, [1], weight_mode="duration")
        assert first["games"] == 1
        baseline = list(metric_repo.inserted)
        metric_repo.calls.clear()
        metric_repo.inserted.clear()

        second = um.score_games(None, state, [1], weight_mode="duration")

        assert second == {"games": 0, "segments": 0, "rows": 0, "skipped": 1}
        assert metric_repo.calls == []
        assert metric_repo.inserted == []
        assert baseline, "the first run should have written rows"

    def test_skipped_games_do_not_advance_later_ratings(self, wired):
        segments = [segment_rows(1, index=0, end=45.0, net_xt=0.5, goals=(2, 0))]
        segments += [segment_rows(2, index=0, net_xt=0.1, goals=(0, 0))]
        wired(segments, player_rows(1, on=0.0, off=45.0) + player_rows(2))

        replayed = new_state()
        um.score_games(None, replayed, [1, 1, 2], weight_mode="duration")

        fresh = new_state()
        um.score_games(None, fresh, [1, 2], weight_mode="duration")

        for dv in ("xt", "gd"):
            assert replayed.ratings(dv) == pytest.approx(fresh.ratings(dv))


class TestMultipleSegments:
    def test_every_segment_of_a_game_is_absorbed_in_one_step(self, wired):
        segments = [
            segment_rows(1, index=0, start=0.0, end=60.0, net_xt=0.4, goals=(1, 0)),
            segment_rows(1, index=1, start=60.0, end=90.0, net_xt=-0.2, goals=(0, 1)),
        ]
        wired(segments, player_rows(1))

        stats = um.score_games(None, new_state(), [1], weight_mode="duration")

        assert stats["games"] == 1
        assert stats["segments"] == 2

    def test_a_substituted_segment_sees_only_its_own_line_up(self, wired):
        segments = [
            segment_rows(1, index=0, start=0.0, end=60.0, net_xt=0.4, goals=(1, 0)),
            segment_rows(1, index=1, start=60.0, end=90.0, net_xt=-0.2, goals=(0, 1)),
        ]
        later_home = [1, 2, 4]
        players = player_rows(1, on=0.0, off=60.0) + player_rows(1, home=later_home, on=60.0, off=90.0)
        metric_repo = wired(segments, players)

        um.score_games(None, new_state(), [1], weight_mode="duration")

        # Everyone present in either segment is rated, including the substitute.
        rated = {row[0] for row in metric_repo.inserted}
        assert rated == set(HOME + later_home + AWAY)
        # But exactly one row per metric per player, i.e. the game is not rated twice.
        assert len(metric_repo.inserted) == len(rated) * 3


class TestLimit:
    def test_limit_stops_after_that_many_absorbed_games(self, wired):
        segments = [segment_rows(game_id) for game_id in (1, 2, 3, 4)]
        players = [row for game_id in (1, 2, 3, 4) for row in player_rows(game_id)]
        wired(segments, players)

        metric_repo = wired(segments, players)
        stats = um.score_games(None, new_state(), [1, 2, 3, 4], weight_mode="duration", limit=2)

        assert stats["games"] == 2
        assert {row[1] for row in metric_repo.inserted} == {1, 2}


class TestSegmentRebuild:
    def test_line_ups_are_rebuilt_from_the_stored_presence_intervals(self, wired):
        # Only players 1, 2 and 4 are on the pitch for the whole game; 3 never appears.
        wired([segment_rows(1)], player_rows(1, home=[1, 2, 4]))

        state = new_state()
        um.score_games(None, state, [1], weight_mode="duration")

        assert set(state.ratings("xt")) == {1, 2, 4, 11, 12, 13}
