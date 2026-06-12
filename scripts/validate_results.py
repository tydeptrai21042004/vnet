#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate VANET result exports.")
    parser.add_argument("results_dir", nargs="?", default="results/demo")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    summary_path = results_dir / "summary_metrics.csv"
    validation_path = results_dir / "validation_report.csv"
    incident_path = results_dir / "incident_locations.csv"
    xlsx_path = results_dir / "results.xlsx"

    missing = [p for p in [summary_path, validation_path, incident_path, xlsx_path] if not p.exists()]
    if missing:
        for p in missing:
            print(f"[FAIL] Missing expected result file: {p}")
        return 2

    summary = pd.read_csv(summary_path)
    validation = pd.read_csv(validation_path)
    incidents = pd.read_csv(incident_path)

    accident_cases = summary[summary["incident_expected"].astype(bool)]
    missing_incident = accident_cases[~accident_cases["incident_started"].astype(bool)]
    fail_rows = validation[validation["status"].astype(str).str.startswith("FAIL")]

    print(f"[CHECK] cases={len(summary)} accident_cases={len(accident_cases)}")
    print(f"[CHECK] incident locations rows={len(incidents)}")
    print(f"[CHECK] Excel workbook={xlsx_path}")

    if not missing_incident.empty:
        print("[FAIL] Some accident-enabled cases have no incident_started:")
        print(missing_incident[["case_id", "result_status"]].to_string(index=False))
        return 3
    if not fail_rows.empty:
        print("[FAIL] Validation report contains FAIL rows:")
        print(fail_rows[["case_id", "status", "detail"]].to_string(index=False))
        return 4

    print("[OK] All accident-enabled cases have incident_started=True and no validation FAIL rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
