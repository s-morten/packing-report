"""Stage 2 of the xT plus-minus pipeline: turn persisted segments into per-game player ratings.

Stage 1 (``insights/gi.py``) is the expensive half. It reads the event feed, prices every action
with the xT model once, and writes one ``METRICS.GAME_SEGMENT`` row per segment plus the per-player
presence intervals in ``BASIS.PLAYER_GAME``.

This script is the cheap half. It reads only those tables -- never the event feed, never the xT
model -- accumulates the ridge sufficient statistics game by game in chronological order, and writes
a rating for every player after every game they played.

Two properties are worth stating up front.

**The rating is updated after every game, not once at the end.** Games are walked in date order and
the state is re-solved after each one, so ``PLAYER_GAME_METRIC`` holds a genuine rating *history*:
``xtpm_rating`` for a player in a given game is what the model believed after absorbing that game
and every earlier one. That is the same shape as the legacy ``updated_pm`` / ``updated_elo`` rows.

**The penalty is not part of the state.** ``ridge`` is applied at solve time only, so re-running
this script with a different ``--ridge`` re-scores the whole history in seconds. ``forgetting`` and
``weight_mode`` *are* part of the state, because they change the accumulation itself; changing
those requires ``--rebuild``.

Examples
--------
Score everything with the configured penalties::

    uv run pipeline/update_metrics.py

Re-score the same history at a different ridge, no re-accumulation::

    uv run pipeline/update_metrics.py --ridge 0.1

Discard the state and accumulate a different scope from scratch::

    uv run pipeline/update_metrics.py --rebuild --seasons 18 19 20 21 22
"""

import argparse
import logging
import tomllib
from pathlib import Path

from dotenv import load_dotenv
from game.game_segments import segments_from_rows
from metrics.high_level.xtpm import FeatureSpec, XtPlusMinus, build_observation

from database_io.connection import get_session, init_db
from database_io.repositories.metric_repo import DB_metric
from database_io.repositories.player_game_repo import DB_player_game
from database_io.repositories.segment_repo import DB_segment

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CONFIG = _ROOT / "configs" / "config.toml"
_DEFAULT_LEAGUES = ["GER-Bundesliga2", "GER-Bundesliga"]

#: Metric names written per player per game, and the dependent variable each one comes from.
_RATING_METRICS = {"xtpm_rating": "xt", "gdpm_rating": "gd"}
_CREDIT_METRICS = {"xtpm_credit": "xt"}
_PLUS_MINUS_METRICS = tuple(_RATING_METRICS) + tuple(_CREDIT_METRICS)


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text()).get("xtpm", {})


def season_strings(seasons: list) -> set[str]:
    """Every spelling of a season that ``BASIS.GAME.season`` might hold.

    The DB stores the readable form produced by :func:`utils.date_utils.to_season`
    (``"2022/2023"``), while both pipeline scripts are configured with the scraper's own integers
    (``22``). The two-digit form is expanded against a 2000 base, so 22 means 2022/2023; a
    four-digit form like 2223 is read directly. Anything else is passed through untouched so an
    already-correct spelling still works.
    """
    forms: set[str] = set()
    for season in seasons:
        text_season = str(season).strip()
        forms.add(text_season)
        if not text_season.isdigit():
            continue
        digits = int(text_season)
        start_year = 2000 + digits if digits < 100 else digits // 100
        forms.add(f"{start_year}/{start_year + 1}")
        forms.add(f"{start_year}{start_year + 1}")
    return forms


def _matches(frame, leagues: list[str] | None, seasons: list[str] | None) -> list[int]:
    """Game ids in the requested scope, preserving the frame's chronological order."""
    selected = frame
    if leagues:
        selected = selected[selected["league"].isin(leagues)]
    if seasons:
        wanted = season_strings(seasons)
        selected = selected[selected["season"].astype(str).isin(wanted)]
    return selected["game_id"].drop_duplicates().tolist()


