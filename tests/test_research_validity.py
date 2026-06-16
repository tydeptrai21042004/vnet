from __future__ import annotations

from pathlib import Path

from vanet_osm_warning.config import ProjectConfig
from vanet_osm_warning.reliability import packet_error_rate
from vanet_osm_warning.synthetic_runner import SyntheticPlatoonRunner


def test_per_increases_with_packet_size() -> None:
    assert packet_error_rate(1400, 1e-6) > packet_error_rate(600, 1e-6) > packet_error_rate(100, 1e-6)


def test_direct_and_multihop_comparison_uses_same_controller() -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    cases = {c["id"]: c for c in cfg.cases}
    assert cases["C2_v2v_direct_dsrc_300B"]["control_algorithm"] == cases["C3_v2v_multihop_dsrc_300B"]["control_algorithm"]


def test_protocol_comparison_is_same_packet_controller_range() -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    cases = {c["id"]: c for c in cfg.cases}
    dsrc = cases["C7_v2v_multihop_packet_600B"]
    cv2x = cases["C12_v2v_cv2x_packet_600B"]
    assert dsrc["channel"]["packet_size_bytes"] == cv2x["channel"]["packet_size_bytes"] == 600
    assert dsrc["control_algorithm"] == cv2x["control_algorithm"]
    assert cfg.merged_channel_for_case(dsrc)["communication_range_m"] == cfg.merged_channel_for_case(cv2x)["communication_range_m"]


def test_synthetic_contact_constraint_prevents_negative_gap(tmp_path: Path) -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    case = next(c for c in cfg.cases if c["id"] == "C1_accident_no_warning")
    result = SyntheticPlatoonRunner(cfg.global_cfg, seed=42).run_case(
        case, cfg.merged_synthetic_for_case(case), cfg.merged_channel_for_case(case), tmp_path,
        v2i_cfg=cfg.merged_v2i_for_case(case), rsus_cfg=cfg.rsus_for_case(case),
    )
    assert result.min_gap_m >= 0.0


def test_config_has_multiple_research_seeds() -> None:
    cfg = ProjectConfig.load("configs/default_cases.json")
    assert len(cfg.global_cfg["seeds"]) >= 5
