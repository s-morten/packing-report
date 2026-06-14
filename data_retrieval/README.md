# data-retrieval

Fetches football data from external sources — APIs and web scraping. Does **not** handle database communication (delegated to `database-io`).

## Sources

| Source | Package | Data |
|---|---|---|
| [api-sports.io](https://www.api-sports.io/) | `api/football_api.py` | Fixtures, lineups, match odds |
| [WhoScored](https://www.whoscored.com/) | `scraper/whoscored_scraper.py` | Match events (passes, shots, tackles, etc.) |
| [ClubElo](https://www.clubelo.com/) | `scraper/club_elo_scraper.py` | Team and league Elo ratings |
| [footballsquads](http://www.footballsquads.co.uk/) | `scraper/footballsquads_scraper.py` | Squad rosters with kit numbers and player ages |

## Structure

```
data_retrieval/
├── src/data_retrieval/
│   ├── api/
│   │   └── football_api.py        # REST client for api-sports.io
│   └── scraper/
│       ├── club_elo_scraper.py     # ClubElo rating fetcher
│       ├── footballsquads_scraper.py  # Squad roster scraper with caching
│       ├── whoscored_scraper.py    # WhoScored event data (via soccerdata)
│       └── whoscored_chromeless.py # Offline WhoScored parser (cached files)
├── tests/
│   ├── api/
│   └── scraper/
└── pyproject.toml
```

## Dependencies

- `requests`, `beautifulsoup4` — web scraping
- `soccerdata` — high-level football data access
- `pandas`, `numpy` — data manipulation
- `database-io`, `utils` (workspace) — db access and shared utilities

## Usage

```python
from data_retrieval.api.football_api import FApi_Handler
from data_retrieval.scraper.club_elo_scraper import ClubEloScraper

api = FApi_Handler()
schedule = api.get_schedule(league_id=79, season=2024)

elo = ClubEloScraper()
rating = elo.get_team_elo_by_date("2024-09-01", "Bayern Munich")
```
