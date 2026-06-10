from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ProtocolConfig:
    name: str = "DSRC_80211p"
    data_rate_bps: float = 6_000_000.0
    base_delay_s: float = 0.02
    processing_delay_s: float = 0.005
    queue_delay_s: float = 0.0
    header_size_bytes: int = 48
    payload_size_bytes: int = 252
    packet_size_bytes: int = 300
    communication_range_m: float = 150.0
    loss_probability: float = 0.0

    @property
    def total_packet_size_bytes(self) -> int:
        # Explicit packet_size_bytes has priority. Otherwise header + payload.
        if self.packet_size_bytes > 0:
            return int(self.packet_size_bytes)
        return int(self.header_size_bytes + self.payload_size_bytes)


def compute_tx_delay_s(packet_size_bytes: int, data_rate_bps: float) -> float:
    if data_rate_bps <= 0:
        raise ValueError("data_rate_bps must be positive")
    return (8.0 * float(packet_size_bytes)) / float(data_rate_bps)


def compute_protocol_delay_s(
    packet_size_bytes: int,
    data_rate_bps: float,
    base_delay_s: float,
    processing_delay_s: float = 0.0,
    queue_delay_s: float = 0.0,
) -> float:
    return (
        float(base_delay_s)
        + compute_tx_delay_s(packet_size_bytes, data_rate_bps)
        + float(processing_delay_s)
        + float(queue_delay_s)
    )


def merge_protocol_config(
    protocol_name: str | None,
    protocols: Dict[str, Dict[str, Any]] | None,
    overrides: Dict[str, Any] | None = None,
) -> ProtocolConfig:
    protocols = protocols or {}
    overrides = overrides or {}
    name = protocol_name or overrides.get("protocol") or "DSRC_80211p"
    raw: Dict[str, Any] = {}
    raw.update(protocols.get(name, {}))
    raw.update(overrides)
    # Legacy compatibility: old configs used delay_s instead of base_delay_s.
    if "base_delay_s" not in raw and "delay_s" in raw:
        raw["base_delay_s"] = raw["delay_s"]
    if "packet_size_bytes" not in raw:
        header = int(raw.get("header_size_bytes", 48))
        payload = int(raw.get("payload_size_bytes", 252))
        raw["packet_size_bytes"] = header + payload
    return ProtocolConfig(
        name=str(raw.get("protocol", name)),
        data_rate_bps=float(raw.get("data_rate_bps", 6_000_000.0)),
        base_delay_s=float(raw.get("base_delay_s", 0.02)),
        processing_delay_s=float(raw.get("processing_delay_s", 0.005)),
        queue_delay_s=float(raw.get("queue_delay_s", 0.0)),
        header_size_bytes=int(raw.get("header_size_bytes", 48)),
        payload_size_bytes=int(raw.get("payload_size_bytes", 252)),
        packet_size_bytes=int(raw.get("packet_size_bytes", 300)),
        communication_range_m=float(raw.get("communication_range_m", 150.0)),
        loss_probability=float(raw.get("loss_probability", 0.0)),
    )
