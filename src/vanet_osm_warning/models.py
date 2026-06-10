from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class VehicleState:
    vid: str
    index: int
    x_m: float
    speed_mps: float
    y_m: float = 0.0
    accel_mps2: float = 0.0
    warning_received_time: Optional[float] = None
    warning_hop: Optional[int] = None
    warning_link_type: Optional[str] = None
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
    link_type: str = "V2V"          # V2V, V2I, I2V, HYBRID
    protocol: str = "DSRC_80211p"
    packet_size_bytes: int = 300
    rsu_id: Optional[str] = None
    data_rate_bps: Optional[float] = None
    tx_delay_s: Optional[float] = None
    queue_delay_s: Optional[float] = None
    processing_delay_s: Optional[float] = None


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
    communication_mode: str = "none"       # none, v2v, v2i, hybrid
    protocol: str = "NONE"
    packet_size_bytes: Optional[int] = None
    control_algorithm: str = "none"

    collisions: int = 0
    unique_warning_receivers: int = 0
    target_receivers: int = 0
    warnings_sent: int = 0
    warnings_delivered: int = 0
    lost_packets: int = 0
    min_gap_m: float = 1e9
    first_warning_time_s: Optional[float] = None
    avg_delay_s: Optional[float] = None
    max_delay_s: Optional[float] = None

    # Correctly separated metrics.
    packet_pdr: Optional[float] = None              # delivered packets / sent packets
    receiver_coverage: Optional[float] = None       # warned vehicles / target vehicles
    pdr: Optional[float] = None                     # legacy alias; same as packet_pdr

    reaction_gain_s: Optional[float] = None
    bytes_sent: int = 0
    bytes_delivered: int = 0
    channel_load: Optional[float] = None            # total transmitted bits / available channel bits
    data_rate_bps: Optional[float] = None

    v2v_warnings_sent: int = 0
    v2v_warnings_delivered: int = 0
    v2v_lost_packets: int = 0
    v2v_bytes_sent: int = 0

    v2i_warnings_sent: int = 0
    v2i_warnings_delivered: int = 0
    v2i_lost_packets: int = 0
    v2i_bytes_sent: int = 0
    rsu_count: int = 0

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "communication_mode": self.communication_mode,
            "protocol": self.protocol,
            "packet_size_bytes": self.packet_size_bytes,
            "control_algorithm": self.control_algorithm,
            "collisions": self.collisions,
            "target_receivers": self.target_receivers,
            "unique_warning_receivers": self.unique_warning_receivers,
            "receiver_coverage": self.receiver_coverage,
            "warnings_sent": self.warnings_sent,
            "warnings_delivered": self.warnings_delivered,
            "lost_packets": self.lost_packets,
            "packet_pdr": self.packet_pdr,
            "pdr": self.pdr,
            "avg_delay_s": self.avg_delay_s,
            "max_delay_s": self.max_delay_s,
            "first_warning_time_s": self.first_warning_time_s,
            "reaction_gain_s": self.reaction_gain_s,
            "min_gap_m": self.min_gap_m,
            "bytes_sent": self.bytes_sent,
            "bytes_delivered": self.bytes_delivered,
            "channel_load": self.channel_load,
            "data_rate_bps": self.data_rate_bps,
            "v2v_warnings_sent": self.v2v_warnings_sent,
            "v2v_warnings_delivered": self.v2v_warnings_delivered,
            "v2v_lost_packets": self.v2v_lost_packets,
            "v2v_bytes_sent": self.v2v_bytes_sent,
            "v2i_warnings_sent": self.v2i_warnings_sent,
            "v2i_warnings_delivered": self.v2i_warnings_delivered,
            "v2i_lost_packets": self.v2i_lost_packets,
            "v2i_bytes_sent": self.v2i_bytes_sent,
            "rsu_count": self.rsu_count,
        }
