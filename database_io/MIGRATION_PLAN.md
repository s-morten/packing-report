# Database Migration Plan

## Goals

- Drop unused tables: `SCHEDULE`, `PREDICTION`, `SQUADS`, `GAMES` (old), `BASE_METRIC` (old)
- Separate hard performance facts from calculated metrics
- Proper `GAME` entity so game metadata isn't duplicated
- Explicit cross-source player matching via `PLAYER_ALIAS`
- Remove metric versioning
- Kit number stored per-game instead of temporal `SQUADS` table

---

## Final Schema

### `BASIS.PLAYER` *(unchanged columns)*

WhoScored ID is always the canonical key.

```sql
id        INTEGER PK         -- WhoScored player ID
name      VARCHAR
birthday  DATE
fapi_id   INTEGER NULL       -- football-api-sports ID for formation/lineup matching
```

### `BASIS.PLAYER_ALIAS` *(new)*

Explicit cross-source matching, replaces fuzzy team+kit+season lookups.

```sql
player_id INTEGER PK FK→PLAYER
source    VARCHAR PK         -- e.g. "footballsquads", "fbref", "clubelo"
source_id VARCHAR            -- identifier in that source
```

### `BASIS.TEAM` *(unchanged)*

```sql
id   INTEGER PK
name VARCHAR
```

### `BASIS.GAME` *(new)*

One row per match. Game metadata no longer duplicated across per-player rows.

```sql
id          INTEGER PK      -- WhoScored game ID
date        DATE
home_team   INTEGER FK→TEAM
away_team   INTEGER FK→TEAM
league      VARCHAR
season      VARCHAR
game_minutes INTEGER         -- 90 (or more with extra time)
```

### `BASIS.PLAYER_GAME` *(new — replaces old GAMES + parts of BASE_METRIC)*

Hard, factual per-player per-game data. Written once, never recalculated.

```sql
player_id   INTEGER PK FK→PLAYER
game_id     INTEGER PK FK→GAME
team_id     INTEGER FK→TEAM
minutes     INTEGER          -- minutes on pitch
starter     BOOLEAN
goals_for   INTEGER          -- team goals while player on pitch
goals_against INTEGER
kit_number  INTEGER          -- per game kit number (no temporal SQUADS table needed)
is_home     BOOLEAN
```

### `METRICS.PLAYER_GAME_METRIC` *(new — replaces BASE_METRIC for derived values)*

Calculated metrics only. Re-running a computation upserts the row (no versioning).

```sql
player_id   INTEGER PK FK→PLAYER
game_id     INTEGER PK FK→GAME
metric      VARCHAR PK       -- e.g. "gde", "xg", "pm", "xt"
value       FLOAT
```

### `SCRAPING.FOOTBALLSQUADS_RAW` *(renamed from FOOTBALLSQUADS_BIRTHDAY)*

Same columns. Renamed to clarify it's a staging/raw import table.

```sql
kit_number    INTEGER PK
name          VARCHAR PK
nationality   VARCHAR
position      VARCHAR
height        VARCHAR
weight        VARCHAR
date_of_birth VARCHAR
place_of_birth VARCHAR
previous_club VARCHAR
team          VARCHAR PK
league        VARCHAR
season        VARCHAR PK
```

### `SCRAPING.SCRAPE_LOG` *(renamed from FOOTBALLSQUADS_PROCESSED)*

Tracks which cache files were already imported.

```sql
file VARCHAR PK
```

---

## Tables to Drop

| Table | Reason |
|---|---|
| `BASIS.GAMES` (old) | Replaced by `GAME` + `PLAYER_GAME` |
| `BASIS.SQUADS` | Kit number moved to `PLAYER_GAME.kit_number` |
| `METRICS.BASE_METRIC` (old) | Replaced by `PLAYER_GAME` (facts) + `PLAYER_GAME_METRIC` (metrics) |
| `METRICS.PREDICTION` | Unused |
| `SCRAPING.SCHEDULE` | Unused |

---

## Migration Steps

### Step 1: Create new ORM models

