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
| **xTPM** (xT plus-minus) | Regression-based team-differential rating. Each match is split into segments of constant line-up; a team-level dependent variable is regressed on signed player indicators and every player gets a rating. |

### xT plus-minus

The plus-minus metric is a two-stage pipeline.

**Stage 1** (`uv run insights/gi.py`) computes the low-level metrics for each game and persists the
facts the regression needs:

- `PLAYER_GAME` — one row per player with the presence interval `on_minute` / `off_minute`
- `GAME_SEGMENT` — one row per segment, where a segment runs between two changes of line-up, with
  both dependent variables normalised per 90 (`net_xt_per90`, `gd90`)

Only substitution boundaries start a new segment, and the match ends at the first sending-off, so
every retained segment is 11-v-11 and no red-card dummy players are needed.

**Stage 2** (`uv run pipeline/update_metrics.py`) reads those segments back, replays the games in
chronological order, and absorbs each one into a persistent ridge state. Rebuilding from the stored
intervals means it needs neither the raw events nor the xT model, so it runs in seconds.

Ratings are published after **every** match, so each player has a rating history rather than just an
end-of-season number. Three metrics are written per player-game:

| Metric | Description |
|---|---|
| `xtpm_rating` | xT plus-minus rating — net xT differential per 90 the player contributed. |
| `gdpm_rating` | Same regression against goal difference. The baseline to compare against. |
| `xtpm_credit` | The raw, pre-shrinkage increment the player's latest match added to their rating. |

The two dependent variables are solved together against a single shared design matrix, so the ridge
penalty `ridge` and the recency discount `forgetting` live in `configs/config.toml` and are **not**
persisted with the state. Changing either re-scores every already-processed match without
replaying a single event.

```bash
# Rescore everything from the stored segments
uv run pipeline/update_metrics.py --rebuild

# Score the next unprocessed matches into the existing state
uv run pipeline/update_metrics.py

# Restrict the scope
uv run pipeline/update_metrics.py --leagues GER-Bundesliga GER-Bundesliga2 --seasons 18 19 20 21 22
```

Note that `ridge` is a penalty on the accumulated statistics, so its useful magnitude depends on
how much weight has accumulated. A penalty that is mild over tens of games will shrink a multi-season
run very hard; calibrate it against `state._n` rather than fixing it a priori.

### Backlog

- Time to ball recovery
- Average distance to opposition / separation (requires tracking data)

## Architecture

```
packing-report/
├── data_retrieval/        # Scraping and API data fetching (WhoScored, api-sports.io, ClubElo)
├── database_io/           # Database access layer (SQLAlchemy ORM, repositories, SQLite/PostgreSQL/Oracle)
├── insights/              # Metric computation pipeline (minutes, goals, VAEP, xT, xT plus-minus)
├── eval/                  # Model evaluation and plotting scripts
├── pipeline/              # ETL orchestration (fetch schedule, formations, event data, score segments)
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
uv sync --all-packages

# Copy environment file and configure
cp .env.example .env
```

Configure `.env` with your database connection and API keys (see `.env.example`).

> Use `uv sync --all-packages`. A plain `uv sync` prunes the workspace packages and leaves the
> editable installs in a broken state.

## Usage

### Fetch match event data

```bash
uv run pipeline/fetch_data.py --config configs/config.toml
```

### Compute player metrics (stage 1)

```bash
uv run insights/gi.py

# Re-derive games that were processed before a metric changed
uv run insights/gi.py --force --limit 30
```

### Score the plus-minus ratings (stage 2)

```bash
uv run pipeline/update_metrics.py --rebuild
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
uv run --all-packages python -m pytest tests -q
```

> Use the command above. A plain `uv run pytest` runs against the system Python and fails on the
> workspace dependencies. The suite also emits `FutureWarning`s from `socceraction`; silence them
> with `PYTHONWARNINGS=ignore` if you want clean output.

## Project Status

Active development. The new normalized database schema (Game, Player, PlayerGame, PlayerGameMetric) is being rolled out alongside legacy tables. See `database_io/MIGRATION_PLAN.md` for details.
