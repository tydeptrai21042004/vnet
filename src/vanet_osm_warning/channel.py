from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable, List, Set

from .models import VehicleState, WarningMessage, EventLog


@dataclass
class V2VChannel:
    communication_range_m: float = 150.0
    delay_s: float = 0.15
    loss_probability: float = 0.0
    rebroadcast_delay_s: float = 0.05
    max_hops: int = 1
    rng: random.Random = field(default_factory=random.Random)

    pending: List[WarningMessage] = field(default_factory=list)
    sent_pairs: Set[tuple] = field(default_factory=set)
    delivered_pairs: Set[tuple] = field(default_factory=set)
    lost_packets: int = 0
    warnings_sent: int = 0
    warnings_delivered: int = 0

    def reset(self) -> None:
        self.pending.clear()
        self.sent_pairs.clear()
        self.delivered_pairs.clear()
        self.lost_packets = 0
        self.warnings_sent = 0
        self.warnings_delivered = 0

    def in_range(self, sender: VehicleState, receiver: VehicleState) -> bool:
        return abs(sender.x_m - receiver.x_m) <= self.communication_range_m

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
            if self.rng.random() < self.loss_probability:
                self.lost_packets += 1
                event_log.add(now_s, "packet_lost", origin_id=origin_id, sender=sender.vid, receiver=receiver.vid, hop=hop)
                continue
            msg = WarningMessage(
                msg_id=f"{origin_id}_{sender.vid}_{receiver.vid}_{hop}_{len(self.pending)}",
                origin_id=origin_id,
                sender_id=sender.vid,
                receiver_id=receiver.vid,
                created_time_s=created_time_s,
                send_time_s=now_s,
                deliver_time_s=now_s + self.delay_s + (hop - 1) * self.rebroadcast_delay_s,
                hop=hop,
            )
            self.pending.append(msg)
            event_log.add(now_s, "packet_sent", origin_id=origin_id, sender=sender.vid, receiver=receiver.vid, hop=hop)

    def deliver_due(self, now_s: float) -> List[WarningMessage]:
        due = [m for m in self.pending if m.deliver_time_s <= now_s + 1e-9]
        self.pending = [m for m in self.pending if m.deliver_time_s > now_s + 1e-9]
        self.warnings_delivered += len(due)
        for m in due:
            self.delivered_pairs.add((m.origin_id, m.receiver_id))
        return due
