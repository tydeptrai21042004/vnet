from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


def test_demo_all_cases_produce_valid_exports(tmp_path: Path) -> None:
    out_dir = tmp_path / "demo_all"
    cmd = [
        sys.executable,
        "-m",
        "vanet_osm_warning.cli",
        "demo",
        "--config",
        "configs/default_cases.json",
        "--out",
        str(out_dir),
    ]
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr

    summary = pd.read_csv(out_dir / "summary_metrics.csv")
    validation = pd.read_csv(out_dir / "validation_report.csv")
    incidents = pd.read_csv(out_dir / "incident_locations.csv")

    assert len(summary) == 13
    assert len(incidents) == 13
    accident = summary[summary["incident_expected"].astype(bool)]
    assert len(accident) == 12
    assert accident["incident_started"].astype(bool).all()
    assert not validation["status"].astype(str).str.startswith("FAIL").any()
    assert (out_dir / "results.xlsx").exists()
