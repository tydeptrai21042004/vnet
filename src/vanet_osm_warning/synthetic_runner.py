from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .channel import V2VChannel
from .collision_warning import compute_ttc
from .metrics import ensure_dir, write_events_csv
from .models import CaseMetrics, EventLog, VehicleState


class SyntheticPlatoonRunner:
    """Pure-Python platoon simulator used for quick testing without SUMO.

    This is not a replacement for SUMO. It is a deterministic fallback that lets
    students test the VANET warning logic, metrics, and plots on any Ubuntu VM.
    The SUMO/OpenStreetMap pipeline uses the same case configuration.
    """

    def __init__(self, global_cfg: Dict, seed: int = 42):
        self.global_cfg = global_cfg
        self.rng = random.Random(seed)

    def _make_vehicles(self, sim_cfg: Dict) -> List[VehicleState]:
        n = int(sim_cfg.get("num_vehicles", 10))
        gap = float(sim_cfg.get("gap_m", 18.0))
        v0 = float(sim_cfg.get("initial_speed_mps", 22.0))
        return [VehicleState(vid=f"veh_{i:02d}", index=i, x_m=-i * gap, speed_mps=v0) for i in range(n)]

    def run_case(self, case: Dict, sim_cfg: Dict, channel_cfg: Dict, out_dir: str | Path) -> CaseMetrics:
        out_dir = ensure_dir(out_dir)
        event_log = EventLog()
        vehicles = self._make_vehicles(sim_cfg)
        channel = V2VChannel(
            communication_range_m=float(channel_cfg.get("communication_range_m", 150.0)),
            delay_s=float(channel_cfg.get("delay_s", 0.15)),
            loss_probability=float(channel_cfg.get("loss_probability", 0.0)),
            rebroadcast_delay_s=float(channel_cfg.get("rebroadcast_delay_s", 0.05)),
            max_hops=int(channel_cfg.get("max_hops", 1)),
            rng=self.rng,
        )
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
        target_receivers = max(0, len(vehicles) - 1) if incident_enabled else 0

        baseline_visual_first_detection: Optional[float] = None

        n_steps = int(duration / dt)
        for step in range(n_steps + 1):
            now = round(step * dt, 10)

            # 1) Trigger sudden braking of the front vehicle.
            if incident_enabled and not incident_started and now >= incident_time:
                incident_started = True
                leader = vehicles[incident_idx]
                event_log.add(now, "incident_started", vehicle=leader.vid, speed_mps=leader.speed_mps)
                if warning_enabled:
                    channel.broadcast_to_followers(
                        now_s=now,
                        sender=leader,
                        vehicles=vehicles,
                        origin_id=leader.vid,
                        created_time_s=now,
                        hop=1,
                        event_log=event_log,
                    )

            # 2) Deliver V2V warning messages.
            for msg in channel.deliver_due(now):
                receiver = next((v for v in vehicles if v.vid == msg.receiver_id), None)
                sender = next((v for v in vehicles if v.vid == msg.sender_id), None)
                if receiver is None:
                    continue
                if receiver.warning_received_time is None:
                    receiver.warning_received_time = now
                    receiver.warning_hop = msg.hop
                    delays.append(now - msg.created_time_s)
                    event_log.add(
                        now,
                        "warning_received",
                        receiver=receiver.vid,
                        sender=msg.sender_id,
                        origin_id=msg.origin_id,
                        delay_s=round(now - msg.created_time_s, 4),
                        hop=msg.hop,
                    )
                    if multi_hop and msg.hop < channel.max_hops and sender is not None:
                        channel.broadcast_to_followers(
                            now_s=now,
                            sender=receiver,
                            vehicles=vehicles,
                            origin_id=msg.origin_id,
                            created_time_s=msg.created_time_s,
                            hop=msg.hop + 1,
                            event_log=event_log,
                        )

            # 3) Driver and vehicle control.
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
                    # VANET reaction: brake early after receiving warning.
                    if rear.speed_mps > min_warn_speed:
                        accelerations[i] = min(accelerations[i], -warning_decel)
                else:
                    # No VANET reaction: only visual/local perception after a reaction time.
                    if rear.visual_detection_time is None and (ttc <= visual_ttc or gap <= visual_gap):
                        rear.visual_detection_time = now
                        event_log.add(now, "visual_danger_detected", vehicle=rear.vid, gap_m=round(gap, 3), ttc_s=round(ttc, 3))
                    if rear.visual_detection_time is not None and now - rear.visual_detection_time >= reaction_time:
                        accelerations[i] = min(accelerations[i], -normal_decel)

                # Hard safety fallback to reduce unrealistic interpenetration after a collision.
                if gap < vehicle_length:
                    accelerations[i] = min(accelerations[i], -emergency_decel)

            # 4) Integrate motion.
            for i, veh in enumerate(vehicles):
                veh.accel_mps2 = accelerations[i]
                veh.speed_mps = max(0.0, veh.speed_mps + veh.accel_mps2 * dt)
                veh.x_m += veh.speed_mps * dt

            # 5) Detect collisions and minimum gap.
            min_gap_this_step = 1e9
            for i in range(1, len(vehicles)):
                front = vehicles[i - 1]
                rear = vehicles[i]
                gap = front.x_m - rear.x_m - vehicle_length
                min_gap_this_step = min(min_gap_this_step, gap)
                pair = (front.vid, rear.vid)
                if gap <= collision_gap and pair not in collision_pairs:
                    collision_pairs.add(pair)
                    front.collided = True
                    rear.collided = True
                    event_log.add(now, "collision", front=front.vid, rear=rear.vid, gap_m=round(gap, 4))
            # Vehicle order may break after a collision, but for metrics we keep the original platoon order.

            # 6) Record trajectory rows.
            for veh in vehicles:
                trajectories.append(
                    {
                        "time_s": now,
                        "vehicle_id": veh.vid,
                        "vehicle_index": veh.index,
                        "x_m": veh.x_m,
                        "speed_mps": veh.speed_mps,
                        "accel_mps2": veh.accel_mps2,
                        "warning_received": veh.warning_received_time is not None,
                        "warning_received_time_s": veh.warning_received_time,
                        "warning_hop": veh.warning_hop,
                        "collided": veh.collided,
                    }
                )

        unique_receivers = len({v.vid for v in vehicles if v.warning_received_time is not None})
        first_warning = min([v.warning_received_time for v in vehicles if v.warning_received_time is not None], default=None)
        avg_delay = sum(delays) / len(delays) if delays else None
        pdr = unique_receivers / target_receivers if target_receivers else None
        reaction_gain = None
        if first_warning is not None and baseline_visual_first_detection is not None:
            reaction_gain = baseline_visual_first_detection - first_warning

        df_traj = pd.DataFrame(trajectories)
        traj_path = out_dir / f"trajectories_{case['id']}.csv"
        df_traj.to_csv(traj_path, index=False)
        write_events_csv(event_log, out_dir / f"events_{case['id']}.csv")

        metrics = CaseMetrics(
            case_id=case["id"],
            case_name=case.get("name", case["id"]),
            collisions=len(collision_pairs),
            unique_warning_receivers=unique_receivers,
            target_receivers=target_receivers,
            warnings_sent=channel.warnings_sent,
            warnings_delivered=channel.warnings_delivered,
            lost_packets=channel.lost_packets,
            min_gap_m=float(df_traj.groupby("time_s").apply(lambda g: 0).shape[0]) if False else float("nan"),
            first_warning_time_s=first_warning,
            avg_delay_s=avg_delay,
            pdr=pdr,
            reaction_gain_s=reaction_gain,
        )
        # Compute true minimum gap from original order over trajectories.
        pivot_x = df_traj.pivot(index="time_s", columns="vehicle_index", values="x_m")
        min_gap = 1e9
        for i in range(1, len(vehicles)):
            gap_series = pivot_x[i - 1] - pivot_x[i] - vehicle_length
            min_gap = min(min_gap, float(gap_series.min()))
        metrics.min_gap_m = min_gap
        return metrics
