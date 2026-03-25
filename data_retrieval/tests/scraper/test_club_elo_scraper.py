# ruff: noqa: I001

import pandas as pd
import pytest

from data_retrieval.scraper import club_elo_scraper as module


class FakeClubElo:
    def read_by_date(self, date):
        return pd.DataFrame(
            {
                "team": ["Arsenal", "Chelsea", "Dortmund"],
                "league": ["ENG-Premier League", "ENG-Premier League", "GER-Bundesliga"],
                "elo": [1800.0, 1750.0, 1700.0],
            }
        ).set_index("team")


def test_get_team_elo_by_date_returns_float(monkeypatch):
    monkeypatch.setattr(module.sd, "ClubElo", lambda: FakeClubElo())
    scraper = module.ClubEloScraper()

    elo = scraper.get_team_elo_by_date("2024-08-31", "Arsenal")

    assert isinstance(elo, float)
    assert elo == 1800.0


def test_get_team_elo_by_date_missing_team_raises_index_error(monkeypatch):
    monkeypatch.setattr(module.sd, "ClubElo", lambda: FakeClubElo())
    scraper = module.ClubEloScraper()

    with pytest.raises(IndexError):
        scraper.get_team_elo_by_date("2024-08-31", "Non Existing Team")


def test_get_avg_league_elo_by_date(monkeypatch):
    monkeypatch.setattr(module.sd, "ClubElo", lambda: FakeClubElo())
    scraper = module.ClubEloScraper()

    avg = scraper.get_avg_league_elo_by_date("2024-08-31", "ENG-Premier League")

    assert avg == 1775.0