def score_games(
    session,
    state: XtPlusMinus,
    game_ids: list[int],
    weight_mode: str,
    limit: int | None = None,
) -> dict:
    """Absorb ``game_ids`` in the order given, writing a rating row for every player after each.

    Returns counters so the caller can log what actually happened rather than what it intended.
    """
    segment_repo = DB_segment()
    player_game_repo = DB_player_game()
    metric_repo = DB_metric()

    segments = segment_repo.get_segments(session, game_ids)
    player_games = player_game_repo.get_player_games(session, game_ids)
    if segments.empty:
        return {"games": 0, "segments": 0, "rows": 0, "skipped": 0}

    segments_by_game = {int(gid): group for gid, group in segments.groupby("game_id")}
    players_by_game = {int(gid): group for gid, group in player_games.groupby("game_id")}

    spec = state.spec
    stats = {"games": 0, "segments": 0, "rows": 0, "skipped": 0}

    for game_id in game_ids:
        rows = segments_by_game.get(int(game_id))
        if rows is None or rows.empty:
            stats["skipped"] += 1
            continue

        game_segments = segments_from_rows(
            rows.to_dict("records"),
            players_by_game.get(int(game_id), []).to_dict("records"),
        )
        observations = [
            build_observation(
                home=segment.home,
                away=segment.away,
                net_xt_per90=float(row["net_xt_per90"]),
                goals_home=int(row["goals_home"]),
                goals_away=int(row["goals_away"]),
                duration_minutes=float(row["duration_minutes"]),
                column_of=state.column_of,
                spec=spec,
                weight_mode=weight_mode,
            )
            for segment, (_, row) in zip(game_segments, rows.iterrows(), strict=True)
        ]
        if not observations:
            stats["skipped"] += 1
            continue

        ratings = state.observe(int(game_id), observations)
        if ratings is None:
            # Already absorbed: the state was not advanced, and this game's rows hold the rating at
            # the end of that game, which must not be overwritten with today's ratings.
            stats["skipped"] += 1
            continue

        stats["games"] += 1
        stats["segments"] += len(observations)

        batch = []
        for player_id, entry in ratings.items():
            for metric_name, dv in _RATING_METRICS.items():
                batch.append([player_id, int(game_id), float(entry[dv]), metric_name])
            for metric_name, dv in _CREDIT_METRICS.items():
                batch.append([player_id, int(game_id), float(entry[f"{dv}_credit"]), metric_name])
        metric_repo.delete_metrics(session, [int(game_id)], _PLUS_MINUS_METRICS)
        metric_repo.insert_batch_metric(session, batch)
        stats["rows"] += len(batch)

        if limit is not None and stats["games"] >= limit:
            logger.info("Reached --limit %d, stopping early", limit)
            break

    return stats


def main():
    parser = argparse.ArgumentParser(description="Score match segments into per-game xT plus-minus ratings")
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG, help="Path to config.toml")
    parser.add_argument("--leagues", nargs="+", default=None, help="Leagues to include (default: from config)")
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=None,
        help="Seasons to include, as the scraper numbers them (e.g. 18 19 20 21 22, or 1819 2223)",
    )
    parser.add_argument("--ridge", type=float, default=None, help="Ridge penalty (default: from config)")
    parser.add_argument("--forgetting", type=float, default=None, help="Per-game discount, 0 < g <= 1")
    parser.add_argument("--weight-mode", choices=["duration", "uniform"], default=None)
    parser.add_argument("--no-home-advantage", action="store_true", help="Drop the twelfth-man dummy column")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Discard any existing state and accumulate from scratch (required to change forgetting)",
    )
    parser.add_argument("--state", type=Path, default=None, help="Override the state file path")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N games (smoke tests)")
    args = parser.parse_args()

    load_dotenv()
    settings = load_config(args.config)
    leagues = args.leagues or _DEFAULT_LEAGUES
    ridge = args.ridge if args.ridge is not None else float(settings.get("ridge", 1.0))
    forgetting = args.forgetting if args.forgetting is not None else float(settings.get("forgetting", 1.0))
    weight_mode = args.weight_mode or settings.get("weight_mode", "duration")
    state_path = Path(args.state or settings.get("state_path", "models/model/xtpm_state.npz"))
    if not state_path.is_absolute():
        state_path = _ROOT / state_path

    dummy = bool(settings.get("home_advantage_dummy", True)) and not args.no_home_advantage
    spec = FeatureSpec(home_advantage_dummy=dummy)

    init_db()
    with get_session() as session:
        segments = DB_segment().get_segments(session)
        if segments.empty:
            raise SystemExit("No GAME_SEGMENT rows found -- run `uv run insights/gi.py` (stage 1) first")

        game_ids = _matches(segments, leagues, args.seasons)
        if not game_ids:
            raise SystemExit(f"No segments in scope for leagues={leagues} seasons={args.seasons}")
        logger.info("Scoping to %d games (%s)", len(game_ids), ", ".join(leagues))

        if args.rebuild or not state_path.exists():
            if state_path.exists():
                logger.info("Discarding existing state at %s", state_path)
            state = XtPlusMinus(spec=spec, forgetting=forgetting, ridge=ridge, weight_mode=weight_mode)
        else:
            state = XtPlusMinus.load(state_path)
            logger.info(
                "Resumed %s: %d players, %d games already absorbed",
                state_path,
                state.n_players,
                len(state.absorbed_game_ids),
            )
            if state.forgetting != forgetting or state.weight_mode != weight_mode:
                raise SystemExit(
                    f"Existing state was built with forgetting={state.forgetting} weight_mode={state.weight_mode!r}; "
                    "re-run with --rebuild to change those"
                )
            # ridge and spec are solve-time / structural choices and are safe to change in place.
            state.ridge = ridge
            state.spec = spec

        stats = score_games(session, state, game_ids, weight_mode, limit=args.limit)
        state.save(state_path)

    logger.info(
        "Absorbed %d games / %d segments, wrote %d metric rows (%d games already absorbed, left untouched)",
        stats["games"],
        stats["segments"],
        stats["rows"],
        stats["skipped"],
    )
    logger.info("State: %d players, %d games, saved to %s", state.n_players, len(state.absorbed_game_ids), state_path)

    for dv in ("xt", "gd"):
        ratings = state.ratings(dv)
        top = sorted(ratings.items(), key=lambda kv: kv[1], reverse=True)[:5]
        logger.info("Top 5 by %s rating: %s", dv, ", ".join(f"{pid}={value:+.4f}" for pid, value in top))


if __name__ == "__main__":
    main()
