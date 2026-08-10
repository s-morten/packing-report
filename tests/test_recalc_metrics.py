import pandas as pd

import database_io.connection as connection
from database_io.models.metric import PlayerGameMetric
from pipeline.recalc_metrics import delete_game_metrics, season_game_ids


class FakeWhoScored:
    def __init__(self, schedule):
        self._schedule = schedule

    def read_schedule(self):
        return self._schedule


def test_season_game_ids_filters_by_season():
    schedule = pd.DataFrame(
        [
            {"league": "GER-Bundesliga", "season": "1819", "game": "a", "game_id": 11},
            {"league": "GER-Bundesliga", "season": "1819", "game": "b", "game_id": 12},
            {"league": "GER-Bundesliga", "season": "1920", "game": "c", "game_id": 21},
            {"league": "GER-Bundesliga2", "season": "1819", "game": "d", "game_id": 13},
        ]
    ).set_index(["league", "season", "game"])

    ws = FakeWhoScored(schedule)

    assert season_game_ids(ws, "1819") == [11, 12, 13]


def test_season_game_ids_empty_schedule_returns_empty_list():
    schedule = pd.DataFrame(columns=["league", "season", "game", "game_id"]).set_index(["league", "season", "game"])

    ws = FakeWhoScored(schedule)

    assert season_game_ids(ws, "1819") == []


def test_delete_game_metrics_deletes_only_matching_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    connection._engine = None
    connection._SessionLocal = None
    connection.init_db()

    with connection.get_session() as session:
        session.add(PlayerGameMetric(player_id=1, game_id=100, metric="minutes", value=90))
        session.add(PlayerGameMetric(player_id=1, game_id=200, metric="minutes", value=60))
        session.add(PlayerGameMetric(player_id=2, game_id=100, metric="goals", value=1))

    with connection.get_session() as session:
        deleted = delete_game_metrics(session, [100])
        assert deleted == 2

    with connection.get_session() as session:
        remaining = session.query(PlayerGameMetric).all()
        assert [row.game_id for row in remaining] == [200]


def test_delete_game_metrics_unknown_game_ids_deletes_nothing(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    connection._engine = None
    connection._SessionLocal = None
    connection.init_db()

    with connection.get_session() as session:
        session.add(PlayerGameMetric(player_id=1, game_id=100, metric="minutes", value=90))

    with connection.get_session() as session:
        deleted = delete_game_metrics(session, [999])
        assert deleted == 0
