from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from .metrics import ensure_dir


def plot_summary(summary_csv: str | Path, out_dir: str | Path) -> None:
    out_dir = ensure_dir(out_dir)
    df = pd.read_csv(summary_csv)
    if df.empty:
        return

    labels = df["case_id"].astype(str)

    plt.figure(figsize=(12, 5))
    plt.bar(labels, df["collisions"].fillna(0))
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Collisions")
    plt.title("Collision count by VANET case")
    plt.tight_layout()
    plt.savefig(out_dir / "summary_collisions_by_case.png", dpi=180)
    plt.close()

    if "pdr" in df.columns:
        plt.figure(figsize=(12, 5))
        plt.bar(labels, df["pdr"].fillna(0))
        plt.xticks(rotation=35, ha="right")
        plt.ylabel("Packet Delivery Ratio")
        plt.ylim(0, 1.05)
        plt.title("Warning packet delivery ratio by case")
        plt.tight_layout()
        plt.savefig(out_dir / "summary_pdr_by_case.png", dpi=180)
        plt.close()

    if "avg_delay_s" in df.columns:
        plt.figure(figsize=(12, 5))
        plt.bar(labels, df["avg_delay_s"].fillna(0))
        plt.xticks(rotation=35, ha="right")
        plt.ylabel("Average delay (s)")
        plt.title("Average warning delay by case")
        plt.tight_layout()
        plt.savefig(out_dir / "summary_delay_by_case.png", dpi=180)
        plt.close()

    if "min_gap_m" in df.columns:
        plt.figure(figsize=(12, 5))
        plt.bar(labels, df["min_gap_m"].fillna(0))
        plt.xticks(rotation=35, ha="right")
        plt.ylabel("Minimum gap (m)")
        plt.title("Minimum observed gap by case")
        plt.tight_layout()
        plt.savefig(out_dir / "summary_min_gap_by_case.png", dpi=180)
        plt.close()


def plot_trajectory_csv(traj_csv: str | Path, out_dir: str | Path) -> None:
    out_dir = ensure_dir(out_dir)
    traj_csv = Path(traj_csv)
    if not traj_csv.exists():
        return
    df = pd.read_csv(traj_csv)
    if df.empty:
        return
    case_id = traj_csv.stem.replace("trajectories_", "")

    plt.figure(figsize=(12, 6))
    for vid, g in df.groupby("vehicle_id"):
        plt.plot(g["time_s"], g["x_m"], linewidth=1.0, label=str(vid))
    plt.xlabel("Time (s)")
    plt.ylabel("Position x (m)")
    plt.title(f"Vehicle trajectories - {case_id}")
    if df["vehicle_id"].nunique() <= 12:
        plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(out_dir / f"trajectory_{case_id}.png", dpi=180)
    plt.close()

    plt.figure(figsize=(12, 6))
    for vid, g in df.groupby("vehicle_id"):
        plt.plot(g["time_s"], g["speed_mps"], linewidth=1.0, label=str(vid))
    plt.xlabel("Time (s)")
    plt.ylabel("Speed (m/s)")
    plt.title(f"Vehicle speeds - {case_id}")
    if df["vehicle_id"].nunique() <= 12:
        plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(out_dir / f"speed_{case_id}.png", dpi=180)
    plt.close()


def plot_all_trajectories(results_dir: str | Path) -> None:
    results_dir = Path(results_dir)
    plots_dir = ensure_dir(results_dir / "plots")
    for traj_csv in results_dir.glob("trajectories_*.csv"):
        plot_trajectory_csv(traj_csv, plots_dir)
    summary = results_dir / "summary_metrics.csv"
    if summary.exists():
        plot_summary(summary, plots_dir)
