from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from .models import CaseMetrics, EventLog


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


def write_summary_csv(metrics: Iterable[CaseMetrics], path: str | Path) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    df = pd.DataFrame([m.as_dict() for m in metrics])
    df.to_csv(path, index=False)


def read_summary(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)
