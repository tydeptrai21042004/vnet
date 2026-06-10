from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .metrics import ensure_dir


def _bar(df: pd.DataFrame, labels, column: str, ylabel: str, title: str, filename: Path, ylim=None) -> None:
    if column not in df.columns:
        return
    plt.figure(figsize=(13, 5))
    plt.bar(labels, df[column].fillna(0))
    plt.xticks(rotation=35, ha="right")
    plt.ylabel(ylabel)
    if ylim is not None:
        plt.ylim(*ylim)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(filename, dpi=180)
    plt.close()


def plot_summary(summary_csv: str | Path, out_dir: str | Path) -> None:
    out_dir = ensure_dir(out_dir)
    df = pd.read_csv(summary_csv)
    if df.empty:
        return

    labels = df["case_id"].astype(str)
    _bar(df, labels, "collisions", "Collisions", "Collision count by case", out_dir / "summary_collisions_by_case.png")
    _bar(df, labels, "packet_pdr", "Packet PDR", "Packet-level delivery ratio by case", out_dir / "summary_packet_pdr_by_case.png", (0, 1.05))
    _bar(df, labels, "receiver_coverage", "Receiver coverage", "Warned target vehicles by case", out_dir / "summary_receiver_coverage_by_case.png", (0, 1.05))
    _bar(df, labels, "avg_delay_s", "Average delay (s)", "Average warning delay by case", out_dir / "summary_delay_by_case.png")
    _bar(df, labels, "bytes_sent", "Bytes sent", "Communication overhead by case", out_dir / "summary_bytes_sent_by_case.png")
    _bar(df, labels, "channel_load", "Channel load", "Estimated channel load by case", out_dir / "summary_channel_load_by_case.png")
    _bar(df, labels, "min_gap_m", "Minimum gap (m)", "Minimum observed gap by case", out_dir / "summary_min_gap_by_case.png")

    if {"packet_size_bytes", "avg_delay_s"}.issubset(df.columns):
        sweep = df.dropna(subset=["packet_size_bytes"])
        if not sweep.empty:
            plt.figure(figsize=(9, 5))
            for mode, g in sweep.groupby("communication_mode"):
                g = g.sort_values("packet_size_bytes")
                plt.plot(g["packet_size_bytes"], g["avg_delay_s"].fillna(0), marker="o", label=str(mode))
            plt.xlabel("Packet size (bytes)")
            plt.ylabel("Average delay (s)")
            plt.title("Packet size impact on warning delay")
            plt.legend()
            plt.tight_layout()
            plt.savefig(out_dir / "packet_size_vs_delay.png", dpi=180)
            plt.close()

    if {"packet_size_bytes", "packet_pdr"}.issubset(df.columns):
        sweep = df.dropna(subset=["packet_size_bytes"])
        if not sweep.empty:
            plt.figure(figsize=(9, 5))
            for mode, g in sweep.groupby("communication_mode"):
                g = g.sort_values("packet_size_bytes")
                plt.plot(g["packet_size_bytes"], g["packet_pdr"].fillna(0), marker="o", label=str(mode))
            plt.xlabel("Packet size (bytes)")
            plt.ylabel("Packet PDR")
            plt.ylim(0, 1.05)
            plt.title("Packet size impact on packet delivery ratio")
            plt.legend()
            plt.tight_layout()
            plt.savefig(out_dir / "packet_size_vs_packet_pdr.png", dpi=180)
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

    if "x_m" in df.columns:
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

    if "speed_mps" in df.columns:
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