Edit `database_io/dims/tables.py` and `database_io/faks/tables.py`:
- Add `Game`, `PlayerGame` models
- Add `PlayerGameMetric` model
- Rename `Birthday_Footballsquads` → `FootballsquadsRaw`
- Rename `Processed_Footballsquads` → `ScrapeLog`
- Add `PlayerAlias` model
- Remove `Games` (old), `Squads`, `Schedule`, `Prediction`, `Metric` (old)

### Step 2: Create new DB handler classes

New files:
- `database_io/dims/game.py` — `DB_game` (insert game, get all games, game exists)
- `database_io/dims/player_game.py` — `DB_player_game` (insert/update player_game row)
- `database_io/dims/metric.py` — `DB_player_game_metric` (upsert metric, get metric, batch upsert)
- `database_io/faks/alias.py` — `DB_player_alias` (insert/get aliases)

Updated files:
- `database_io/faks/player.py` — add `insert_alias()` method (or keep it separate)
- `database_io/dims/player_age.py` → rename class to `DB_footballsquads_raw`, update table references

Removed files:
- `database_io/faks/squads.py` — delete entirely
- `database_io/faks/schedule.py` — delete entirely
- `database_io/faks/predictions.py` — delete entirely
- `database_io/dims/games.py` — delete entirely
- `database_io/dims/elo.py` — delete entirely

### Step 3: Update DB_handler composition

Edit `database_io/db_handler.py`:
- Remove `squads`, `schedule`, `predictions` attributes
- Add `game`, `player_game`, `metric`, `alias` attributes
- Rename `player_age` → `footballsquads_raw`
- Rename `metric` (old) → `metric` (new `DB_player_game_metric`)

### Step 4: Update metrics code

- `insights/metrics/low_level/minutes.py:88-94` — write to `PLAYER_GAME.minutes` instead of `BASE_METRIC`
- `insights/metrics/low_level/goals.py:40-52` — write to `PLAYER_GAME.goals_for` / `goals_against` instead of `BASE_METRIC`
- `insights/game/game_timeline.py:147-177` — create `GAME` row, write game metadata, remove commented-out elo/pm batch writes
- Update `GameTimeline.handle()` to build a single `PLAYER_GAME` row per player
- (Future) `PlayerELO.update()` → write to `PLAYER_GAME_METRIC`

### Step 5: Update pipeline scripts

- `insights/gi.py:39` — change `dbh.games.get_all_games(0.1)` to `dbh.game.get_all_game_ids()`
- `pipeline/fetch_formation.py` — use `PLAYER_ALIAS` for matching instead of `DB_squads.match_players()`

### Step 6: Update web queries

- `database_io/webpage.py` — rewrite queries to join `PLAYER_GAME` + `PLAYER_GAME_METRIC` + `GAME` instead of old `GAMES` + `BASE_METRIC`
- Inline `Latest_elo` view logic into the queries or create a DB view

### Step 7: Update reset script

- `database_io/reset_db.py` — update to delete from new tables

### Step 8: Update tests

- `tests/test_goals.py` — update `write` test expectations for new table structure
- `tests/test_minutes.py` — same
- Remove any tests referencing dropped handler classes

### Step 9: Create DB migration SQL

Generate DDL for the new tables. Run:

```sql
-- New tables
CREATE TABLE BASIS.GAME (...);
CREATE TABLE BASIS.PLAYER_GAME (...);
CREATE TABLE METRICS.PLAYER_GAME_METRIC (...);
CREATE TABLE BASIS.PLAYER_ALIAS (...);

-- Rename staging tables
ALTER TABLE SCRAPING.FOOTBALLSQUADS_BIRTHDAY RENAME TO FOOTBALLSQUADS_RAW;
ALTER TABLE SCRAPING.FOOTBALLSQUADS_PROCESSED RENAME TO SCRAPE_LOG;

-- Drop old tables
DROP TABLE BASIS.GAMES CASCADE CONSTRAINTS;
DROP TABLE BASIS.SQUADS CASCADE CONSTRAINTS;
DROP TABLE METRICS.BASE_METRIC CASCADE CONSTRAINTS;
DROP TABLE METRICS.PREDICTION CASCADE CONSTRAINTS;
DROP TABLE SCRAPING.SCHEDULE CASCADE CONSTRAINTS;
```
