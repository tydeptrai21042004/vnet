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
    md.append("# VANET V2V/V2I Collision Warning Simulation Report\n")
    md.append("## Experiment cases\n")
    md.append(df.to_markdown(index=False))
    md.append("\n\n## Metric definitions\n")
    md.append("- **communication_mode**: `none`, `v2v`, `v2i`, or `hybrid`.\n")
    md.append("- **protocol**: abstract communication protocol profile used by the delay/packet model.\n")
    md.append("- **packet_size_bytes**: warning packet size. Larger packets increase transmission delay and communication overhead.\n")
    md.append("- **packet_pdr**: packet-level delivery ratio = delivered packets / sent packets.\n")
    md.append("- **receiver_coverage**: warned affected vehicles / target affected vehicles. This is separated from packet PDR.\n")
    md.append("- **avg_delay_s** and **max_delay_s**: delay from accident creation to warning reception.\n")
    md.append("- **bytes_sent** and **channel_load**: communication overhead indicators.\n")
    md.append("- **collisions** and **min_gap_m**: traffic safety indicators. Lower collisions and higher gap are better.\n")
    md.append("\n## Recommended discussion\n")
    md.append(
        "Compare the no-warning baseline against V2V, V2I, and hybrid communication. "
        "Direct V2V is usually fast and infrastructure-free, but its range is limited. "
        "Multi-hop V2V increases coverage but can increase delay and packet overhead. "
        "V2I uses roadside units, so coverage depends on RSU placement and RSU range. "
        "The hybrid mode combines local V2V warning with infrastructure-assisted warning and is expected to provide the most robust coverage at the cost of higher overhead.\n"
    )
    md.append("\n## Packet-size/protocol discussion\n")
    md.append(
        "Use the generated packet-size plots to explain how larger packets increase transmission time, bytes sent, and channel load. "
        "If packet loss is enabled, packet PDR and receiver coverage may decrease. "
        "This gives a direct experiment for evaluating the impact of communication protocol parameters and packet size on VANET safety performance.\n"
    )
    out_path.write_text("\n".join(md), encoding="utf-8")
