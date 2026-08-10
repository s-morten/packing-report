import argparse
import logging
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from data_retrieval.scraper.whoscored_chromeless import WhoScored
from dotenv import load_dotenv

from database_io.connection import get_session, init_db
from database_io.models.metric import PlayerGameMetric
from database_io.models.player import Player

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_DEFAULT_DATA_DIR = Path.home() / "soccerdata" / "data" / "WhoScored"


def load_data(
    leagues: list[str] | None = None,
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    if leagues is None:
        leagues = ["GER-Bundesliga2", "GER-Bundesliga"]
    if seasons is None:
        seasons = [18, 19, 20, 21, 22]

    init_db()
    with get_session() as session:
        gde_rows = (
            session.query(PlayerGameMetric.player_id, PlayerGameMetric.game_id, PlayerGameMetric.value)
            .filter(PlayerGameMetric.metric == "gde")
            .all()
        )
        player_rows = session.query(Player.id, Player.name).all()

    df = pd.DataFrame(gde_rows, columns=["player_id", "game_id", "gde"])
    if df.empty:
        logger.warning("No GDE data found in PLAYER_GAME_METRIC.")
        return df

    name_df = pd.DataFrame(player_rows, columns=["player_id", "name"])
    df = df.merge(name_df, on="player_id", how="left")
    df["name"] = df["name"].fillna(f"Player_{df['player_id']}")

    data_dir = Path(os.environ.get("SOCCERDATA_DIR", str(_DEFAULT_DATA_DIR)))
    ws = WhoScored(leagues=leagues, seasons=seasons, data_dir=data_dir)
    schedule = ws.read_schedule().reset_index()
    sched = schedule[["game_id", "date", "league"]].drop_duplicates("game_id")
    sched["date"] = pd.to_datetime(sched["date"])
    df = df.merge(sched, on="game_id", how="left")

    df = df.sort_values(["date", "game_id"]).reset_index(drop=True)
    logger.info("Loaded %d GDE records across %d players", len(df), df["player_id"].nunique())
    return df


def plot_top_players(df: pd.DataFrame, top_n: int, output_dir: Path):
    latest = df.loc[df.groupby("player_id")["date"].idxmax()]
    top = latest.nlargest(top_n, "gde")

    fig, ax = plt.subplots(figsize=(10, max(4, top_n * 0.4)))
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(top)))[::-1]
    bars = ax.barh(range(len(top)), top["gde"].values, color=colors)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top["name"].values)
    ax.invert_yaxis()
    ax.set_xlabel("ELO Rating")
    ax.set_title(f"Top {top_n} Players by Latest ELO")

    for bar, val in zip(bars, top["gde"].values, strict=True):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2, f"{val:.0f}", va="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_dir / "top_players.png", dpi=150)
    plt.close(fig)
    logger.info("Saved top_players.png")


def plot_elo_trajectory(df: pd.DataFrame, top_n: int, output_dir: Path):
    latest = df.loc[df.groupby("player_id")["date"].idxmax()]
    top_ids = latest.nlargest(top_n, "gde")["player_id"].tolist()

    fig, ax = plt.subplots(figsize=(12, 6))
    cmap = plt.cm.Set2
    for i, pid in enumerate(top_ids):
        player_df = df[df["player_id"] == pid].sort_values("date")
        name = player_df["name"].iloc[0]
        ax.plot(player_df["date"], player_df["gde"], color=cmap(i / max(top_n - 1, 1)), label=name, linewidth=1.5)

    ax.set_xlabel("Date")
    ax.set_ylabel("ELO Rating")
    ax.set_title(f"ELO Trajectory — Top {top_n} Players")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(output_dir / "elo_trajectory.png", dpi=150)
    plt.close(fig)
    logger.info("Saved elo_trajectory.png")


def plot_elo_distribution(df: pd.DataFrame, output_dir: Path):
    latest = df.loc[df.groupby("player_id")["date"].idxmax()]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(latest["gde"].values, bins=50, color="steelblue", edgecolor="white", alpha=0.8)
    ax.axvline(latest["gde"].mean(), color="red", linestyle="--", label=f"Mean: {latest['gde'].mean():.0f}")
    ax.set_xlabel("ELO Rating")
    ax.set_ylabel("Number of Players")
    ax.set_title("Distribution of Latest ELO Ratings")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "elo_distribution.png", dpi=150)
    plt.close(fig)
    logger.info("Saved elo_distribution.png")


