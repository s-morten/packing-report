# ruff: noqa: I001

from collections import defaultdict

import pytest

from data_retrieval.scraper import footballsquads_scraper as module


class DummyPlayerAge:
    def __init__(self):
        self.to_sql_calls = []
        self.updated_files = []

    def get_processed_player_age_files(self):
        return ["already_done.pckl"]

    def player_age_to_sql(self, payload):
        self.to_sql_calls.append(payload)

    def update_processed_player_age(self, file_name):
        self.updated_files.append(file_name)


class DummyDBHandler:
    def __init__(self):
        self.player_age = DummyPlayerAge()


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code


def _mock_full_team_html() -> bytes:
    rows = ["<tr><th>No</th><th>Name</th><th>Pos</th></tr>"]
    for number in range(1, 35):
        name = "Hannes Wolf" if number == 11 else f"Player {number}"
        name_cell = f"<i>{name}</i>" if number == 11 else name
        rows.append(f"<tr><td>{number}</td><td>{name_cell}</td><td>MF</td></tr>")
    return f"<html><body><div id='main'><table>{''.join(rows)}</table></div></body></html>".encode()


@pytest.fixture
def scraper():
    return module.Footballsquads_scraper(cache_location="/tmp/cache", db_handler=DummyDBHandler())


def test_validate_row_data(scraper):
    assert scraper.validate_row_data(None) is False
    assert scraper.validate_row_data([]) is False
    assert scraper.validate_row_data(["A", "Name"]) is False
    assert scraper.validate_row_data(["10", "Player Name"]) is True


def test_remove_unwanted_urls(scraper):
    urls = ["./arsenal.htm", "./../index.html", "./../werder.html", "squads.htm/werder_again"]

    filtered = scraper.remove_unwanted_urls(urls)

    assert filtered == ["./arsenal.htm", "./../werder.html"]


def test_fetch_all_links_on_page_filters_forbidden(monkeypatch, scraper):
    html = b"""
    <html><body>
      <a href=\"./arsenal.htm\">Arsenal</a>
      <a href=\"./index.html\">Index</a>
      <a href=\"./chelsea.htm\">Chelsea</a>
    </body></html>
    """
    monkeypatch.setattr(module.requests, "get", lambda url: FakeResponse(content=html))

    links = scraper.fetch_all_links_on_page("http://example.org")

    assert links == ["./arsenal.htm", "./chelsea.htm"]


def test_scrape_kit_number_table_success(monkeypatch, scraper):
    monkeypatch.setattr(module.requests, "get", lambda url: FakeResponse(content=b"<html />", status_code=200))

    result = scraper.scrape_kit_number_table("http://example.org")

    assert result == b"<html />"


def test_scrape_kit_number_table_failure_raises(monkeypatch, scraper):
    monkeypatch.setattr(module.requests, "get", lambda url: FakeResponse(content=b"", status_code=500))

    with pytest.raises(ValueError):
        scraper.scrape_kit_number_table("http://example.org")


def test_extract_numbers_from_html_table_parses_rows_and_italic(scraper):
    html = b"""
    <div id=\"main\">
      <table>
        <tr><th>No</th><th>Name</th><th>Pos</th></tr>
        <tr><td>11</td><td><i>Hannes Wolf</i></td><td>MF</td></tr>
        <tr><td>11</td><td>Duplicate Name</td><td>FW</td></tr>
        <tr><td>12</td><td>Regular Name</td><td>DF</td></tr>
      </table>
    </div>
    """

    result = scraper.extract_numbers_from_html_table(html)

    assert isinstance(result, defaultdict)
    assert result["11"] == ["Hannes Wolf", "MF"]
    assert result["12"] == ["Regular Name", "DF"]


def test_integration_scrape_and_extract_full_mocked_team(monkeypatch, scraper):
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda url: FakeResponse(content=_mock_full_team_html(), status_code=200),
    )

    table_html = scraper.scrape_kit_number_table("http://example.org/full-team")
    table_dict = scraper.extract_numbers_from_html_table(table_html)

    assert isinstance(table_dict, defaultdict)
    assert len(table_dict.keys()) == 34
    assert table_dict["11"][0] == "Hannes Wolf"


def test_extract_numbers_from_html_table_missing_main_raises(scraper):
    with pytest.raises(ValueError):
        scraper.extract_numbers_from_html_table(b"<html><body>No table</body></html>")


def test_scrape_infos_from_filename_returns_replaced_values(monkeypatch, scraper):
    def fake_replace(value, what):
        if what == "teamname":
            return "Arsenal"
        if what == "league":
            return "Premier League"
        raise AssertionError("unexpected replacement type")

    monkeypatch.setattr(module, "replace_from_config", fake_replace)

    result = scraper.scrape_infos_from_filename("2020-2021_eng_prem_arsenal.pckl")

    assert result == ("Arsenal", "Premier League", "2020/2021")


def test_scrape_infos_from_filename_returns_none_for_missing_team(monkeypatch, scraper):
    def fake_replace(value, what):
        if what == "teamname":
            return None
        if what == "league":
            return "Premier League"
        raise AssertionError("unexpected replacement type")

    monkeypatch.setattr(module, "replace_from_config", fake_replace)

    assert scraper.scrape_infos_from_filename("2020-2021_eng_prem_unknown.pckl") is None


def test_cache_to_db_processes_unseen_files(monkeypatch, scraper):
    monkeypatch.setattr(
        module.filesystem_io,
        "directory_files",
        lambda cache_location: ["already_done.pckl", "2020-2021_eng_prem_arsenal.pckl"],
    )
    monkeypatch.setattr(
        scraper,
        "scrape_infos_from_filename",
        lambda cache_file: ("Arsenal", "Premier League", "2020/2021"),
    )
    monkeypatch.setattr(
        module.filesystem_io,
        "footballsquads_table_from_file",
        lambda path: {
            "10": ["Player", "MID", "x", "x", "x", "x", "x", "x"],
            "11": ["Too", "Short"],
        },
    )

    scraper.cache_to_db(leagues=["Premier League"])

    assert len(scraper.db_handler.player_age.to_sql_calls) == 1
    assert scraper.db_handler.player_age.to_sql_calls[0] == [
        "10",
        "Player",
        "MID",
        "x",
        "x",
        "x",
        "x",
        "x",
        "x",
        "Arsenal",
        "Premier League",
        "2020/2021",
    ]
    assert scraper.db_handler.player_age.updated_files == ["2020-2021_eng_prem_arsenal.pckl"]


def test_replace_from_config_invalid_option_raises():
    with pytest.raises(ValueError):
        module.replace_from_config("Arsenal", "invalid")


def test_replace_from_config_reads_mapping(monkeypatch):
    monkeypatch.setattr(module.json, "load", lambda file_obj: {"Arsenal": ["arsenal", "AFC"]})
    monkeypatch.setattr(module, "open", lambda path: object(), raising=False)

    assert module.replace_from_config("arsenal", "teamname") == "Arsenal"
    assert module.replace_from_config("unknown", "teamname") is None
