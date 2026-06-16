from __future__ import annotations

from pathlib import Path

from vanet_osm_warning.config import ProjectConfig


def test_default_config_has_expected_cases_and_incident_policy() -> None:
    cfg = ProjectConfig.load(Path("configs/default_cases.json"))
    case_ids = [case["id"] for case in cfg.cases]

    assert len(case_ids) == 27
    assert case_ids[0] == "C0_normal_no_incident"
    assert case_ids[1] == "C1_accident_no_warning"
    assert len(set(case_ids)) == len(case_ids)

    c0 = cfg.cases[0]
    assert c0["incident_enabled"] is False
    assert c0["warning_enabled"] is False
    assert c0["communication_mode"] == "none"

    for case in cfg.cases[1:]:
        assert case["incident_enabled"] is True, f"{case['id']} must be an accident case"

    warning_cases = [case for case in cfg.cases if case.get("warning_enabled")]
    assert warning_cases, "At least one warning case is required"
    for case in warning_cases:
        assert case.get("communication_mode") in {"v2v", "v2i", "hybrid"}

    fixed = cfg.sumo_fixed_incident
    assert fixed.get("enabled") is True
    assert float(fixed.get("time_s", 0)) > 0
    assert float(fixed.get("fallback_after_s", 0)) >= 0
    assert float(fixed.get("search_radius_m", 0)) > 0


def test_protocol_packet_sizes_are_separated_between_v2v_and_v2i() -> None:
    cfg = ProjectConfig.load(Path("configs/default_cases.json"))
    cases = {case["id"]: case for case in cfg.cases}

    small_v2v = cfg.merged_channel_for_case(cases["C6_v2v_multihop_packet_100B"])
    large_v2v = cfg.merged_channel_for_case(cases["C8_v2v_multihop_packet_1400B"])
    small_v2i = cfg.merged_v2i_for_case(cases["C9_v2i_packet_100B"])
    large_v2i = cfg.merged_v2i_for_case(cases["C11_v2i_packet_1400B"])

    assert int(small_v2v["packet_size_bytes"]) == 100
    assert int(large_v2v["packet_size_bytes"]) == 1400
    assert int(small_v2i["packet_size_bytes"]) == 100
    assert int(large_v2i["packet_size_bytes"]) == 1400
