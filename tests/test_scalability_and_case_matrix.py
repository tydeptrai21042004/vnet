from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from vanet_osm_warning.config import ProjectConfig
from vanet_osm_warning.synthetic_runner import SyntheticPlatoonRunner


def _case(cfg: ProjectConfig, case_id: str) -> dict:
    return next(case for case in cfg.cases if case["id"] == case_id)


def _run(cfg: ProjectConfig, case_id: str, out: Path, seed: int = 42):
    case = _case(cfg, case_id)
    return SyntheticPlatoonRunner(cfg.global_cfg, seed=seed).run_case(
        case,
        cfg.merged_synthetic_for_case(case),
        cfg.merged_channel_for_case(case),
        out,
        v2i_cfg=cfg.merged_v2i_for_case(case),
        rsus_cfg=cfg.rsus_for_case(case),
    )


def test_default_configuration_uses_at_least_30_vehicles() -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    assert cfg.synthetic_platoon["num_vehicles"] >= 30


def test_case_catalog_contains_control_protocol_density_and_accounting_matrices() -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    ids = {case["id"] for case in cfg.cases}
    required = {
        "C13_v2v_direct_preemptive_dsrc_300B",
        "C14_v2v_multihop_preemptive_dsrc_300B",
        "C15_v2v_direct_emergency_dsrc_300B",
        "C16_v2v_multihop_emergency_dsrc_300B",
        "C17_v2v_cv2x_packet_100B",
        "C18_v2v_cv2x_packet_300B",
        "C19_v2v_cv2x_packet_1400B",
        "C20_v2i_broadcast_600B",
        "C21_v2i_unicast_600B",
        "C22_density_low_12cars",
        "C23_density_medium_30cars",
        "C24_density_high_50cars",
        "C25_hybrid_broadcast_600B",
        "C26_hybrid_unicast_600B",
    }
    assert required <= ids
    assert len(cfg.cases) >= 27


def test_density_overrides_are_strictly_increasing() -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    counts = [
        cfg.merged_synthetic_for_case(_case(cfg, cid))["num_vehicles"]
        for cid in ("C22_density_low_12cars", "C23_density_medium_30cars", "C24_density_high_50cars")
    ]
    assert counts == [12, 30, 50]


def test_50_vehicle_stress_case_remains_physically_valid(tmp_path: Path) -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    result = _run(cfg, "C24_density_high_50cars", tmp_path)
    trajectory = pd.read_csv(tmp_path / "trajectories_C24_density_high_50cars.csv")
    assert trajectory["vehicle_id"].nunique() == 50
    assert result.target_receivers <= 49
    assert result.unique_warning_receivers <= result.target_receivers
    assert result.min_gap_m >= 0.0
    assert 0.0 <= (result.packet_pdr or 0.0) <= 1.0
    assert 0.0 <= (result.receiver_coverage or 0.0) <= 1.0


def test_same_seed_reproduces_stress_case_metrics(tmp_path: Path) -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    a = _run(cfg, "C24_density_high_50cars", tmp_path / "a", seed=77)
    b = _run(cfg, "C24_density_high_50cars", tmp_path / "b", seed=77)
    fields = (
        "warnings_sent", "warnings_delivered", "lost_packets", "unique_warning_receivers",
        "unique_colliding_pairs", "bytes_sent", "packet_pdr", "receiver_coverage", "min_gap_m",
    )
    assert {f: getattr(a, f) for f in fields} == {f: getattr(b, f) for f in fields}


def test_v2i_unicast_accounts_for_more_bytes_than_broadcast(tmp_path: Path) -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    broadcast = _run(cfg, "C20_v2i_broadcast_600B", tmp_path / "broadcast")
    unicast = _run(cfg, "C21_v2i_unicast_600B", tmp_path / "unicast")
    assert unicast.v2i_bytes_sent > broadcast.v2i_bytes_sent
    assert unicast.target_receivers == broadcast.target_receivers


def test_control_matrix_changes_one_factor_per_pair() -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    direct = _case(cfg, "C13_v2v_direct_preemptive_dsrc_300B")
    multihop = _case(cfg, "C14_v2v_multihop_preemptive_dsrc_300B")
    assert direct["control_algorithm"] == multihop["control_algorithm"]
    assert direct["protocol"] == multihop["protocol"]
    assert direct["channel"]["packet_size_bytes"] == multihop["channel"]["packet_size_bytes"]
    assert direct["multi_hop"] is False and multihop["multi_hop"] is True


def test_invalid_vehicle_count_and_accounting_are_rejected(tmp_path: Path) -> None:
    raw = json.loads(Path("configs/default_cases.json").read_text())
    raw["synthetic_platoon"]["num_vehicles"] = 1
    raw["cases"][0]["v2i"] = {"downlink_accounting": "unknown"}
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="num_vehicles|downlink_accounting"):
        ProjectConfig.load(path)
