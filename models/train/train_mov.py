import json
import logging
import os
import pickle
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from data_retrieval.scraper.whoscored_chromeless import WhoScored
from dotenv import load_dotenv
from ngboost import NGBRegressor
from sklearn.model_selection import train_test_split
from tqdm import tqdm

from database_io.connection import get_session, init_db
from database_io.models.metric import PlayerGameMetric

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_DEFAULT_DATA_DIR = Path.home() / "soccerdata" / "data" / "WhoScored"


def _load_player_team_map(ws: WhoScored, game_ids: list[int]) -> pd.DataFrame:
    rows = []
    logger.info("Loading player-team mappings for %d games ...", len(game_ids))
    loader = ws.read_events(match_id=game_ids, output_fmt="loader")
    for gid in tqdm(game_ids, desc="Loader"):
        try:
            pdf = loader.players(gid)
            tdf = loader.teams(game_id=gid)
            team_name_map = dict(zip(tdf["team_id"], tdf["team_name"], strict=True))
            for _, r in pdf.iterrows():
                rows.append(
                    {
                        "game_id": gid,
                        "player_id": int(r["player_id"]),
                        "team_id": int(r["team_id"]),
                        "team_name": team_name_map.get(int(r["team_id"]), ""),
                    }
                )
        except Exception:
            continue
    return pd.DataFrame(rows)


def load_training_data(
    leagues: list[str] | None = None,
    seasons: list[int] | None = None,
    data_dir: Path | str | None = None,
) -> pd.DataFrame:
    if leagues is None:
        leagues = ["GER-Bundesliga2", "GER-Bundesliga"]
    if seasons is None:
        seasons = [18, 19, 20, 21, 22]
    if data_dir is None:
        data_dir = os.environ.get("SOCCERDATA_DIR", "")
        if not data_dir:
            data_dir = _DEFAULT_DATA_DIR
    data_dir = Path(data_dir)

    init_db()
    with get_session() as session:
        minutes_q = (
            session.query(PlayerGameMetric.player_id, PlayerGameMetric.game_id, PlayerGameMetric.value)
            .filter(PlayerGameMetric.metric == "minutes")
            .all()
        )
        goals_q = (
            session.query(PlayerGameMetric.player_id, PlayerGameMetric.game_id, PlayerGameMetric.value)
            .filter(PlayerGameMetric.metric == "goals")
            .all()
        )

    minutes_df = pd.DataFrame(minutes_q, columns=["player_id", "game_id", "minutes"])
    goals_df = pd.DataFrame(goals_q, columns=["player_id", "game_id", "goal_diff"])

    df = minutes_df.merge(goals_df, on=["player_id", "game_id"])
    df["minutes"] = df["minutes"].fillna(0).astype(int)
    df["goal_diff"] = df["goal_diff"].fillna(0).astype(int)

    db_game_ids = sorted(df["game_id"].unique())
    logger.info("Loaded %d player-game records across %d games", len(df), len(db_game_ids))

    team_df = _load_player_team_map(WhoScored(leagues=leagues, seasons=seasons, data_dir=data_dir), db_game_ids)
    logger.info("Loaded %d player-team mappings", len(team_df))

    df = df.merge(team_df, on=["game_id", "player_id"], how="inner")
    logger.info("After merge with team info: %d records", len(df))

    ws = WhoScored(leagues=leagues, seasons=seasons, data_dir=data_dir)
    schedule = ws.read_schedule().reset_index()
    sched = schedule[["league", "season", "game_id", "date", "home_team", "away_team"]].drop_duplicates("game_id")
    sched["date"] = pd.to_datetime(sched["date"])

    df = df.merge(sched, on="game_id", how="inner")
    df["is_home"] = (df["team_name"] == df["home_team"]).astype(int)
    df = df.sort_values(["date", "game_id"]).reset_index(drop=True)
    df["game_minutes"] = 90
    n_records = len(df)
    n_games = df["game_id"].nunique()
    n_players = df["player_id"].nunique()
    logger.info("Final training data: %d records, %d games, %d players", n_records, n_games, n_players)
    return df


def _build_opponent_map(df: pd.DataFrame) -> pd.DataFrame:
    teams_per_game = df[["game_id", "team_id"]].drop_duplicates()
    rows = []
    for gid, group in teams_per_game.groupby("game_id"):
        team_ids = group["team_id"].tolist()
        if len(team_ids) == 2:
            rows.append({"game_id": gid, "team_id": team_ids[0], "opponent_team_id": team_ids[1]})
            rows.append({"game_id": gid, "team_id": team_ids[1], "opponent_team_id": team_ids[0]})
    return pd.DataFrame(rows)


