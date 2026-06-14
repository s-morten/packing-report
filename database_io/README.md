# database-io

SQLAlchemy-based database access layer for the packing-report project. Provides ORM models, repository classes, and connection management supporting **SQLite**, **PostgreSQL**, and **Oracle** backends.

## Quick Start

```python
from database_io import get_session, Game, Player, PlayerGameMetric

with get_session() as session:
    games = session.query(Game).all()
```

## Database Support

| Backend | Env `DB_TYPE` | Driver |
|---|---|---|
| SQLite (default) | `sqlite` | `sqlite3` |
| PostgreSQL | `postgres` | `psycopg` (v3) |
| Oracle | `oracle` | `oracledb` |

## Schema

Three logical schemas mapped via configurable schema names:

| Schema | Tables | Purpose |
|---|---|---|
| **BASIS** | `Game`, `Player`, `PlayerAlias`, `PlayerGame`, `Team` | Core entities (players, teams, games, player-game facts) |
| **METRICS** | `PlayerGameMetric` | Computed per-player per-game analytics (GDE, xT, VAEP, Elo) |
| **SCRAPING** | `FootballsquadsRaw`, `ScrapeLog` | Raw imported data and import tracking |

## Structure

```
database_io/
├── connection.py          # Engine factory, session management, schema routing
├── db_handler.py          # Facade over all repositories
├── models/
│   ├── base.py            # Declarative base
│   ├── basis.py           # Game, Player, PlayerAlias, PlayerGame, Team
│   ├── metrics.py         # PlayerGameMetric
│   └── scraping.py        # FootballsquadsRaw, ScrapeLog
├── repositories/
│   ├── game_repo.py       # DB_games
│   ├── metric_repo.py     # DB_metric
│   ├── player_repo.py     # DB_player
│   ├── player_age_repo.py # DB_player_age
│   ├── team_repo.py       # DB_team
│   ├── squads_repo.py     # DB_squads
│   ├── schedule_repo.py   # DB_schedule
│   └── predictions_repo.py# DB_predictions
├── reset_db.py            # Helper to clear all data
├── MIGRATION_PLAN.md      # Schema migration docs
└── pyproject.toml
```

## Migration Status

The codebase is migrating from denormalized legacy tables (`BASIS.GAMES`, `METRICS.BASE_METRIC`) to a normalized schema. Both old and new models coexist. See [MIGRATION_PLAN.md](./MIGRATION_PLAN.md) for details.
