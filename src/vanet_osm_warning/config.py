from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ProjectConfig:
    global_cfg: Dict[str, Any]
    synthetic_platoon: Dict[str, Any]
    channel_default: Dict[str, Any]
    cases: List[Dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def load(path: str | Path) -> "ProjectConfig":
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return ProjectConfig(
            global_cfg=raw.get("global", {}),
            synthetic_platoon=raw.get("synthetic_platoon", {}),
            channel_default=raw.get("channel_default", {}),
            cases=raw.get("cases", []),
        )

    def merged_synthetic_for_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(self.synthetic_platoon)
        cfg.update(case.get("synthetic_override", {}))
        return cfg

    def merged_channel_for_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(self.channel_default)
        cfg.update(case.get("channel", {}))
        return cfg
