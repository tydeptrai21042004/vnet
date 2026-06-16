from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .models import EventLog, VehicleState, WarningMessage
from .protocols import compute_protocol_delay_s, compute_tx_delay_s
from .reliability import packet_error_rate


@dataclass
class RSU:
    rsu_id: str
    x_m: float
    y_m: float = 0.0
    range_m: float = 500.0

    def distance_to_vehicle(self, vehicle: VehicleState) -> float:
        return math.hypot(self.x_m - vehicle.x_m, self.y_m - vehicle.y_m)


@dataclass
class V2IChannel:
    rsus: List[RSU]
    protocol: str = "V2I_LTE_5G"
    packet_size_bytes: int = 300
    header_size_bytes: int = 64
    payload_size_bytes: int = 236
    data_rate_bps: float = 20_000_000.0
    uplink_base_delay_s: float = 0.03
    downlink_base_delay_s: float = 0.03
    processing_delay_s: float = 0.02
    queue_delay_s: float = 0.0
    loss_probability: float = 0.02
    bit_error_rate: float = 0.0
    downlink_accounting: str = "broadcast"  # broadcast or unicast
    rng: random.Random = field(default_factory=random.Random)

    pending: List[WarningMessage] = field(default_factory=list)
    sent_keys: set[tuple] = field(default_factory=set)
    lost_packets: int = 0
    warnings_sent: int = 0
    warnings_delivered: int = 0
    bytes_sent: int = 0
    bytes_delivered: int = 0
    uplink_packets_sent: int = 0
    downlink_packets_sent: int = 0
    uplink_bytes_sent: int = 0
    downlink_bytes_sent: int = 0

    @property
    def total_packet_size_bytes(self) -> int:
        if self.packet_size_bytes > 0:
            return int(self.packet_size_bytes)
        return int(self.header_size_bytes + self.payload_size_bytes)

    @property
    def effective_loss_probability(self) -> float:
        return packet_error_rate(self.total_packet_size_bytes, self.bit_error_rate, self.loss_probability)

    def tx_delay_s(self) -> float:
        return compute_tx_delay_s(self.total_packet_size_bytes, self.data_rate_bps)

    def uplink_delay_s(self) -> float:
        return compute_protocol_delay_s(
            self.total_packet_size_bytes,
            self.data_rate_bps,
            self.uplink_base_delay_s,
            processing_delay_s=0.0,
            queue_delay_s=self.queue_delay_s,
        )

    def downlink_delay_s(self) -> float:
        return compute_protocol_delay_s(
            self.total_packet_size_bytes,
            self.data_rate_bps,
            self.downlink_base_delay_s,
            processing_delay_s=0.0,
            queue_delay_s=self.queue_delay_s,
        )

    def nearest_rsu(self, vehicle: VehicleState) -> Optional[RSU]:
        candidates = [(rsu.distance_to_vehicle(vehicle), rsu) for rsu in self.rsus if rsu.distance_to_vehicle(vehicle) <= rsu.range_m]
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]

    def broadcast_warning(
        self,
        now_s: float,
        origin_vehicle: VehicleState,
        vehicles: Iterable[VehicleState],
        created_time_s: float,
        event_log: EventLog,
        target_followers_only: bool = True,
    ) -> None:
        rsu = self.nearest_rsu(origin_vehicle)
        if rsu is None:
            event_log.add(now_s, "v2i_no_rsu_in_range", origin_id=origin_vehicle.vid)
            return
        event_log.add(now_s, "v2i_rsu_selected", origin_id=origin_vehicle.vid, rsu=rsu.rsu_id)
        total_delay = self.uplink_delay_s() + self.processing_delay_s + self.downlink_delay_s()
        eligible = [v for v in vehicles if v.vid != origin_vehicle.vid and (not target_followers_only or v.index > origin_vehicle.index) and rsu.distance_to_vehicle(v) <= rsu.range_m]
        if not eligible:
            return
        # One physical uplink from the origin to the RSU. Downlink is either one
        # broadcast transmission or one unicast per receiver, selected explicitly.
        self.uplink_packets_sent += 1
        self.uplink_bytes_sent += self.total_packet_size_bytes
        downlink_tx = 1 if self.downlink_accounting.lower() == "broadcast" else len(eligible)
        self.downlink_packets_sent += downlink_tx
        self.downlink_bytes_sent += downlink_tx * self.total_packet_size_bytes
        self.warnings_sent += len(eligible)
        self.bytes_sent += (1 + downlink_tx) * self.total_packet_size_bytes
        for receiver in eligible:
            if receiver.vid == origin_vehicle.vid:
                continue
            if target_followers_only and receiver.index <= origin_vehicle.index:
                continue
            if rsu.distance_to_vehicle(receiver) > rsu.range_m:
                continue
            key = (origin_vehicle.vid, rsu.rsu_id, receiver.vid)
            if key in self.sent_keys:
                continue
            self.sent_keys.add(key)
            if self.rng.random() < self.effective_loss_probability:
                self.lost_packets += 1
                event_log.add(
                    now_s,
                    "v2i_packet_lost",
                    origin_id=origin_vehicle.vid,
                    rsu=rsu.rsu_id,
                    receiver=receiver.vid,
                    protocol=self.protocol,
                    packet_size_bytes=self.total_packet_size_bytes,
                    effective_loss_probability=round(self.effective_loss_probability, 8),
                )
                continue
            msg = WarningMessage(
                msg_id=f"V2I_{origin_vehicle.vid}_{rsu.rsu_id}_{receiver.vid}_{len(self.pending)}",
                origin_id=origin_vehicle.vid,
                sender_id=rsu.rsu_id,
                receiver_id=receiver.vid,
                created_time_s=created_time_s,
                send_time_s=now_s,
                deliver_time_s=now_s + total_delay,
                hop=1,
                link_type="V2I",
                protocol=self.protocol,
                packet_size_bytes=self.total_packet_size_bytes,
                rsu_id=rsu.rsu_id,
                data_rate_bps=self.data_rate_bps,
                tx_delay_s=self.tx_delay_s(),
                queue_delay_s=self.queue_delay_s,
                processing_delay_s=self.processing_delay_s,
            )
            self.pending.append(msg)
            event_log.add(
                now_s,
                "v2i_packet_sent",
                origin_id=origin_vehicle.vid,
                rsu=rsu.rsu_id,
                receiver=receiver.vid,
                protocol=self.protocol,
                packet_size_bytes=self.total_packet_size_bytes,
                deliver_time_s=round(now_s + total_delay, 4),
                tx_delay_s=round(self.tx_delay_s(), 6),
            )

    def deliver_due(self, now_s: float) -> List[WarningMessage]:
        due = [m for m in self.pending if m.deliver_time_s <= now_s + 1e-9]
        self.pending = [m for m in self.pending if m.deliver_time_s > now_s + 1e-9]
        self.warnings_delivered += len(due)
        self.bytes_delivered += sum(int(m.packet_size_bytes) for m in due)
        return due
