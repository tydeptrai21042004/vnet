from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from .models import CaseMetrics, EventLog


NA_TEXT = "N/A"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_events_csv(event_log: EventLog, path: str | Path) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    rows = event_log.rows
    if not rows:
        path.write_text("time_s,event\n", encoding="utf-8")
        return
    keys = sorted({k for row in rows for k in row.keys()})
    if "time_s" in keys:
        keys.remove("time_s")
        keys.insert(0, "time_s")
    if "event" in keys:
        keys.remove("event")
        keys.insert(1, "event")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _metrics_dataframe(metrics: Iterable[CaseMetrics]) -> pd.DataFrame:
    return pd.DataFrame([m.as_dict() for m in metrics])


def write_summary_csv(metrics: Iterable[CaseMetrics], path: str | Path) -> pd.DataFrame:
    path = Path(path)
    ensure_dir(path.parent)
    df = _metrics_dataframe(metrics)
    df.to_csv(path, index=False)
    return df


def read_summary(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def read_all_event_logs(out_dir: str | Path) -> pd.DataFrame:
    out_dir = Path(out_dir)
    frames: list[pd.DataFrame] = []
    for event_file in sorted(out_dir.glob("events_*.csv")):
        try:
            df = pd.read_csv(event_file)
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        case_id = event_file.name[len("events_") : -len(".csv")]
        if df.empty:
            continue
        if "case_id" not in df.columns:
            df.insert(0, "case_id", case_id)
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["case_id", "time_s", "event"])
    return pd.concat(frames, ignore_index=True, sort=False)


def extract_incident_locations(metrics: Iterable[CaseMetrics], out_dir: str | Path) -> pd.DataFrame:
    """Create one defensible accident-location row per case.

    Primary source is CaseMetrics. Event CSV values are used as a fallback in case
    older result files are analyzed.
    """
    rows: list[dict] = []
    metric_rows = [m.as_dict() for m in metrics]
    for row in metric_rows:
        rows.append(
            {
                "case_id": row.get("case_id"),
                "case_name": row.get("case_name"),
                "incident_expected": row.get("incident_expected"),
                "incident_started": row.get("incident_started"),
                "incident_vehicle": row.get("incident_vehicle"),
                "incident_time_s": row.get("incident_time_s"),
                "edge_id": row.get("incident_edge_id"),
                "lane_id": row.get("incident_lane_id"),
                "lane_position_m": row.get("incident_lane_position_m"),
                "x_m": row.get("incident_x_m"),
                "y_m": row.get("incident_y_m"),
                "result_status": row.get("result_status"),
            }
        )

    df = pd.DataFrame(rows)
    # Fallback from event logs if metrics are missing because this function may be
    # reused on old output folders.
    if df.empty or "incident_started" not in df.columns or not df["incident_started"].fillna(False).any():
        events = read_all_event_logs(out_dir)
        if not events.empty:
            incidents = events[events.get("event", pd.Series(dtype=str)) == "incident_started"].copy()
            rename = {
                "vehicle": "incident_vehicle",
                "lane_position_m": "lane_position_m",
            }
            incidents.rename(columns=rename, inplace=True)
            keep = [c for c in ["case_id", "time_s", "incident_vehicle", "edge_id", "lane_id", "lane_position_m", "x_m", "y_m"] if c in incidents.columns]
            if keep:
                fallback = incidents[keep].drop_duplicates("case_id", keep="first")
                fallback.rename(columns={"time_s": "incident_time_s"}, inplace=True)
                fallback["incident_started"] = True
                return fallback
    return df


def write_incident_locations_csv(metrics: Iterable[CaseMetrics], out_dir: str | Path) -> pd.DataFrame:
    out_dir = ensure_dir(out_dir)
    df = extract_incident_locations(metrics, out_dir)
    df.to_csv(out_dir / "incident_locations.csv", index=False)
    return df


def build_validation_report(metrics: Iterable[CaseMetrics]) -> pd.DataFrame:
    rows: list[dict] = []
    for m in metrics:
        d = m.as_dict()
        incident_expected = bool(d.get("incident_expected", True))
        incident_started = bool(d.get("incident_started", False))
        warning_enabled = str(d.get("communication_mode", "none")).lower() != "none"
        warnings_sent = int(d.get("warnings_sent") or 0)
        target_receivers = int(d.get("target_receivers") or 0)
        status = "OK"
        detail = "Case has valid result rows."
        if incident_expected and not incident_started:
            status = "FAIL"
            detail = "Accident case did not trigger incident_started. Check SUMO route/map or fixed incident config."
        elif not incident_expected:
            status = "OK_NO_INCIDENT_EXPECTED"
            detail = "Normal baseline intentionally has no accident and no warning metrics."
        elif not warning_enabled:
            status = "OK_ACCIDENT_NO_WARNING_BASELINE"
            detail = "Accident happened; communication metrics are N/A because warning is disabled by design."
        elif target_receivers <= 0:
            status = "WARNING_NO_TARGET_RECEIVERS"
            detail = "Accident happened, but no target receiver was found behind/near the accident vehicle."
        elif warnings_sent <= 0:
            status = "FAIL_NO_WARNING_SENT"
            detail = "Warning-enabled accident case has targets but sent no warning packets."
        elif d.get("packet_pdr") is not None and not -1e-9 <= float(d["packet_pdr"]) <= 1.0 + 1e-9:
            status = "FAIL_INVALID_PDR"
            detail = "packet_pdr must be in [0, 1]."
        elif d.get("receiver_coverage") is not None and not -1e-9 <= float(d["receiver_coverage"]) <= 1.0 + 1e-9:
            status = "FAIL_INVALID_COVERAGE"
            detail = "receiver_coverage must be in [0, 1]."
        elif int(d.get("warnings_delivered") or 0) > int(d.get("warnings_sent") or 0):
            status = "FAIL_DELIVERED_EXCEEDS_SENT"
            detail = "Logical delivered packets cannot exceed logical packet attempts."
        elif float(d.get("min_gap_m") or 0.0) < -1e-9:
            status = "FAIL_NEGATIVE_PHYSICAL_GAP"
            detail = "Physical clearance cannot be negative; check collision dynamics."
        rows.append(
            {
                "case_id": d.get("case_id"),
                "incident_expected": incident_expected,
                "incident_started": incident_started,
                "warning_mode": d.get("communication_mode"),
                "target_receivers": target_receivers,
                "warnings_sent": warnings_sent,
                "warnings_delivered": int(d.get("warnings_delivered") or 0),
                "collisions": int(d.get("collisions") or 0),
                "status": status,
                "detail": detail,
            }
        )
    return pd.DataFrame(rows)


