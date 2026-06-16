from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from vanet_osm_warning.config import ProjectConfig
from vanet_osm_warning.synthetic_runner import SyntheticPlatoonRunner


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "no_sumo_30_cases.json"


def _load_raw() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _write_fast_config(tmp_path: Path, case_ids: list[str] | None = None) -> Path:
    raw = _load_raw()
    raw["global"]["duration_s"] = 2.5
    raw["global"]["step_length_s"] = 0.5
    raw["synthetic_platoon"]["incident_time_s"] = 0.5
    raw["synthetic_platoon"]["num_vehicles"] = 4
    raw["synthetic_platoon"]["gap_m"] = 12.0
    if case_ids is not None:
        raw["cases"] = [case for case in raw["cases"] if case["id"] in case_ids]
    path = tmp_path / "fast_no_sumo_cases.json"
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "vanet_osm_warning.cli", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )


def test_no_sumo_catalog_has_exactly_30_unique_cases() -> None:
    raw = _load_raw()
    ids = [case["id"] for case in raw["cases"]]
    assert len(ids) == 30
    assert len(set(ids)) == 30
    assert ids[0] == "C0_normal_no_incident"
    assert ids[-1] == "C29_dsrc_congested_latency"


@pytest.mark.parametrize(
    ("case_id", "expected_mode"),
    [
        ("C0_normal_no_incident", "none"),
        ("C3_v2v_multihop_dsrc_300B", "v2v"),
        ("C4_v2i_lte_5g_300B", "v2i"),
        ("C5_hybrid_v2v_v2i_300B", "hybrid"),
        ("C28_dsrc_high_error_channel", "v2v"),
    ],
)
def test_representative_cases_are_loadable(case_id: str, expected_mode: str) -> None:
    cfg = ProjectConfig.load(CONFIG)
    case = next(c for c in cfg.cases if c["id"] == case_id)
    assert case.get("communication_mode", "none") == expected_mode
    synthetic = cfg.merged_synthetic_for_case(case)
    assert int(synthetic["num_vehicles"]) > 0
    if expected_mode in {"v2v", "hybrid"}:
        channel = cfg.merged_channel_for_case(case)
        assert int(channel["packet_size_bytes"]) > 0
        assert float(channel["communication_range_m"]) > 0
    if expected_mode in {"v2i", "hybrid"}:
        v2i = cfg.merged_v2i_for_case(case)
        assert int(v2i["packet_size_bytes"]) > 0
        assert float(v2i["rsu_range_m"]) > 0


def test_single_case_cli_generates_complete_behavior_outputs(tmp_path: Path) -> None:
    case_id = "C3_v2v_multihop_dsrc_300B"
    config = _write_fast_config(tmp_path, [case_id])
    out = tmp_path / "single_case"
    result = _run_cli("no-sumo", "--config", str(config), "--out", str(out), "--seeds", "42")
    assert result.returncode == 0, result.stdout + result.stderr

    required = [
        out / "results.xlsx",
        out / "summary_metrics.csv",
        out / "events_C3_v2v_multihop_dsrc_300B.csv",
        out / "trajectories_C3_v2v_multihop_dsrc_300B.csv",
        out / "behavior_visualization" / "index.html",
        out / "behavior_visualization" / "replay_C3_v2v_multihop_dsrc_300B.html",
        out / "behavior_visualization" / "case_catalog.json",
    ]
    for path in required:
        assert path.exists() and path.stat().st_size > 0, path

    summary = pd.read_csv(out / "summary_metrics.csv")
    assert list(summary["case_id"]) == [case_id]
    trajectories = pd.read_csv(out / f"trajectories_{case_id}.csv")
    assert {"time_s", "vehicle_id", "x_m", "speed_mps"}.issubset(trajectories.columns)
    assert trajectories["vehicle_id"].nunique() == 4


def test_all_30_cases_execute_with_python_runner(tmp_path: Path) -> None:
    raw = _load_raw()
    raw["global"]["duration_s"] = 2.0
    raw["global"]["step_length_s"] = 0.5
    raw["synthetic_platoon"]["incident_time_s"] = 0.5
    raw["synthetic_platoon"]["num_vehicles"] = 4
    config = tmp_path / "all_30_runner.json"
    config.write_text(json.dumps(raw), encoding="utf-8")
    cfg = ProjectConfig.load(config)
    out = tmp_path / "runner_outputs"
    completed = []
    for case in cfg.cases:
        runner = SyntheticPlatoonRunner(cfg.global_cfg, seed=42)
        metrics = runner.run_case(
            case,
            cfg.merged_synthetic_for_case(case),
            cfg.merged_channel_for_case(case),
            out,
            v2i_cfg=cfg.merged_v2i_for_case(case),
            rsus_cfg=cfg.rsus_for_case(case),
        )
        completed.append(metrics.case_id)
        assert (out / f"events_{case['id']}.csv").exists()
        assert (out / f"trajectories_{case['id']}.csv").exists()
    assert len(completed) == 30
    assert len(set(completed)) == 30

