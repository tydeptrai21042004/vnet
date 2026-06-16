from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .channel import V2VChannel
from .collision_warning import compute_ttc
from .metrics import ensure_dir, write_events_csv
from .models import CaseMetrics, EventLog, VehicleState, WarningMessage
from .v2i_channel import RSU, V2IChannel


class SyntheticPlatoonRunner:
    """Pure-Python platoon simulator used for quick testing without SUMO.

    The simulator now supports four communication modes:
    no warning, V2V, V2I, and hybrid V2V+V2I.  It also supports an abstract
    protocol/packet-size model so packet size affects transmission delay,
    overhead, packet PDR, and channel load.
    """

    def __init__(self, global_cfg: Dict, seed: int = 42):
        self.global_cfg = global_cfg
        self.seed = seed
        self.rng = random.Random(seed)

    def _make_vehicles(self, sim_cfg: Dict) -> List[VehicleState]:
        n = int(sim_cfg.get("num_vehicles", 10))
        gap = float(sim_cfg.get("gap_m", 18.0))
        v0 = float(sim_cfg.get("initial_speed_mps", 22.0))
        vehicle_length = float(self.global_cfg.get("vehicle_length_m", 4.5))
        spacing = gap + vehicle_length  # gap_m is bumper-to-bumper clearance
        return [VehicleState(vid=f"veh_{i:02d}", index=i, x_m=-i * spacing, y_m=0.0, speed_mps=v0) for i in range(n)]

    def _build_v2v_channel(self, channel_cfg: Dict) -> V2VChannel:
        packet_size = int(channel_cfg.get("packet_size_bytes", int(channel_cfg.get("header_size_bytes", 48)) + int(channel_cfg.get("payload_size_bytes", 252))))
        return V2VChannel(
            communication_range_m=float(channel_cfg.get("communication_range_m", 150.0)),
            delay_s=float(channel_cfg.get("delay_s", channel_cfg.get("base_delay_s", 0.15))),
            loss_probability=float(channel_cfg.get("loss_probability", 0.0)),
            bit_error_rate=float(channel_cfg.get("bit_error_rate", 0.0)),
            rebroadcast_delay_s=float(channel_cfg.get("rebroadcast_delay_s", 0.05)),
            max_hops=int(channel_cfg.get("max_hops", 1)),
            rng=self.rng,
            protocol=str(channel_cfg.get("protocol", "DSRC_80211p")),
            packet_size_bytes=packet_size,
            header_size_bytes=int(channel_cfg.get("header_size_bytes", 48)),
            payload_size_bytes=int(channel_cfg.get("payload_size_bytes", max(0, packet_size - int(channel_cfg.get("header_size_bytes", 48))))),
            data_rate_bps=float(channel_cfg.get("data_rate_bps", 6_000_000.0)),
            base_delay_s=float(channel_cfg.get("base_delay_s", channel_cfg.get("delay_s", 0.02))),
            processing_delay_s=float(channel_cfg.get("processing_delay_s", 0.005)),
            queue_delay_s=float(channel_cfg.get("queue_delay_s", 0.0)),
            protocol_mode=bool(channel_cfg.get("protocol_mode", True)),
        )

    def _build_rsus(self, rsus_cfg: List[Dict], v2i_cfg: Dict, vehicles: List[VehicleState], sim_cfg: Optional[Dict] = None) -> List[RSU]:
        rsu_range = float(v2i_cfg.get("rsu_range_m", v2i_cfg.get("range_m", 500.0)))
        if rsus_cfg:
            return [
                RSU(
                    rsu_id=str(r.get("id", r.get("rsu_id", f"RSU_{idx}"))),
                    x_m=float(r.get("x_m", r.get("x", 0.0))),
                    y_m=float(r.get("y_m", r.get("y", 0.0))),
                    range_m=float(r.get("range_m", r.get("range", rsu_range))),
                )
                for idx, r in enumerate(rsus_cfg)
            ]
        # Auto RSUs for synthetic mode: place one near the expected incident point
        # and one near the middle of the initial platoon. This keeps V2I active in
        # demo mode without requiring the user to manually tune coordinates.
        sim_cfg = sim_cfg or {}
        incident_idx = int(sim_cfg.get("incident_vehicle_index", 0))
        incident_time = float(sim_cfg.get("incident_time_s", 20.0))
        v0 = float(sim_cfg.get("initial_speed_mps", vehicles[incident_idx].speed_mps if vehicles else 0.0))
        expected_incident_x = vehicles[incident_idx].x_m + v0 * incident_time if vehicles else 0.0
        mid_initial_x = sum(v.x_m for v in vehicles) / max(1, len(vehicles))
        return [
            RSU("RSU_AUTO_INCIDENT", x_m=expected_incident_x - 0.25 * rsu_range, y_m=0.0, range_m=rsu_range),
            RSU("RSU_AUTO_PLATOON", x_m=mid_initial_x, y_m=0.0, range_m=rsu_range),
        ]

    def _build_v2i_channel(self, v2i_cfg: Dict, rsus: List[RSU]) -> V2IChannel:
        packet_size = int(v2i_cfg.get("packet_size_bytes", int(v2i_cfg.get("header_size_bytes", 64)) + int(v2i_cfg.get("payload_size_bytes", 236))))
        base_delay = float(v2i_cfg.get("base_delay_s", 0.03))
        return V2IChannel(
            rsus=rsus,
            protocol=str(v2i_cfg.get("protocol", "V2I_LTE_5G")),
            packet_size_bytes=packet_size,
            header_size_bytes=int(v2i_cfg.get("header_size_bytes", 64)),
            payload_size_bytes=int(v2i_cfg.get("payload_size_bytes", max(0, packet_size - int(v2i_cfg.get("header_size_bytes", 64))))),
            data_rate_bps=float(v2i_cfg.get("data_rate_bps", 20_000_000.0)),
            uplink_base_delay_s=float(v2i_cfg.get("uplink_base_delay_s", base_delay)),
            downlink_base_delay_s=float(v2i_cfg.get("downlink_base_delay_s", base_delay)),
            processing_delay_s=float(v2i_cfg.get("processing_delay_s", 0.02)),
            queue_delay_s=float(v2i_cfg.get("queue_delay_s", 0.0)),
            loss_probability=float(v2i_cfg.get("loss_probability", 0.02)),
            bit_error_rate=float(v2i_cfg.get("bit_error_rate", 0.0)),
            downlink_accounting=str(v2i_cfg.get("downlink_accounting", "broadcast")),
            rng=self.rng,
        )

    @staticmethod
    def _communication_mode(case: Dict) -> str:
        if not bool(case.get("warning_enabled", False)):
            return "none"
        return str(case.get("communication_mode", "v2v")).lower()

    @staticmethod
    def _deliver_warning_to_vehicle(
        now: float,
        msg: WarningMessage,
        receiver: VehicleState,
        delays: list[float],
        event_log: EventLog,
    ) -> bool:
        if receiver.warning_received_time is not None:
            event_log.add(
                now,
                "duplicate_warning_ignored",
                receiver=receiver.vid,
                sender=msg.sender_id,
                link_type=msg.link_type,
                protocol=msg.protocol,
            )
            return False
        receiver.warning_received_time = now
        receiver.warning_hop = msg.hop
        receiver.warning_link_type = msg.link_type
        scheduled_delay = msg.deliver_time_s - msg.created_time_s
        delays.append(scheduled_delay)
        event_log.add(
            now,
            "warning_received",
            receiver=receiver.vid,
            sender=msg.sender_id,
            origin_id=msg.origin_id,
            delay_s=round(scheduled_delay, 6),
            hop=msg.hop,
            link_type=msg.link_type,
            protocol=msg.protocol,
            packet_size_bytes=msg.packet_size_bytes,
        )
        return True

    def _warning_deceleration(
        self,
        control_algorithm: str,
        rear: VehicleState,
        front: VehicleState,
        gap: float,
        ttc: float,
        dt: float,
        normal_decel: float,
        warning_decel: float,
        emergency_decel: float,
        min_warn_speed: float,
        visual_gap: float,
    ) -> float:
        alg = control_algorithm.lower()
        safe_ttc = float(self.global_cfg.get("safe_ttc_s", 3.0))
        if alg in {"emergency_brake", "hard_brake"}:
            return -emergency_decel
        if alg in {"ttc_adaptive", "adaptive_ttc", "gap_control"}:
            # A lightweight CACC-like control rule: after receiving warning, compute a
            # target speed that keeps the rear vehicle closer to the front vehicle speed
            # when TTC/gap is unsafe.  Stronger braking is used only when necessary.
            if ttc < safe_ttc or gap < max(visual_gap, rear.speed_mps * 0.8):
                safe_extra_gap = max(0.0, gap - visual_gap)
                target_speed = min(rear.speed_mps, front.speed_mps + safe_extra_gap / max(safe_ttc, 0.1))
                target_speed = max(min_warn_speed, target_speed)
                needed_decel = max(normal_decel, (rear.speed_mps - target_speed) / max(dt * 4.0, 0.1))
                return -min(emergency_decel, max(warning_decel, needed_decel))
            return -min(warning_decel, max(normal_decel, warning_decel * 0.5))
        # Default: pre-emptive VANET braking.
        return -warning_decel

    def run_case(
        self,
        case: Dict,
        sim_cfg: Dict,
        channel_cfg: Dict,
        out_dir: str | Path,
        v2i_cfg: Optional[Dict] = None,
        rsus_cfg: Optional[List[Dict]] = None,
    ) -> CaseMetrics:
        out_dir = ensure_dir(out_dir)
        event_log = EventLog()
        vehicles = self._make_vehicles(sim_cfg)
        channel = self._build_v2v_channel(channel_cfg)
        rsus = self._build_rsus(rsus_cfg or [], v2i_cfg or {}, vehicles, sim_cfg=sim_cfg)
        v2i = self._build_v2i_channel(v2i_cfg or {}, rsus)

        dt = float(self.global_cfg.get("step_length_s", 0.1))
        duration = float(self.global_cfg.get("duration_s", 90.0))
        vehicle_length = float(self.global_cfg.get("vehicle_length_m", 4.5))
        collision_gap = float(self.global_cfg.get("collision_gap_m", 0.7))
        reaction_time = float(self.global_cfg.get("driver_reaction_time_s", 1.0))
        visual_ttc = float(self.global_cfg.get("visual_detection_ttc_s", 1.2))
        visual_gap = float(self.global_cfg.get("visual_detection_gap_m", 12.0))

        incident_enabled = bool(case.get("incident_enabled", True))
        warning_enabled = bool(case.get("warning_enabled", False))
        multi_hop = bool(case.get("multi_hop", False))
        communication_mode = self._communication_mode(case)
        control_algorithm = str(case.get("control_algorithm", "preemptive_brake" if warning_enabled else "none"))
        incident_time = float(sim_cfg.get("incident_time_s", 20.0))
        incident_idx = int(sim_cfg.get("incident_vehicle_index", 0))
        emergency_decel = float(sim_cfg.get("emergency_decel_mps2", 8.0))
        normal_decel = float(sim_cfg.get("normal_decel_mps2", 3.5))
        warning_decel = float(sim_cfg.get("warning_decel_mps2", 6.0))
        min_warn_speed = float(sim_cfg.get("min_speed_after_warning_mps", 4.0))

        incident_started = False
        trajectories: list[dict] = []
        delays: list[float] = []
        collision_pairs = set()
        target_radius = float(sim_cfg.get("target_radius_m", self.global_cfg.get("target_receiver_radius_m", 600.0)))
        incident_vehicle = vehicles[incident_idx]
        target_ids = {v.vid for v in vehicles if v.index > incident_idx and (incident_vehicle.x_m - v.x_m) <= target_radius}
        target_receivers = len(target_ids) if incident_enabled else 0
        baseline_visual_first_detection: Optional[float] = None

        n_steps = int(duration / dt)
        for step in range(n_steps + 1):
            now = round(step * dt, 10)

            # 1) Trigger sudden braking of the front vehicle.
            if incident_enabled and not incident_started and now >= incident_time:
                incident_started = True
                leader = vehicles[incident_idx]
                event_log.add(
                    now,
                    "incident_started",
                    vehicle=leader.vid,
                    speed_mps=round(leader.speed_mps, 4),
                    communication_mode=communication_mode,
                    control_algorithm=control_algorithm,
                    edge_id="synthetic_platoon",
                    lane_id="synthetic_lane_0",
                    lane_position_m=round(leader.x_m, 4),
                    x_m=round(leader.x_m, 4),
                    y_m=round(leader.y_m, 4),
                    fixed_incident=True,
                )
                if warning_enabled:
                    if communication_mode in {"v2v", "hybrid"}:
                        channel.broadcast_to_followers(
                            now_s=now,
                            sender=leader,
                            vehicles=vehicles,
                            origin_id=leader.vid,
                            created_time_s=now,
                            hop=1,
                            event_log=event_log,
                        )
                    if communication_mode in {"v2i", "hybrid"}:
                        v2i.broadcast_warning(
                            now_s=now,
                            origin_vehicle=leader,
                            vehicles=vehicles,
                            created_time_s=now,
                            event_log=event_log,
                            target_followers_only=True,
                        )

            # 2) Deliver V2V warning messages.
            for msg in channel.deliver_due(now):
                receiver = next((v for v in vehicles if v.vid == msg.receiver_id), None)
                if receiver is None:
                    continue
                accepted = self._deliver_warning_to_vehicle(now, msg, receiver, delays, event_log)
                if accepted and multi_hop and msg.hop < channel.max_hops:
                    channel.broadcast_to_followers(
                        now_s=now,
                        sender=receiver,
                        vehicles=vehicles,
                        origin_id=msg.origin_id,
                        created_time_s=msg.created_time_s,
                        hop=msg.hop + 1,
                        event_log=event_log,
                    )

            # 3) Deliver V2I warning messages.
            for msg in v2i.deliver_due(now):
                receiver = next((v for v in vehicles if v.vid == msg.receiver_id), None)
                if receiver is None:
                    continue
                accepted = self._deliver_warning_to_vehicle(now, msg, receiver, delays, event_log)
                # Optional hybrid rebroadcast: infrastructure warning can seed V2V dissemination.
                if accepted and communication_mode == "hybrid" and bool(case.get("hybrid_rebroadcast_from_v2i", False)):
                    channel.broadcast_to_followers(
                        now_s=now,
                        sender=receiver,
                        vehicles=vehicles,
                        origin_id=msg.origin_id,
                        created_time_s=msg.created_time_s,
                        hop=1,
                        event_log=event_log,
                    )

            # 4) Driver and vehicle control.
            accelerations = [0.0 for _ in vehicles]
            if incident_started:
                leader = vehicles[incident_idx]
                if leader.speed_mps > 0.05:
                    accelerations[incident_idx] = -emergency_decel

            for i in range(1, len(vehicles)):
                front = vehicles[i - 1]
                rear = vehicles[i]
                gap = front.x_m - rear.x_m - vehicle_length
                ttc = compute_ttc(gap, rear.speed_mps, front.speed_mps)

                if incident_started and baseline_visual_first_detection is None and (ttc <= visual_ttc or gap <= visual_gap):
                    baseline_visual_first_detection = now

                if rear.warning_received_time is not None:
                    if rear.speed_mps > min_warn_speed:
                        decel = self._warning_deceleration(
                            control_algorithm=control_algorithm,
                            rear=rear,
                            front=front,
                            gap=gap,
                            ttc=ttc,
                            dt=dt,
                            normal_decel=normal_decel,
                            warning_decel=warning_decel,
                            emergency_decel=emergency_decel,
                            min_warn_speed=min_warn_speed,
                            visual_gap=visual_gap,
                        )
                        accelerations[i] = min(accelerations[i], decel)
                else:
                    if rear.visual_detection_time is None and (ttc <= visual_ttc or gap <= visual_gap):
                        rear.visual_detection_time = now
                        event_log.add(now, "visual_danger_detected", vehicle=rear.vid, gap_m=round(gap, 3), ttc_s=round(ttc, 3))
                    if rear.visual_detection_time is not None and now - rear.visual_detection_time >= reaction_time:
                        accelerations[i] = min(accelerations[i], -normal_decel)

                if gap < vehicle_length:
                    accelerations[i] = min(accelerations[i], -emergency_decel)

            # 5) Integrate motion.
            for i, veh in enumerate(vehicles):
                veh.accel_mps2 = accelerations[i]
                veh.speed_mps = max(0.0, veh.speed_mps + veh.accel_mps2 * dt)
                veh.x_m += veh.speed_mps * dt

            # 6) Detect collisions.
            for i in range(1, len(vehicles)):
                front = vehicles[i - 1]
                rear = vehicles[i]
                gap = front.x_m - rear.x_m - vehicle_length
                pair = (front.vid, rear.vid)
                if gap <= collision_gap:
                    if pair not in collision_pairs:
                        collision_pairs.add(pair)
                        event_log.add(now, "collision", front=front.vid, rear=rear.vid, gap_m=round(gap, 4))
                    front.collided = True
                    rear.collided = True
                    # Contact constraint: prevent vehicles from numerically passing
                    # through one another after impact. The rear vehicle follows the
                    # front vehicle at zero clearance and cannot be faster.
                    rear.x_m = min(rear.x_m, front.x_m - vehicle_length)
                    rear.speed_mps = min(rear.speed_mps, front.speed_mps)
                    rear.accel_mps2 = min(rear.accel_mps2, front.accel_mps2)

            # 7) Record trajectory rows.
            for veh in vehicles:
                trajectories.append(
                    {
                        "time_s": now,
                        "vehicle_id": veh.vid,
                        "vehicle_index": veh.index,
                        "x_m": veh.x_m,
                        "y_m": veh.y_m,
                        "speed_mps": veh.speed_mps,
                        "accel_mps2": veh.accel_mps2,
                        "warning_received": veh.warning_received_time is not None,
                        "warning_received_time_s": veh.warning_received_time,
                        "warning_hop": veh.warning_hop,
                        "warning_link_type": veh.warning_link_type,
                        "collided": veh.collided,
                    }
                )

        warned_ids = {v.vid for v in vehicles if v.warning_received_time is not None}
        unique_receivers = len(warned_ids.intersection(target_ids))
        first_warning = min([v.warning_received_time for v in vehicles if v.warning_received_time is not None], default=None)
        avg_delay = sum(delays) / len(delays) if delays else None
        max_delay = max(delays) if delays else None
        receiver_coverage = unique_receivers / target_receivers if target_receivers else None

        total_warnings_sent = channel.warnings_sent + v2i.warnings_sent
        total_warnings_delivered = channel.warnings_delivered + v2i.warnings_delivered
        total_lost_packets = channel.lost_packets + v2i.lost_packets
        total_bytes_sent = channel.bytes_sent + v2i.bytes_sent
        total_bytes_delivered = channel.bytes_delivered + v2i.bytes_delivered
        packet_pdr = total_warnings_delivered / total_warnings_sent if total_warnings_sent else None

        reaction_gain = None
        if first_warning is not None and baseline_visual_first_detection is not None:
            reaction_gain = baseline_visual_first_detection - first_warning

        df_traj = pd.DataFrame(trajectories)
        df_traj.to_csv(out_dir / f"trajectories_{case['id']}.csv", index=False)
        write_events_csv(event_log, out_dir / f"events_{case['id']}.csv")

        # Compute true minimum gap from original order over trajectories.
        pivot_x = df_traj.pivot(index="time_s", columns="vehicle_index", values="x_m")
        min_gap = 1e9
        for i in range(1, len(vehicles)):
            gap_series = pivot_x[i - 1] - pivot_x[i] - vehicle_length
            min_gap = min(min_gap, max(0.0, float(gap_series.min())))

        # Load approximation: used capacity fraction during the entire simulated time.
        v2v_load = (channel.bytes_sent * 8.0) / max(duration * channel.data_rate_bps, 1.0)
        v2i_load = (v2i.bytes_sent * 8.0) / max(duration * v2i.data_rate_bps, 1.0)
        normalized_offered_load = v2v_load + v2i_load if total_bytes_sent else None
        duplicate_deliveries = max(0, total_warnings_delivered - unique_receivers)
        useful_delivery_ratio = unique_receivers / total_warnings_delivered if total_warnings_delivered else None
        protocol = channel.protocol if communication_mode == "v2v" else v2i.protocol if communication_mode == "v2i" else f"{channel.protocol}+{v2i.protocol}" if communication_mode == "hybrid" else "NONE"
        packet_size_bytes = channel.total_packet_size_bytes if communication_mode == "v2v" else v2i.total_packet_size_bytes if communication_mode == "v2i" else max(channel.total_packet_size_bytes, v2i.total_packet_size_bytes) if communication_mode == "hybrid" else None
        data_rate_bps = channel.data_rate_bps if communication_mode == "v2v" else v2i.data_rate_bps if communication_mode == "v2i" else min(channel.data_rate_bps, v2i.data_rate_bps) if communication_mode == "hybrid" else None

        incident_expected = bool(case.get("incident_enabled", True))
        incident_vehicle = vehicles[incident_idx].vid if incident_started and incident_enabled else None
        incident_x = vehicles[incident_idx].x_m if incident_started and incident_enabled else None
        incident_y = vehicles[incident_idx].y_m if incident_started and incident_enabled else None
        result_status = "OK" if (not incident_expected or incident_started) else "ERROR_NO_INCIDENT"

        return CaseMetrics(
            case_id=case["id"],
            case_name=case.get("name", case["id"]),
            communication_mode=communication_mode,
            protocol=protocol,
            packet_size_bytes=packet_size_bytes,
            control_algorithm=control_algorithm,
            collisions=len(collision_pairs),
            unique_warning_receivers=unique_receivers,
            target_receivers=target_receivers,
            warnings_sent=total_warnings_sent,
            warnings_delivered=total_warnings_delivered,
            lost_packets=total_lost_packets,
            min_gap_m=min_gap,
            first_warning_time_s=first_warning,
            avg_delay_s=avg_delay,
            max_delay_s=max_delay,
            packet_pdr=packet_pdr,
            receiver_coverage=receiver_coverage,
            pdr=packet_pdr,
            reaction_gain_s=reaction_gain,
            warning_lead_time_vs_visual_detection_s=reaction_gain,
            bytes_sent=total_bytes_sent,
            bytes_delivered=total_bytes_delivered,
            channel_load=normalized_offered_load,
            normalized_offered_load=normalized_offered_load,
            duplicate_deliveries=duplicate_deliveries,
            useful_delivery_ratio=useful_delivery_ratio,
            unique_colliding_pairs=len(collision_pairs),
            data_rate_bps=data_rate_bps,
            v2v_warnings_sent=channel.warnings_sent,
            v2v_warnings_delivered=channel.warnings_delivered,
            v2v_lost_packets=channel.lost_packets,
            v2v_bytes_sent=channel.bytes_sent,
            v2i_warnings_sent=v2i.warnings_sent,
            v2i_warnings_delivered=v2i.warnings_delivered,
            v2i_lost_packets=v2i.lost_packets,
            v2i_bytes_sent=v2i.bytes_sent,
            rsu_count=len(rsus) if communication_mode in {"v2i", "hybrid"} else 0,
            incident_expected=incident_expected,
            incident_started=incident_started,
            incident_vehicle=incident_vehicle,
            incident_time_s=incident_time if incident_started and incident_enabled else None,
            incident_edge_id="synthetic_platoon" if incident_started and incident_enabled else None,
            incident_lane_id="synthetic_lane_0" if incident_started and incident_enabled else None,
            incident_lane_position_m=incident_x,
            incident_x_m=incident_x,
            incident_y_m=incident_y,
            result_status=result_status,
        )
