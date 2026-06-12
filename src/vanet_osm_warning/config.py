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
    protocols: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    v2i_default: Dict[str, Any] = field(default_factory=dict)
    rsus: List[Dict[str, Any]] = field(default_factory=list)
    sumo_fixed_incident: Dict[str, Any] = field(default_factory=dict)

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
            protocols=raw.get("protocols", {}),
            v2i_default=raw.get("v2i_default", {}),
            rsus=raw.get("rsus", []),
            sumo_fixed_incident=raw.get("sumo_fixed_incident", {}),
        )

    def merged_synthetic_for_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(self.synthetic_platoon)
        cfg.update(case.get("synthetic_override", {}))
        return cfg

    def merged_channel_for_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(self.channel_default)
        protocol_name = case.get("protocol", cfg.get("protocol"))
        if protocol_name and protocol_name in self.protocols:
            cfg.update(self.protocols[protocol_name])
            cfg["protocol"] = protocol_name
        cfg.update(case.get("channel", {}))
        # If case overrides protocol inside channel, apply that protocol first then case-specific values.
        protocol_name = cfg.get("protocol")
        if protocol_name and protocol_name in self.protocols:
            protocol_values = dict(self.protocols[protocol_name])
            protocol_values.update(cfg)
            cfg = protocol_values
            cfg["protocol"] = protocol_name
        return cfg

    def merged_v2i_for_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(self.v2i_default)
        protocol_name = case.get("v2i_protocol", case.get("protocol", cfg.get("protocol")))
        if protocol_name and protocol_name in self.protocols:
            cfg.update(self.protocols[protocol_name])
            cfg["protocol"] = protocol_name
        cfg.update(case.get("v2i", {}))
        protocol_name = cfg.get("protocol")
        if protocol_name and protocol_name in self.protocols:
            protocol_values = dict(self.protocols[protocol_name])
            protocol_values.update(cfg)
            cfg = protocol_values
            cfg["protocol"] = protocol_name
        return cfg

    def rsus_for_case(self, case: Dict[str, Any]) -> List[Dict[str, Any]]:
        return case.get("rsus", self.rsus)

    def sumo_incident_for_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(self.sumo_fixed_incident)
        cfg.update(case.get("sumo_fixed_incident", {}))
        return cfg