def compute_team_opp_elos(df: pd.DataFrame, player_elos: dict) -> pd.DataFrame:
    df = df.copy()
    df["p_elo"] = df["player_id"].map(player_elos)
    team_avg = df.groupby(["game_id", "team_id"])["p_elo"].mean().reset_index()
    team_avg.columns = ["game_id", "team_id", "team_avg_elo"]
    df = df.merge(team_avg, on=["game_id", "team_id"], how="left")

    opp_map = _build_opponent_map(df)
    opp_avg = team_avg.rename(columns={"team_id": "opponent_team_id", "team_avg_elo": "opp_avg_elo"})
    df = df.merge(opp_map, on=["game_id", "team_id"], how="left")
    df = df.merge(opp_avg, on=["game_id", "opponent_team_id"], how="left")

    df["p_rating"] = df["p_elo"] * 0.33 + df["team_avg_elo"] * 0.67
    df["rating_diff"] = df["p_rating"] - df["opp_avg_elo"]
    df["minutes_missed"] = (df["game_minutes"] - df["minutes"]).clip(lower=0)
    return df


def _calc_k(minutes_played: int, games_played: int, base_k: float = 20.0) -> float:
    minutes_factor = min(minutes_played, 90) / 90
    uncertainty_factor = 1.0 / max(1.0, (games_played / 10) ** 0.5)
    return base_k * minutes_factor * uncertainty_factor


