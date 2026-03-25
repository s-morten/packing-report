import json

from data_retrieval.api import football_api as module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeConnection:
    def __init__(self, host):
        self.host = host
        self.requests = []
        self.next_payload = {"ok": True}

    def request(self, method, url, headers=None):
        self.requests.append((method, url, headers))

    def getresponse(self):
        return FakeResponse(self.next_payload)


def _build_handler(monkeypatch):
    monkeypatch.setenv("FOOTBALL_API_KEY", "test-key")
    captured = {}

    def fake_https_connection(host):
        conn = FakeConnection(host)
        captured["conn"] = conn
        return conn

    monkeypatch.setattr(module.http.client, "HTTPSConnection", fake_https_connection)
    handler = module.FApi_Handler()
    return handler, captured["conn"]


def test_init_sets_headers_and_connection(monkeypatch):
    handler, conn = _build_handler(monkeypatch)

    assert conn.host == "v3.football.api-sports.io"
    assert handler.headers["x-rapidapi-host"] == "v3.football.api-sports.io"
    assert handler.headers["x-rapidapi-key"] == "test-key"


def test_get_schedule_requests_expected_endpoint(monkeypatch):
    handler, conn = _build_handler(monkeypatch)
    conn.next_payload = {"response": [{"id": 1}]}

    result = handler.get_schedule(39, 2024)

    assert result == {"response": [{"id": 1}]}
    method, url, headers = conn.requests[-1]
    assert method == "GET"
    assert url == "/fixtures?league=39&season=2024&timezone=Europe/Berlin"
    assert headers == handler.headers


def test_get_formation_requests_expected_endpoint(monkeypatch):
    handler, conn = _build_handler(monkeypatch)
    conn.next_payload = {"response": [{"formation": "4-3-3"}]}

    result = handler.get_formation(1226178)

    assert result == {"response": [{"formation": "4-3-3"}]}
    method, url, headers = conn.requests[-1]
    assert method == "GET"
    assert url == "/fixtures/lineups?fixture=1226178"
    assert headers == handler.headers


def test_get_odds_requests_expected_endpoint(monkeypatch):
    handler, conn = _build_handler(monkeypatch)
    conn.next_payload = {"response": [{"bookmaker": "bet365"}]}

    result = handler.get_odds(2024, 1226178, 79)

    assert result == {"response": [{"bookmaker": "bet365"}]}
    method, url, headers = conn.requests[-1]
    assert method == "GET"
    assert url == "/odds?season=2024&bet=1&bookmaker=8&fixture=1226178&league=79"
    assert headers == handler.headers