def plot_elo_vs_goals(df: pd.DataFrame, output_dir: Path):
    latest = df.loc[df.groupby("player_id")["date"].idxmax()]
    goals_df = df.groupby("player_id")["gde"].mean().reset_index().rename(columns={"gde": "avg_gde"})
    latest = latest.merge(goals_df, on="player_id", suffixes=("", "_avg"))

    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(
        latest["avg_gde"],
        latest["gde"],
        c=latest["gde"],
        cmap="viridis",
        alpha=0.6,
        s=20,
    )
    plt.colorbar(scatter, ax=ax, label="Latest ELO")
    ax.set_xlabel("Average GDE (across all games)")
    ax.set_ylabel("Latest ELO")
    ax.set_title("Latest ELO vs. Average GDE")
    fig.tight_layout()
    fig.savefig(output_dir / "elo_vs_gde.png", dpi=150)
    plt.close(fig)
    logger.info("Saved elo_vs_gde.png")


def plot_elo_by_league(df: pd.DataFrame, output_dir: Path):
    latest = df.loc[df.groupby("player_id")["date"].idxmax()]
    by_league = latest.groupby("league")

    league_labels = []
    league_data = []
    for league, group in sorted(by_league):
        league_labels.append(league)
        league_data.append(group["gde"].values)

    fig, ax = plt.subplots(figsize=(12, max(5, len(league_labels) * 0.5)))
    bp = ax.boxplot(league_data, labels=league_labels, patch_artist=True)
    for patch, color in zip(bp["boxes"], plt.cm.Set3(np.linspace(0, 1, len(league_labels))), strict=True):
        patch.set_facecolor(color)

    ax.set_ylabel("ELO Rating")
    ax.set_title("ELO Distribution by League")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(output_dir / "elo_by_league.png", dpi=150)
    plt.close(fig)
    logger.info("Saved elo_by_league.png")


def plot_elo_stability(df: pd.DataFrame, top_n: int, output_dir: Path):
    latest = df.loc[df.groupby("player_id")["date"].idxmax()]
    top_ids = latest.nlargest(top_n, "gde")["player_id"].tolist()

    fig, ax = plt.subplots(figsize=(10, max(4, top_n * 0.4)))
    names = []
    mean_elos = []
    std_elos = []

    for pid in top_ids:
        player_df = df[df["player_id"] == pid].sort_values("date")
        names.append(player_df["name"].iloc[0])
        elos = player_df["gde"].tail(10).values
        mean_elos.append(np.mean(elos))
        std_elos.append(np.std(elos) if len(elos) > 1 else 0)

    y_pos = range(len(names))
    ax.barh(y_pos, mean_elos, xerr=std_elos, color="steelblue", capsize=3)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlabel("Mean ELO (last 10 games)")
    ax.set_title(f"Top {top_n} — ELO Stability (error bars = std over last 10 games)")
    fig.tight_layout()
    fig.savefig(output_dir / "elo_stability.png", dpi=150)
    plt.close(fig)
    logger.info("Saved elo_stability.png")


def main():
    parser = argparse.ArgumentParser(description="MoV / Goal-Difference ELO Evaluation")
    parser.add_argument("--top", type=int, default=20, help="Number of top players to highlight (default: 20)")
    parser.add_argument("--model-path", type=str, default=None, help="Path to trained model for validation plot")
    parser.add_argument("--output-dir", type=str, default="eval/output", help="Output directory for plots")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_data()
    if df.empty:
        logger.error("No GDE data available. Run models/train/train_mov.py first.")
        return

    plot_top_players(df, args.top, output_dir)
    plot_elo_trajectory(df, args.top, output_dir)
    plot_elo_distribution(df, output_dir)
    plot_elo_vs_goals(df, output_dir)

    if df["league"].notna().any():
        plot_elo_by_league(df, output_dir)

    plot_elo_stability(df, args.top, output_dir)

    if args.model_path:
        logger.info("Model validation not yet implemented — placeholder for future extension.")

    logger.info("All plots saved to %s", output_dir)


if __name__ == "__main__":
    main()
