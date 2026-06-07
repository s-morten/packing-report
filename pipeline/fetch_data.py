import argparse
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import soccerdata as sd
import toml
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "config.toml"


def date_to_season_code(d: datetime) -> int:
    """Convert a date to a WhoScored season code.

    A season runs July–June. The code is the start year minus 2000.
    2022-07-01 -> 22, 2023-06-30 -> 22, 2023-07-01 -> 23
    """
    if d.month >= 7:
        return d.year - 2000
    return d.year - 1 - 2000


def date_range_to_season_codes(start: datetime, end: datetime) -> list[int]:
    seasons = set()
    for year in range(start.year - 1, end.year + 2):
        s_start = datetime(year, 7, 1, tzinfo=start.tzinfo)
        s_end = datetime(year + 1, 6, 30, tzinfo=start.tzinfo)
        if start <= s_end and end >= s_start:
            seasons.add(year - 2000)
    return sorted(seasons)


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return toml.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch WhoScored match data for a configurable timeframe.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to config.toml")
    parser.add_argument("--leagues", nargs="*", help="Override leagues from config")
    parser.add_argument("--days-back", type=int, help="Days before today to include")
    parser.add_argument("--days-forward", type=int, help="Days after today to include")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD). Overrides --days-back")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD). Overrides --days-forward")
    parser.add_argument("--data-dir", type=Path, help="WhoScored cache directory. Overrides SOCCERDATA_DIR env")
    parser.add_argument("--chrome-path", type=Path, help="Path to Chromium browser")
    parser.add_argument("--headless", type=lambda x: x.lower() != "false", default=None, help="Run browser headless")
    parser.add_argument("--dry-run", action="store_true", help="Print matches that would be fetched, then exit")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)

    leagues = args.leagues or config.get("whoscored", {}).get("leagues", [])
    if not leagues:
        print("No leagues configured. Set [whoscored] leagues in config.toml or pass --leagues.")
        return

    fetch_config = config.get("fetch", {})
    now = datetime.now(UTC)

    if args.start:
        start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    else:
        start = now - timedelta(days=args.days_back if args.days_back is not None else fetch_config.get("days_back", 7))

    if args.end:
        end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    else:
        end = now + timedelta(
            days=args.days_forward if args.days_forward is not None else fetch_config.get("days_forward", 0)
        )

    if start > end:
        print(f"Error: start ({start.date()}) is after end ({end.date()})")
        return

    seasons = date_range_to_season_codes(start, end)
    if not seasons:
        print(f"No seasons found for date range {start.date()} – {end.date()}")
        return

    data_dir = args.data_dir or Path(os.environ.get("SOCCERDATA_DIR", ""))
    chrome_path = args.chrome_path or Path(fetch_config.get("chrome_path", "/usr/bin/chromium"))
    headless = args.headless if args.headless is not None else fetch_config.get("headless", True)

    print(f"Leagues:      {', '.join(leagues)}")
    print(f"Seasons:      {', '.join(str(s) for s in seasons)}")
    print(f"Date range:   {start.date()} – {end.date()}")
    print(f"Data dir:     {data_dir}")
    print(f"Browser:      {chrome_path}{' (headless)' if headless else ''}")
    print()

    ws = sd.WhoScored(
        leagues=leagues,
        seasons=seasons,
        data_dir=data_dir,
        path_to_browser=chrome_path,
        headless=headless,
    )

    print("Reading schedule...")
    schedule = ws.read_schedule().reset_index()
    if schedule.empty:
        print("No schedule data found for the configured leagues and seasons.")
        return

    if "date" in schedule.columns:
        mask = (schedule["date"] >= start) & (schedule["date"] <= end)
        matches = schedule[mask]
    else:
        print("Warning: schedule has no 'date' column. Using all available matches.")
        matches = schedule

    if matches.empty:
        print(f"No matches found in date range {start.date()} – {end.date()}.")
        return

    match_ids = sorted(matches["game_id"].unique())
    print(f"Matches in range: {len(match_ids)}")
    print(f"First match:      {matches['date'].min().date() if 'date' in matches.columns else 'N/A'}")
    print(f"Last match:       {matches['date'].max().date() if 'date' in matches.columns else 'N/A'}")
    print()

    if args.dry_run:
        print("Dry run — matches that would be fetched:")
        for mid in match_ids:
            row = matches[matches["game_id"] == mid].iloc[0]
            d = row["date"].date() if "date" in row else "?"
            print(f"  {mid} ({d})")
        return

    fetched = 0
    skipped = 0
    errors = []

    for mid in tqdm(match_ids, desc="Fetching match events"):
        try:
            result = ws.read_events(match_id=[mid], on_error="skip")
            if result is not None and not (isinstance(result, pd.DataFrame) and result.empty):
                fetched += 1
            else:
                skipped += 1
        except Exception as e:
            errors.append((mid, str(e)))
            skipped += 1

    print()
    print("=== Summary ===")
    print(f"  Total matches in range:  {len(match_ids)}")
    print(f"  Successfully fetched:    {fetched}")
    print(f"  Skipped / already cached: {skipped}")
    if errors:
        print(f"  Errors:                   {len(errors)}")
        for mid, err in errors[:5]:
            print(f"    - {mid}: {err}")
        if len(errors) > 5:
            print(f"    ... and {len(errors) - 5} more")
    print("Done.")


if __name__ == "__main__":
    main()
