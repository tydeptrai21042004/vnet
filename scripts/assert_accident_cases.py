#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes", "y"})


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strict result checker: every accident-enabled case must have a logged accident location."
    )
    parser.add_argument("results_dir", nargs="?", default="results/demo")
    parser.add_argument(
        "--require-warning-for-warning-cases",
        action="store_true",
        help="Also fail if a warning-enabled accident case has no warning packets sent.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    summary_path = results_dir / "summary_metrics.csv"
    incident_path = results_dir / "incident_locations.csv"
    validation_path = results_dir / "validation_report.csv"

    for path in [summary_path, incident_path, validation_path]:
        if not path.exists():
            print(f"[FAIL] Missing file: {path}")
            return 2

    summary = pd.read_csv(summary_path)
    incidents = pd.read_csv(incident_path)
    validation = pd.read_csv(validation_path)

    required_summary_cols = {"case_id", "incident_expected", "incident_started", "communication_mode"}
    missing_cols = required_summary_cols - set(summary.columns)
    if missing_cols:
        print(f"[FAIL] summary_metrics.csv is missing columns: {sorted(missing_cols)}")
        return 3

    accident_cases = summary[_as_bool(summary["incident_expected"])]
    if accident_cases.empty:
        print("[FAIL] No accident-enabled cases found.")
        return 4

    no_incident = accident_cases[~_as_bool(accident_cases["incident_started"])]
    if not no_incident.empty:
        print("[FAIL] These accident-enabled cases did not start an incident:")
        print(no_incident[["case_id", "result_status"]].to_string(index=False))
        return 5

    location_cols = ["case_id", "incident_started", "incident_time_s", "edge_id", "lane_id", "lane_position_m", "x_m", "y_m"]
    missing_location_cols = [c for c in location_cols if c not in incidents.columns]
    if missing_location_cols:
        print(f"[FAIL] incident_locations.csv is missing columns: {missing_location_cols}")
        return 6

    incident_accident = incidents[incidents["case_id"].isin(accident_cases["case_id"])]
    bad_location = incident_accident[
        incident_accident[["incident_time_s", "lane_id", "lane_position_m", "x_m", "y_m"]]
        .isna()
        .any(axis=1)
    ]
    if not bad_location.empty:
        print("[FAIL] Some accident cases are missing defensible accident location fields:")
        print(bad_location[["case_id", "incident_time_s", "edge_id", "lane_id", "lane_position_m", "x_m", "y_m"]].to_string(index=False))
        return 7

    fail_rows = validation[validation["status"].astype(str).str.startswith("FAIL")]
    if not fail_rows.empty:
        print("[FAIL] validation_report.csv contains FAIL rows:")
        print(fail_rows[["case_id", "status", "detail"]].to_string(index=False))
        return 8

    if args.require_warning_for_warning_cases:
        warning_cases = accident_cases[accident_cases["communication_mode"].astype(str).str.lower() != "none"]
        missing_warning = warning_cases[(warning_cases["warnings_sent"].fillna(0).astype(float) <= 0)]
        if not missing_warning.empty:
            print("[FAIL] These warning-enabled accident cases sent no warning packets:")
            print(missing_warning[["case_id", "communication_mode", "target_receivers", "warnings_sent"]].to_string(index=False))
            return 9

    print(f"[OK] Accident cases checked: {len(accident_cases)}")
    print("[OK] Every accident-enabled case has incident_started=True.")
    print("[OK] Every accident-enabled case has accident time, lane, position, x, and y.")
    if args.require_warning_for_warning_cases:
        print("[OK] Every warning-enabled accident case sent warning packets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