def write_validation_report_csv(metrics: Iterable[CaseMetrics], out_dir: str | Path) -> pd.DataFrame:
    out_dir = ensure_dir(out_dir)
    df = build_validation_report(metrics)
    df.to_csv(out_dir / "validation_report.csv", index=False)
    return df


def _summary_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Human-friendly copy: blanks are annotated so Excel does not look empty."""
    if df.empty:
        return df
    display = df.copy()
    explanation_cols = []
    for _, row in display.iterrows():
        if not bool(row.get("incident_expected", True)):
            explanation_cols.append("Normal baseline: no accident/warning by design")
        elif str(row.get("communication_mode", "none")).lower() == "none":
            explanation_cols.append("Accident baseline: warning metrics are N/A by design")
        else:
            explanation_cols.append("Warning-enabled case")
    display["why_some_cells_are_NA"] = explanation_cols
    return display.fillna(NA_TEXT)


def _case_explanation_dataframe(metrics: Iterable[CaseMetrics]) -> pd.DataFrame:
    rows = []
    for m in metrics:
        d = m.as_dict()
        mode = str(d.get("communication_mode", "none")).lower()
        if not bool(d.get("incident_expected", True)):
            explanation = "Normal traffic baseline. It intentionally has no accident, no warning packets, and N/A communication metrics."
        elif mode == "none":
            explanation = "Sudden-brake accident baseline without VANET. Accident location is logged, but warning delay/PDR/coverage are N/A by design."
        else:
            explanation = "Accident case with VANET warning enabled. Incident, warning, receiver coverage, delay, PDR, and packet-size metrics should be checked."
        rows.append(
            {
                "case_id": d.get("case_id"),
                "communication_mode": mode,
                "explanation": explanation,
            }
        )
    return pd.DataFrame(rows)


def _autosize_excel(writer, sheet_name: str, df: pd.DataFrame) -> None:
    try:
        ws = writer.sheets[sheet_name]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(df.columns, start=1):
            max_len = max([len(str(col))] + [len(str(x)) for x in df[col].head(200).fillna(NA_TEXT).tolist()])
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = min(max(max_len + 2, 10), 42)
        for cell in ws[1]:
            cell.style = "Headline 4"
    except (AttributeError, KeyError, TypeError, ValueError):
        # Formatting is optional; data export must never fail because styling failed.
        pass


def write_results_excel(metrics: Iterable[CaseMetrics], out_dir: str | Path, filename: str = "results.xlsx") -> Optional[Path]:
    out_dir = ensure_dir(out_dir)
    metrics_list = list(metrics)
    summary = _metrics_dataframe(metrics_list)
    summary_excel = _summary_for_excel(summary)
    incidents = write_incident_locations_csv(metrics_list, out_dir)
    validation = write_validation_report_csv(metrics_list, out_dir)
    events = read_all_event_logs(out_dir).fillna(NA_TEXT)
    case_explain = _case_explanation_dataframe(metrics_list)

    path = out_dir / filename
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            summary_excel.to_excel(writer, sheet_name="summary_for_excel", index=False)
            summary.to_excel(writer, sheet_name="summary_numeric", index=False)
            incidents.fillna(NA_TEXT).to_excel(writer, sheet_name="incident_locations", index=False)
            validation.fillna(NA_TEXT).to_excel(writer, sheet_name="validation_report", index=False)
            case_explain.to_excel(writer, sheet_name="case_explanation", index=False)
            if not events.empty:
                # Event logs are usually small. If a future run creates too many rows,
                # keep Excel valid and tell the user to inspect per-case CSVs.
                max_excel_rows = 1_048_000
                events.head(max_excel_rows).to_excel(writer, sheet_name="all_events", index=False)
            sheets = {
                "summary_for_excel": summary_excel,
                "summary_numeric": summary,
                "incident_locations": incidents,
                "validation_report": validation,
                "case_explanation": case_explain,
            }
            if not events.empty:
                sheets["all_events"] = events.head(1_048_000)
            for sheet_name, df in sheets.items():
                _autosize_excel(writer, sheet_name, df)
        return path
    except ImportError:
        print("[WARN] openpyxl is not installed; Excel workbook was not written. Install: pip install openpyxl")
        return None


def write_result_exports(metrics: Iterable[CaseMetrics], out_dir: str | Path) -> None:
    """Write all user-facing result files after a run."""
    out_dir = ensure_dir(out_dir)
    metrics_list = list(metrics)
    write_summary_csv(metrics_list, out_dir / "summary_metrics.csv")
    write_incident_locations_csv(metrics_list, out_dir)
    write_validation_report_csv(metrics_list, out_dir)
    xlsx = write_results_excel(metrics_list, out_dir)
    if xlsx is not None:
        print(f"[OK] Excel workbook written: {xlsx}")
