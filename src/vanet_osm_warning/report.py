from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .models import CaseMetrics


def write_markdown_report(metrics: Iterable[CaseMetrics], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([m.as_dict() for m in metrics])
    md = []
    md.append("# VANET Collision Warning Simulation Report\n")
    md.append("## Experiment cases\n")
    md.append(df.to_markdown(index=False))
    md.append("\n\n## How to read the metrics\n")
    md.append("- **collisions**: number of rear-end collision events detected. Lower is better.\n")
    md.append("- **pdr**: packet delivery ratio for warning messages. Higher is better.\n")
    md.append("- **avg_delay_s**: average warning delay. Lower is better.\n")
    md.append("- **reaction_gain_s**: how much earlier the rear vehicles receive a warning compared with pure visual detection baseline. Higher is better.\n")
    md.append("- **min_gap_m**: minimum bumper-to-bumper distance observed. Higher is safer.\n")
    md.append("\n## Recommended discussion for the thesis\n")
    md.append("The baseline without VANET should be compared against direct V2V and multi-hop V2V. If direct V2V improves the first few following vehicles but fails for a long platoon, the multi-hop broadcast case demonstrates why warning propagation is needed. The delay/loss stress case should be used to explain that VANET safety applications require low delay and reliable delivery.\n")
    out_path.write_text("\n".join(md), encoding="utf-8")
