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
        cfg = ProjectConfig(
            global_cfg=raw.get("global", {}),
            synthetic_platoon=raw.get("synthetic_platoon", {}),
            channel_default=raw.get("channel_default", {}),
            cases=raw.get("cases", []),
            protocols=raw.get("protocols", {}),
            v2i_default=raw.get("v2i_default", {}),
            rsus=raw.get("rsus", []),
            sumo_fixed_incident=raw.get("sumo_fixed_incident", {}),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        errors: list[str] = []
        if float(self.global_cfg.get("duration_s", 0)) <= 0:
            errors.append("global.duration_s must be > 0")
        if float(self.global_cfg.get("step_length_s", 0)) <= 0:
            errors.append("global.step_length_s must be > 0")
        if int(self.synthetic_platoon.get("num_vehicles", 0)) < 2:
            errors.append("synthetic_platoon.num_vehicles must be >= 2")
        if float(self.synthetic_platoon.get("gap_m", 0)) <= 0:
            errors.append("synthetic_platoon.gap_m must be > 0")
        ids = [str(c.get("id", "")) for c in self.cases]
        if any(not x for x in ids):
            errors.append("every case must have a non-empty id")
        if len(ids) != len(set(ids)):
            errors.append("case ids must be unique")
        allowed_modes = {"none", "v2v", "v2i", "hybrid"}
        for case in self.cases:
            cid = case.get("id", "<unknown>")
            mode = str(case.get("communication_mode", "none")).lower()
            if mode not in allowed_modes:
                errors.append(f"{cid}: communication_mode must be one of {sorted(allowed_modes)}")
            if bool(case.get("warning_enabled", False)) and mode == "none":
                errors.append(f"{cid}: warning_enabled=true requires a communication mode")
            for section_name, section in (("channel", case.get("channel", {})), ("v2i", case.get("v2i", {}))):
                if "packet_size_bytes" in section and int(section["packet_size_bytes"]) <= 0:
                    errors.append(f"{cid}: {section_name}.packet_size_bytes must be > 0")
                if "max_hops" in section and int(section["max_hops"]) <= 0:
                    errors.append(f"{cid}: {section_name}.max_hops must be > 0")
                if "downlink_accounting" in section and str(section["downlink_accounting"]).lower() not in {"broadcast", "unicast"}:
                    errors.append(f"{cid}: {section_name}.downlink_accounting must be broadcast or unicast")
            override = case.get("synthetic_override", {})
            if "num_vehicles" in override and int(override["num_vehicles"]) < 2:
                errors.append(f"{cid}: synthetic_override.num_vehicles must be >= 2")
        for pname, proto in self.protocols.items():
            if float(proto.get("data_rate_bps", 0)) <= 0:
                errors.append(f"protocols.{pname}.data_rate_bps must be > 0")
            for key in ("loss_probability", "bit_error_rate"):
                if key in proto and not 0 <= float(proto[key]) <= 1:
                    errors.append(f"protocols.{pname}.{key} must be in [0,1]")
        if errors:
            raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))

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
