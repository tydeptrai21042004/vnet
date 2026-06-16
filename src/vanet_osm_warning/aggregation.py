from __future__ import annotations

from dataclasses import fields
from statistics import mean, pstdev
from typing import Iterable

import pandas as pd

from .models import CaseMetrics


def aggregate_replications(metrics: Iterable[CaseMetrics]) -> tuple[list[CaseMetrics], pd.DataFrame]:
    rows = [m.as_dict() for m in metrics]
    if not rows:
        return [], pd.DataFrame()
    df = pd.DataFrame(rows)
    numeric = [c for c in df.select_dtypes(include="number").columns if c not in {"packet_size_bytes", "data_rate_bps"}]
    summary_rows = []
    aggregate_objects = []
    valid_fields = {f.name for f in fields(CaseMetrics)}
    for case_id, group in df.groupby("case_id", sort=False):
        base = group.iloc[0].to_dict()
        for col in numeric:
            vals = pd.to_numeric(group[col], errors="coerce").dropna().tolist()
            if vals:
                base[col] = mean(vals)
        base["replications"] = len(group)
        for col in numeric:
            vals = pd.to_numeric(group[col], errors="coerce").dropna().tolist()
            base[f"{col}_std"] = pstdev(vals) if len(vals) > 1 else 0.0
        summary_rows.append(base)
        kwargs = {k: v for k, v in base.items() if k in valid_fields}
        for name in ["collisions", "unique_colliding_pairs", "unique_warning_receivers", "target_receivers", "warnings_sent", "warnings_delivered", "lost_packets", "bytes_sent", "bytes_delivered", "duplicate_deliveries", "v2v_warnings_sent", "v2v_warnings_delivered", "v2v_lost_packets", "v2v_bytes_sent", "v2i_warnings_sent", "v2i_warnings_delivered", "v2i_lost_packets", "v2i_bytes_sent", "rsu_count"]:
            if name in kwargs and pd.notna(kwargs[name]):
                kwargs[name] = int(round(float(kwargs[name])))
        aggregate_objects.append(CaseMetrics(**kwargs))
    return aggregate_objects, pd.DataFrame(summary_rows)
