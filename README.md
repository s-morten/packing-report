# packing-report

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

Player-level football (soccer) analytics pipeline. Rates players on metrics that capture their indirect impact on the pitch — actions that affect the team's performance but aren't directly attributable to the individual.

## Metrics

| Metric | Description |
|---|---|
| **GDE** (Goal Difference Elo) | An Elo-based system that rates players on margin of victory. An advancement of the plus-minus score from basketball. |
| **xT-impact** | Proportional Expected Threat impact of a player during a game. |
| **VAEP** | Valuing Actions by Estimating Probabilities — rates every on-ball action by its impact on scoring/conceding probability. |

### Backlog

- Time to ball recovery
- Average distance to opposition / separation (requires tracking data)

## Architecture

```
packing-report/
├── data_retrieval/        # Scraping and API data fetching (WhoScored, api-sports.io, ClubElo)
├── database_io/           # Database access layer (SQLAlchemy ORM, repositories, SQLite/PostgreSQL/Oracle)
├── insights/              # Metric computation pipeline (minutes, goals, VAEP, xT)
├── eval/                  # Model evaluation and plotting scripts
├── pipeline/              # ETL orchestration (fetch schedule, formations, event data)
├── models/                # Trained ML models (xT grid, VAEP XGBoost) and training scripts
├── utils/                 # Shared utilities (date helpers, filesystem I/O, football data parsing)
├── configs/               # Configuration files and name-mapping dictionaries
├── tests/                 # Test suite
└── srv/                   # Oracle TNS configuration
```

## Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Copy environment file and configure
cp .env.example .env
```

Configure `.env` with your database connection and API keys (see `.env.example`).

## Usage

### Fetch match event data

```bash
uv run pipeline/fetch_data.py --config configs/config.toml
```

### Compute player metrics

```bash
uv run insights/gi.py
```

### Run evaluation scripts

```bash
uv run eval/some_script.py
```

### Lint

```bash
make lint
```

## Testing

```bash
uv run pytest
```

## Project Status

Active development. The new normalized database schema (Game, Player, PlayerGame, PlayerGameMetric) is being rolled out alongside legacy tables. See `database_io/MIGRATION_PLAN.md` for details.
