import argparse
import logging
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import soccerdata as sd
from dotenv import load_dotenv

from database_io.connection import get_session, init_db
from database_io.models.metric import PlayerGameMetric
from database_io.models.player import Player

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

LOW_LEVEL_METRICS = ["minutes", "goals", "vaep", "xt", "time_to_recovery"]
_PER90_METRICS = ["goals", "vaep", "xt"]

_DEFAULT_DATA_DIR = Path.home() / "soccerdata" / "data" / "WhoScored"
_DEFAULT_LEAGUES = ["GER-Bundesliga2", "GER-Bundesliga"]
_DEFAULT_SEASONS = [18, 19, 20, 21, 22]


def load_data(leagues: list[str] | None = None, seasons: list[int] | list[str] | None = None) -> pd.DataFrame:
    if leagues is None:
        leagues = _DEFAULT_LEAGUES
    if seasons is None:
        seasons = _DEFAULT_SEASONS

    init_db()
    with get_session() as session:
        metric_rows = (
            session.query(
                PlayerGameMetric.player_id,
                PlayerGameMetric.game_id,
                PlayerGameMetric.metric,
                PlayerGameMetric.value,
            )
            .filter(PlayerGameMetric.metric.in_(LOW_LEVEL_METRICS))
            .all()
        )
        player_rows = session.query(Player.id, Player.name).all()

    df = pd.DataFrame(metric_rows, columns=["player_id", "game_id", "metric", "value"])
    if df.empty:
        logger.warning("No low-level metric data found in PLAYER_GAME_METRIC.")
        return df

    name_df = pd.DataFrame(player_rows, columns=["player_id", "name"])
    df = df.merge(name_df, on="player_id", how="left")
    df["name"] = df["name"].fillna("Player_" + df["player_id"].astype(str))

    data_dir = Path(os.environ.get("SOCCERDATA_DIR", str(_DEFAULT_DATA_DIR)))
    ws = sd.WhoScored(leagues=leagues, seasons=seasons, data_dir=data_dir)
    schedule = ws.read_schedule().reset_index()
    sched = schedule[["game_id", "date", "league", "season"]].drop_duplicates("game_id")
    df = df.merge(sched, on="game_id", how="left")
    df["date"] = pd.to_datetime(df["date"])

    logger.info("Loaded %d metric records across %d players", len(df), df["player_id"].nunique())
    return df


def pivot_wide(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    wide = df.pivot_table(
        index=["player_id", "game_id", "name", "date", "league", "season"],
        columns="metric",
        values="value",
    ).reset_index()
    for metric in LOW_LEVEL_METRICS:
        if metric not in wide.columns:
            wide[metric] = np.nan
    return wide


def player_summary(wide: pd.DataFrame, min_games: int = 5) -> pd.DataFrame:
    if wide.empty:
        return wide
    metric_cols = [metric for metric in LOW_LEVEL_METRICS if metric in wide.columns]
    group = wide.groupby(["player_id", "name"])
    by_player = wide.groupby("player_id")
    summary = group[metric_cols].mean().reset_index()
    summary["league"] = summary["player_id"].map(by_player["league"].first())
    summary["games"] = summary["player_id"].map(by_player["minutes"].count())
    summary["minutes_played"] = summary["player_id"].map(by_player["minutes"].sum())
    minutes_played = summary["minutes_played"].replace(0, np.nan)
    for metric in _PER90_METRICS:
        if metric not in wide.columns:
            continue
        summary[f"{metric}_per90"] = summary["player_id"].map(by_player[metric].sum()) / minutes_played * 90
    summary = summary[summary["games"] >= min_games].reset_index(drop=True)
    logger.info("Summarised %d players (>= %d games)", len(summary), min_games)
    return summary


def plot_top_players(summary: pd.DataFrame, top_n: int, output_dir: Path):
    for metric in LOW_LEVEL_METRICS:
        if metric not in summary.columns or summary[metric].isna().all():
            continue
        top = summary[summary[metric].notna()].nlargest(top_n, metric)
        if top.empty:
            continue

        fig, ax = plt.subplots(figsize=(10, max(4, len(top) * 0.4)))
        colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(top)))[::-1]
        bars = ax.barh(range(len(top)), top[metric].values, color=colors)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels(top["name"].values)
        ax.invert_yaxis()
        ax.set_xlabel(f"Average {metric}")
        ax.set_title(f"Top {len(top)} Players by Average {metric}")

        for bar, val in zip(bars, top[metric].values, strict=True):
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"{val:.2f}", va="center", fontsize=8)

        fig.tight_layout()
        fig.savefig(output_dir / f"top_{metric}.png", dpi=150)
        plt.close(fig)
        logger.info("Saved top_%s.png", metric)