def _build_game_index(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    game_index = {}
    game_dates = {}
    game_teams = {}
    for gid, group in df.groupby("game_id"):
        records = []
        for r in group.itertuples(index=False):
            records.append(
                {
                    "player_id": int(r.player_id),
                    "team_id": int(r.team_id),
                    "is_home": int(r.is_home),
                    "minutes": int(r.minutes),
                    "goal_diff": int(r.goal_diff),
                    "game_minutes": int(r.game_minutes),
                }
            )
        game_index[gid] = records
        game_dates[gid] = group["date"].iloc[0]
        game_teams[gid] = list(group["team_id"].unique())
    return game_index, game_dates, game_teams


def _batch_predict(ngb: NGBRegressor, batch: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array(batch, dtype=float)
    dist = ngb.pred_dist(x)
    lowers = np.atleast_1d(np.asarray(dist.ppf(0.25), dtype=float))
    uppers = np.atleast_1d(np.asarray(dist.ppf(0.75), dtype=float))
    return lowers, uppers


def train_mov_elo(
    leagues: list[str] | None = None,
    seasons: list[int] | None = None,
    data_dir: Path | str | None = None,
    n_iterations: int = 5,
    convergence_threshold: float = 0.5,
    start_elo: float = 1500.0,
    base_k: float = 20.0,
    c: float = 400.0,
    output_prefix: str = "models/model/mov",
) -> NGBRegressor:
    df = load_training_data(leagues, seasons, data_dir)
    all_players = sorted(df["player_id"].unique())
    all_game_ids = df["game_id"].unique()
    logger.info("Players: %d, Games: %d", len(all_players), len(all_game_ids))

    game_index, game_dates, game_teams = _build_game_index(df)
    game_order = sorted(game_dates, key=game_dates.get)

    player_elos = dict.fromkeys(all_players, start_elo)
    player_games_played = dict.fromkeys(all_players, 0)
    minutes_missed_max = (df["game_minutes"] - df["minutes"]).clip(lower=0).max()
    minutes_missed_max = float(minutes_missed_max) if minutes_missed_max > 0 else 1.0

    ngb = None
    elo_diff_max_val = 1.0
    final_elo_per_game = []

    for iteration in range(1, n_iterations + 1):
        logger.info("=== Iteration %d/%d ===", iteration, n_iterations)

        df_iter = compute_team_opp_elos(df, player_elos)

        current_max = max(abs(df_iter["rating_diff"].max()), abs(df_iter["rating_diff"].min()))
        if current_max > 0:
            elo_diff_max_val = current_max

        df_iter["elo_diff_scaled"] = df_iter["rating_diff"] / elo_diff_max_val
        df_iter["min_missed_scaled"] = df_iter["minutes_missed"] / minutes_missed_max

        X = df_iter[["is_home", "elo_diff_scaled", "min_missed_scaled"]].values
        Y = df_iter["goal_diff"].values

        X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=42)

        ngb = NGBRegressor(random_state=42, verbose=False)
        ngb.fit(X_train, Y_train, X_test, Y_test)

        Y_pred = ngb.predict(X_test)
        test_mse = float(np.mean((Y_pred - Y_test) ** 2))
        logger.info("Test MSE: %.4f", test_mse)

        prev_elos = player_elos.copy()
        iter_elo_records = []

        for gid in tqdm(game_order, desc=f"Iter {iteration}"):
            records = game_index[gid]
            team_ids = game_teams.get(gid, [])
            if len(team_ids) != 2:
                continue

            # Split players by team
            team_a = [r for r in records if r["team_id"] == team_ids[0]]
            team_b = [r for r in records if r["team_id"] == team_ids[1]]

            # Compute team avg ELOs once
            team_a_elo = float(np.mean([player_elos[r["player_id"]] for r in team_a]))
            team_b_elo = float(np.mean([player_elos[r["player_id"]] for r in team_b]))

            # Build batch features and metadata
            batch = []
            meta = []
            for r in records:
                p_elo = player_elos[r["player_id"]]
                p_team_elo = team_a_elo if r["team_id"] == team_ids[0] else team_b_elo
                opp_elo = team_b_elo if r["team_id"] == team_ids[0] else team_a_elo
                p_rating = 0.33 * p_elo + 0.67 * p_team_elo
                rating_diff = p_rating - opp_elo
                min_missed = max(0, r["game_minutes"] - r["minutes"])

                batch.append(
                    [
                        r["is_home"],
                        rating_diff / elo_diff_max_val,
                        min_missed / minutes_missed_max,
                    ]
                )
                meta.append(
                    {
                        "player_id": r["player_id"],
                        "p_rating": p_rating,
                        "opp_elo": opp_elo,
                        "minutes": r["minutes"],
                        "goal_diff": r["goal_diff"],
                    }
                )

            # Batch NGBoost prediction
            lowers, uppers = _batch_predict(ngb, batch)

            # Update ELOs
            for i, m in enumerate(meta):
                pid = m["player_id"]
                curr_elo = player_elos[pid]
                mov = m["goal_diff"]
                exp_lower = float(lowers[i]) if i < len(lowers) else 0.0
                exp_upper = float(uppers[i]) if i < len(uppers) else 0.0

                if mov >= exp_lower and mov <= exp_upper:
                    new_elo = curr_elo
                else:
                    game_result = 1 if mov > exp_upper else 0
                    p_rating_val = np.power(10, m["p_rating"] / c)
                    opp_rating_val = np.power(10, m["opp_elo"] / c)
                    expected_outcome = p_rating_val / (p_rating_val + opp_rating_val)
                    k = _calc_k(m["minutes"], player_games_played.get(pid, 0), base_k)
                    new_elo = curr_elo + k * (game_result - expected_outcome)

                player_elos[pid] = new_elo
                player_games_played[pid] = player_games_played.get(pid, 0) + 1
                iter_elo_records.append(
                    {
                        "player_id": pid,
                        "game_id": gid,
                        "gde": new_elo,
                        "date": game_dates.get(gid),
                    }
                )

        final_elo_per_game = iter_elo_records

        changes = [abs(player_elos[pid] - prev_elos.get(pid, start_elo)) for pid in all_players]
        mean_change = float(np.mean(changes))
        logger.info("Mean ELO change: %.4f", mean_change)

        if mean_change < convergence_threshold:
            logger.info("Converged after %d iterations", iteration)
            break

    # Write final ELOs to database
    logger.info("Writing %d ELO records to database ...", len(final_elo_per_game))
    init_db()
    metric_batch = [[r["player_id"], r["game_id"], r["gde"], "gde"] for r in final_elo_per_game]
    with get_session() as session:
        from database_io.repositories.metric_repo import DB_metric

        DB_metric().insert_batch_metric(session, metric_batch)

    # Save model
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    model_path = Path(output_prefix + f"_{timestamp}.pkl")
    metadata_path = Path("models/meta") / f"mov_{timestamp}.json"

    os.makedirs(model_path.parent, exist_ok=True)
    os.makedirs(metadata_path.parent, exist_ok=True)

    model_data = {"model": ngb, "elo_diff_max": elo_diff_max_val, "minutes_missed_max": minutes_missed_max}
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    metadata = {
        "model": "mov",
        "created_utc": datetime.now(UTC).isoformat(),
        "n_iterations": iteration,
        "convergence_threshold": convergence_threshold,
        "start_elo": start_elo,
        "base_k": base_k,
        "c": c,
        "elo_diff_max": elo_diff_max_val,
        "minutes_missed_max": minutes_missed_max,
        "n_players": len(all_players),
        "n_records": len(df),
        "n_games": len(all_game_ids),
        "final_test_mse": test_mse,
        "n_leagues": len(leagues) if leagues else 0,
        "seasons": seasons,
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info("Model saved to %s", model_path)
    logger.info("Metadata saved to %s", metadata_path)
    return ngb


if __name__ == "__main__":
    train_mov_elo()
