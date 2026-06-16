from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


def test_demo_all_cases_produce_valid_exports(tmp_path: Path) -> None:
    out_dir = tmp_path / "demo_all"
    raw = json.loads(Path("configs/default_cases.json").read_text())
    raw["global"]["duration_s"] = 18.0
    raw["synthetic_platoon"]["incident_time_s"] = 4.0
    test_config = tmp_path / "integration_cases.json"
    test_config.write_text(json.dumps(raw), encoding="utf-8")
    cmd = [
        sys.executable,
        "-m",
        "vanet_osm_warning.cli",
        "demo",
        "--config",
        str(test_config),
        "--out",
        str(out_dir),
        "--seeds",
        "42",
    ]
    env = dict(os.environ)
    src = str(Path.cwd() / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False, env=env)
    assert completed.returncode == 0, completed.stdout + completed.stderr

    summary = pd.read_csv(out_dir / "summary_metrics.csv")
    validation = pd.read_csv(out_dir / "validation_report.csv")
    incidents = pd.read_csv(out_dir / "incident_locations.csv")

    cfg_case_count = 27
    assert len(summary) == cfg_case_count
    assert len(incidents) == cfg_case_count
    accident = summary[summary["incident_expected"].astype(bool)]
    assert len(accident) == cfg_case_count - 1
    assert accident["incident_started"].astype(bool).all()
    assert not validation["status"].astype(str).str.startswith("FAIL").any()
    assert (out_dir / "results.xlsx").exists()
