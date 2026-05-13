from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class VehicleState:
    vid: str
    index: int
    x_m: float
    speed_mps: float
    accel_mps2: float = 0.0
    warning_received_time: Optional[float] = None
    warning_hop: Optional[int] = None
    collided: bool = False
    visual_detection_time: Optional[float] = None


@dataclass
class WarningMessage:
    msg_id: str
    origin_id: str
    sender_id: str
    receiver_id: str
    created_time_s: float
    send_time_s: float
    deliver_time_s: float
    hop: int
    kind: str = "EMERGENCY_BRAKE"


@dataclass
class EventLog:
    rows: list[dict] = field(default_factory=list)

    def add(self, time_s: float, event: str, **kwargs) -> None:
        row = {"time_s": round(float(time_s), 4), "event": event}
        row.update(kwargs)
        self.rows.append(row)


@dataclass
class CaseMetrics:
    case_id: str
    case_name: str
    collisions: int = 0
    unique_warning_receivers: int = 0
    target_receivers: int = 0
    warnings_sent: int = 0
    warnings_delivered: int = 0
    lost_packets: int = 0
    min_gap_m: float = 1e9
    first_warning_time_s: Optional[float] = None
    avg_delay_s: Optional[float] = None
    pdr: Optional[float] = None
    reaction_gain_s: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "collisions": self.collisions,
            "target_receivers": self.target_receivers,
            "unique_warning_receivers": self.unique_warning_receivers,
            "warnings_sent": self.warnings_sent,
            "warnings_delivered": self.warnings_delivered,
            "lost_packets": self.lost_packets,
            "pdr": self.pdr,
            "avg_delay_s": self.avg_delay_s,
            "first_warning_time_s": self.first_warning_time_s,
            "reaction_gain_s": self.reaction_gain_s,
            "min_gap_m": self.min_gap_m,
        }