def plot_trajectory(wide: pd.DataFrame, summary: pd.DataFrame, metric: str, top_n: int, output_dir: Path):
    if metric not in summary.columns or metric not in wide.columns:
        return
    valid = summary[summary[metric].notna()]
    if valid.empty:
        return
    top_ids = valid.nlargest(top_n, metric)["player_id"].tolist()

    fig, ax = plt.subplots(figsize=(12, 6))
    cmap = plt.cm.Set2
    for i, pid in enumerate(top_ids):
        player_df = wide[wide["player_id"] == pid].sort_values("date")
        player_df = player_df[player_df[metric].notna()]
        name = player_df["name"].iloc[0]
        ax.plot(
            player_df["date"],
            player_df[metric],
            color=cmap(i / max(top_n - 1, 1)),
            label=name,
            linewidth=1.5,
        )

    ax.set_xlabel("Date")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} Trajectory — Top {len(top_ids)} Players")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(output_dir / f"trajectory_{metric}.png", dpi=150)
    plt.close(fig)
    logger.info("Saved trajectory_%s.png", metric)


def plot_distribution(summary: pd.DataFrame, output_dir: Path):
    metric_cols = [m for m in LOW_LEVEL_METRICS if m in summary.columns and not summary[m].isna().all()]
    if not metric_cols:
        return

    fig, axes = plt.subplots(1, len(metric_cols), figsize=(4 * len(metric_cols), 4))
    axes = axes if isinstance(axes, np.ndarray) else [axes]
    for ax, metric in zip(axes, metric_cols, strict=True):
        values = summary[metric].dropna()
        ax.hist(values, bins=50, color="steelblue", edgecolor="white", alpha=0.8)
        ax.axvline(values.mean(), color="red", linestyle="--", label=f"Mean: {values.mean():.2f}")
        ax.set_xlabel(f"Average {metric}")
        ax.set_ylabel("Number of Players")
        ax.set_title(metric)
        ax.legend(fontsize=7)

    fig.tight_layout()
    fig.savefig(output_dir / "distribution.png", dpi=150)
    plt.close(fig)
    logger.info("Saved distribution.png")


def plot_correlation(summary: pd.DataFrame, output_dir: Path):
    metric_cols = [m for m in LOW_LEVEL_METRICS if m in summary.columns]
    if len(metric_cols) < 2:
        return
    corr = summary[metric_cols].corr()

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)))
    ax.set_yticks(range(len(corr)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.columns)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="Pearson correlation")
    ax.set_title("Correlation of Player Averages")
    fig.tight_layout()
    fig.savefig(output_dir / "correlation.png", dpi=150)
    plt.close(fig)
    logger.info("Saved correlation.png")


def plot_by_league(summary: pd.DataFrame, metric: str, output_dir: Path):
    if metric not in summary.columns or "league" not in summary.columns:
        return
    by_league = summary[summary[metric].notna()].groupby("league")
    labels = []
    data = []
    for league, group in sorted(by_league):
        labels.append(league)
        data.append(group[metric].values)

    fig, ax = plt.subplots(figsize=(12, max(5, len(labels) * 0.5)))
    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    for patch, color in zip(bp["boxes"], plt.cm.Set3(np.linspace(0, 1, len(labels))), strict=True):
        patch.set_facecolor(color)

    ax.set_ylabel(metric)
    ax.set_title(f"{metric} by League")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(output_dir / f"by_league_{metric}.png", dpi=150)
    plt.close(fig)
    logger.info("Saved by_league_%s.png", metric)


def main():
    parser = argparse.ArgumentParser(description="Analyse and plot low-level metrics on a per-player basis")
    parser.add_argument("--metric", choices=LOW_LEVEL_METRICS, default="time_to_recovery")
    parser.add_argument("--top", type=int, default=20, help="Number of top players to highlight (default: 20)")
    parser.add_argument("--min-games", type=int, default=5, help="Minimum games per player (default: 5)")
    parser.add_argument("--league", action="append", dest="leagues", default=None, help="League filter (repeatable)")
    parser.add_argument("--season", action="append", dest="seasons", default=None, help="Season filter (repeatable)")
    parser.add_argument("--output-dir", type=str, default="eval/output", help="Output directory for plots")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(leagues=args.leagues, seasons=args.seasons)
    if df.empty:
        logger.error("No low-level metric data available. Run insights/gi.py first.")
        return

    wide = pivot_wide(df)
    summary = player_summary(wide, min_games=args.min_games)
    if summary.empty:
        logger.error("No players with at least %d games.", args.min_games)
        return

    summary.to_csv(output_dir / "player_summary.csv", index=False)
    logger.info("Saved player_summary.csv (%d players)", len(summary))

    plot_top_players(summary, args.top, output_dir)
    plot_trajectory(wide, summary, args.metric, args.top, output_dir)
    plot_distribution(summary, output_dir)
    plot_correlation(summary, output_dir)
    plot_by_league(summary, args.metric, output_dir)

    logger.info("All plots saved to %s", output_dir)


if __name__ == "__main__":
    main()
