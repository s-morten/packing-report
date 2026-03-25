from data_retrieval.scraper import whoscored_scraper as module


class FakeWhoScored:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.read_events_calls = 0

    def read_events(self):
        self.read_events_calls += 1
        return "ok"


def test_init_builds_whoscored_with_config(monkeypatch, tmp_path):
    fake_config = {"whoscored": {"leagues": ["ENG-Premier League"], "seasons": ["2324"]}}
    captured = {}

    def fake_constructor(**kwargs):
        captured.update(kwargs)
        return FakeWhoScored(**kwargs)

    monkeypatch.setattr(module.toml, "load", lambda path: fake_config)
    monkeypatch.setattr(module.sd, "WhoScored", fake_constructor)

    scraper = module.WhoScoredScraper(
        live=True,
        config_path=str(tmp_path / "config.toml"),
        cache_path=str(tmp_path / "cache"),
        chrome_path="/usr/bin/chromium",
    )

    assert captured["leagues"] == ["ENG-Premier League"]
    assert captured["seasons"] == ["2324"]
    assert captured["no_cache"] is True
    assert captured["no_store"] is False
    assert captured["path_to_browser"] == "/usr/bin/chromium"
    assert captured["headless"] is False
    assert str(captured["data_dir"]).endswith("cache")
    assert isinstance(scraper.scraper, FakeWhoScored)


def test_scrape_games_calls_read_events(monkeypatch, tmp_path):
    fake_config = {"whoscored": {"leagues": ["ENG-Premier League"], "seasons": ["2324"]}}
    fake_instance = FakeWhoScored()

    monkeypatch.setattr(module.toml, "load", lambda path: fake_config)
    monkeypatch.setattr(module.sd, "WhoScored", lambda **kwargs: fake_instance)

    scraper = module.WhoScoredScraper(
        live=False,
        config_path=str(tmp_path / "config.toml"),
        cache_path=str(tmp_path / "cache"),
        chrome_path="/usr/bin/chromium",
    )

    scraper.scrape_games()

    assert fake_instance.read_events_calls == 1
