from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from vanet_osm_warning.channel import V2VChannel
from vanet_osm_warning.metrics import write_result_exports
from vanet_osm_warning.models import CaseMetrics, EventLog


def test_larger_packet_size_increases_protocol_delay() -> None:
    small = V2VChannel(packet_size_bytes=100, data_rate_bps=6_000_000, protocol_mode=True)
    large = V2VChannel(packet_size_bytes=1400, data_rate_bps=6_000_000, protocol_mode=True)
    assert large.transmission_delay_s() > small.transmission_delay_s()
    assert large.one_hop_delay_s() > small.one_hop_delay_s()


def test_result_exports_create_csv_excel_and_validation(tmp_path: Path) -> None:
    metrics = [
        CaseMetrics(
            case_id="C0_normal_no_incident",
            case_name="Normal baseline",
            communication_mode="none",
            incident_expected=False,
            incident_started=False,
            result_status="OK_NO_INCIDENT_EXPECTED",
        ),
        CaseMetrics(
            case_id="C1_accident_no_warning",
            case_name="Accident without warning",
            communication_mode="none",
            collisions=3,
            incident_expected=True,
            incident_started=True,
            incident_vehicle="veh_00",
            incident_time_s=25.0,
            incident_edge_id="E0",
            incident_lane_id="E0_0",
            incident_lane_position_m=100.0,
            incident_x_m=10.0,
            incident_y_m=20.0,
            result_status="OK",
        ),
        CaseMetrics(
            case_id="C5_hybrid_v2v_v2i_300B",
            case_name="Hybrid warning",
            communication_mode="hybrid",
            collisions=0,
            target_receivers=4,
            unique_warning_receivers=4,
            warnings_sent=5,
            warnings_delivered=5,
            packet_pdr=1.0,
            pdr=1.0,
            receiver_coverage=1.0,
            avg_delay_s=0.05,
            incident_expected=True,
            incident_started=True,
            incident_vehicle="veh_00",
            incident_time_s=25.0,
            incident_edge_id="E0",
            incident_lane_id="E0_0",
            incident_lane_position_m=100.0,
            incident_x_m=10.0,
            incident_y_m=20.0,
            result_status="OK",
        ),
    ]

    log = EventLog()
    log.add(25.0, "incident_started", vehicle="veh_00", edge_id="E0", lane_id="E0_0", lane_position_m=100, x_m=10, y_m=20)
    # Event CSV writing is exercised indirectly by write_result_exports reading whatever exists.
    write_result_exports(metrics, tmp_path)

    assert (tmp_path / "summary_metrics.csv").exists()
    assert (tmp_path / "incident_locations.csv").exists()
    assert (tmp_path / "validation_report.csv").exists()
    assert (tmp_path / "results.xlsx").exists()

    validation = pd.read_csv(tmp_path / "validation_report.csv")
    assert not validation["status"].astype(str).str.startswith("FAIL").any()

    workbook = pd.ExcelFile(tmp_path / "results.xlsx")
    expected_sheets = {"summary_for_excel", "summary_numeric", "incident_locations", "validation_report", "case_explanation"}
    assert expected_sheets.issubset(set(workbook.sheet_names))

    summary_for_excel = pd.read_excel(workbook, sheet_name="summary_for_excel")
    c1 = summary_for_excel.loc[summary_for_excel["case_id"] == "C1_accident_no_warning"].iloc[0]
    assert "warning metrics are N/A" in str(c1["why_some_cells_are_NA"])


def test_validation_fails_when_accident_case_has_no_incident(tmp_path: Path) -> None:
    metrics = [
        CaseMetrics(
            case_id="C2_v2v_direct_dsrc_300B",
            case_name="Broken accident case",
            communication_mode="v2v",
            incident_expected=True,
            incident_started=False,
            result_status="ERROR_NO_INCIDENT_STARTED",
        )
    ]
    write_result_exports(metrics, tmp_path)
    validation = pd.read_csv(tmp_path / "validation_report.csv")
    assert validation.loc[0, "status"] == "FAIL"
