from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable, List, Set

from .models import VehicleState, WarningMessage, EventLog
from .protocols import compute_protocol_delay_s, compute_tx_delay_s
from .reliability import packet_error_rate


@dataclass
class V2VChannel:
    communication_range_m: float = 150.0
    # Legacy fixed delay. If protocol_mode=True, this is replaced by protocol delay.
    delay_s: float = 0.15
    loss_probability: float = 0.0
    bit_error_rate: float = 0.0
    rebroadcast_delay_s: float = 0.05
    max_hops: int = 1
    rng: random.Random = field(default_factory=random.Random)

    # Protocol/packet-size model.
    protocol: str = "DSRC_80211p"
    packet_size_bytes: int = 300
    header_size_bytes: int = 48
    payload_size_bytes: int = 252
    data_rate_bps: float = 6_000_000.0
    base_delay_s: float = 0.02
    processing_delay_s: float = 0.005
    queue_delay_s: float = 0.0
    protocol_mode: bool = True

    pending: List[WarningMessage] = field(default_factory=list)
    sent_pairs: Set[tuple] = field(default_factory=set)
    delivered_pairs: Set[tuple] = field(default_factory=set)
    lost_packets: int = 0
    warnings_sent: int = 0
    warnings_delivered: int = 0
    bytes_sent: int = 0
    bytes_delivered: int = 0

    def reset(self) -> None:
        self.pending.clear()
        self.sent_pairs.clear()
        self.delivered_pairs.clear()
        self.lost_packets = 0
        self.warnings_sent = 0
        self.warnings_delivered = 0
        self.bytes_sent = 0
        self.bytes_delivered = 0

    @property
    def total_packet_size_bytes(self) -> int:
        if self.packet_size_bytes > 0:
            return int(self.packet_size_bytes)
        return int(self.header_size_bytes + self.payload_size_bytes)

    @property
    def effective_loss_probability(self) -> float:
        return packet_error_rate(self.total_packet_size_bytes, self.bit_error_rate, self.loss_probability)

    def transmission_delay_s(self) -> float:
        return compute_tx_delay_s(self.total_packet_size_bytes, self.data_rate_bps)

    def one_hop_delay_s(self) -> float:
        if not self.protocol_mode:
            return float(self.delay_s)
        return compute_protocol_delay_s(
            packet_size_bytes=self.total_packet_size_bytes,
            data_rate_bps=self.data_rate_bps,
            base_delay_s=self.base_delay_s,
            processing_delay_s=self.processing_delay_s,
            queue_delay_s=self.queue_delay_s,
        )

    def in_range(self, sender: VehicleState, receiver: VehicleState) -> bool:
        dx = sender.x_m - receiver.x_m
        dy = sender.y_m - receiver.y_m
        return (dx * dx + dy * dy) ** 0.5 <= self.communication_range_m

    def broadcast_to_followers(
        self,
        now_s: float,
        sender: VehicleState,
        vehicles: Iterable[VehicleState],
        origin_id: str,
        created_time_s: float,
        hop: int,
        event_log: EventLog,
    ) -> None:
        if hop > self.max_hops:
            return
        for receiver in vehicles:
            if receiver.vid == sender.vid:
                continue
            # Platoon model: higher index means behind the sender.
            if receiver.index <= sender.index:
                continue
            if not self.in_range(sender, receiver):
                continue
            pair = (origin_id, sender.vid, receiver.vid, hop)
            if pair in self.sent_pairs:
                continue
            self.sent_pairs.add(pair)
            self.warnings_sent += 1
            self.bytes_sent += self.total_packet_size_bytes
            if self.rng.random() < self.effective_loss_probability:
                self.lost_packets += 1
                event_log.add(
                    now_s,
                    "v2v_packet_lost",
                    origin_id=origin_id,
                    sender=sender.vid,
                    receiver=receiver.vid,
                    hop=hop,
                    protocol=self.protocol,
                    packet_size_bytes=self.total_packet_size_bytes,
                    effective_loss_probability=round(self.effective_loss_probability, 8),
                )
                continue
            tx_delay_s = self.transmission_delay_s() if self.protocol_mode else None
            # now_s is already the actual send/rebroadcast time. Add only the
            # current-hop protocol delay plus one local rebroadcast delay for
            # hops after the first. Do not add cumulative delays again here.
            rebroadcast_extra_s = self.rebroadcast_delay_s if hop > 1 else 0.0
            deliver_time_s = now_s + rebroadcast_extra_s + self.one_hop_delay_s()
            msg = WarningMessage(
                msg_id=f"{origin_id}_{sender.vid}_{receiver.vid}_{hop}_{len(self.pending)}",
                origin_id=origin_id,
                sender_id=sender.vid,
                receiver_id=receiver.vid,
                created_time_s=created_time_s,
                send_time_s=now_s,
                deliver_time_s=deliver_time_s,
                hop=hop,
                link_type="V2V",
                protocol=self.protocol,
                packet_size_bytes=self.total_packet_size_bytes,
                data_rate_bps=self.data_rate_bps,
                tx_delay_s=tx_delay_s,
                queue_delay_s=self.queue_delay_s,
                processing_delay_s=self.processing_delay_s,
            )
            self.pending.append(msg)
            event_log.add(
                now_s,
                "v2v_packet_sent",
                origin_id=origin_id,
                sender=sender.vid,
                receiver=receiver.vid,
                hop=hop,
                protocol=self.protocol,
                packet_size_bytes=self.total_packet_size_bytes,
                deliver_time_s=round(deliver_time_s, 4),
                tx_delay_s=round(tx_delay_s or 0.0, 6),
            )

    def deliver_due(self, now_s: float) -> List[WarningMessage]:
        due = [m for m in self.pending if m.deliver_time_s <= now_s + 1e-9]
        self.pending = [m for m in self.pending if m.deliver_time_s > now_s + 1e-9]
        self.warnings_delivered += len(due)
        self.bytes_delivered += sum(int(m.packet_size_bytes) for m in due)
        for m in due:
            self.delivered_pairs.add((m.origin_id, m.receiver_id))
        return due
