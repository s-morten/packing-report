import numpy as np
import pandas as pd
import pytest

from eval.eval_low_level import LOW_LEVEL_METRICS, pivot_wide, player_summary


def make_wide():
    return pd.DataFrame(
        [
            {
                "player_id": 1,
                "game_id": 100,
                "name": "Player A",
                "date": pd.Timestamp("2018-08-25"),
                "league": "GER-Bundesliga",
                "season": "1819",
                "minutes": 90,
                "goals": 1,
                "vaep": 0.5,
                "xt": 1.0,
                "time_to_recovery": np.nan,
            },
            {
                "player_id": 1,
                "game_id": 101,
                "name": "Player A",
                "date": pd.Timestamp("2018-09-01"),
                "league": "GER-Bundesliga",
                "season": "1819",
                "minutes": 45,
                "goals": 0,
                "vaep": -0.2,
                "xt": 0.5,
                "time_to_recovery": 9.0,
            },
            {
                "player_id": 2,
                "game_id": 100,
                "name": "Player B",
                "date": pd.Timestamp("2018-08-25"),
                "league": "GER-Bundesliga2",
                "season": "1819",
                "minutes": 90,
                "goals": 0,
                "vaep": 0.1,
                "xt": 0.2,
                "time_to_recovery": 6.0,
            },
        ]
    )


class TestPivotWide:
    def test_pivot_creates_one_column_per_metric(self):
        long = pd.melt(
            make_wide(),
            id_vars=["player_id", "game_id", "name", "date", "league", "season"],
            value_vars=LOW_LEVEL_METRICS,
            var_name="metric",
            value_name="value",
        )

        wide = pivot_wide(long)

        assert set(LOW_LEVEL_METRICS) <= set(wide.columns)
        assert len(wide) == 3
        assert wide.loc[0, "player_id"] == 1

    def test_pivot_keeps_sparse_metrics_as_nan(self):
        long = pd.melt(
            make_wide(),
            id_vars=["player_id", "game_id", "name", "date", "league", "season"],
            value_vars=LOW_LEVEL_METRICS,
            var_name="metric",
            value_name="value",
        )

        wide = pivot_wide(long)

        assert wide.loc[(wide["game_id"] == 100) & (wide["player_id"] == 1), "time_to_recovery"].isna().all()


class TestPlayerSummary:
    def test_aggregates_per_player(self):
        wide = make_wide()

        summary = player_summary(wide, min_games=1)

        player_a = summary[summary["player_id"] == 1].iloc[0]
        assert player_a["games"] == 2
        assert player_a["minutes_played"] == 135
        assert player_a["minutes"] == 67.5
        assert player_a["goals"] == 0.5
        assert player_a["time_to_recovery"] == 9.0
        assert player_a["goals_per90"] == pytest.approx(1 / 135 * 90)

    def test_filters_by_min_games(self):
        wide = make_wide()

        summary = player_summary(wide, min_games=2)

        assert summary["player_id"].tolist() == [1]
