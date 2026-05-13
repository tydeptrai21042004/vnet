from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .channel import V2VChannel
from .metrics import ensure_dir, write_events_csv
from .models import CaseMetrics, EventLog, VehicleState
from .sumo_tools import add_sumo_tools_to_path, find_executable


def _euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class SumoTraciRunner:
    """SUMO/TraCI runner for OSM maps.

    This module controls the simulated vehicles in a real SUMO network converted
    from OpenStreetMap. It injects a sudden-braking incident, simulates V2V
    warning packets, and records metrics.
    """

    def __init__(self, global_cfg: Dict, seed: int = 42, gui: bool = False):
        self.global_cfg = global_cfg
        self.rng = random.Random(seed)
        self.gui = gui

    def _select_incident_vehicle(self, traci) -> Optional[str]:
        by_lane: Dict[str, List[Tuple[float, str]]] = {}
        for vid in traci.vehicle.getIDList():
            lane = traci.vehicle.getLaneID(vid)
            if not lane or lane.startswith(":" ):
                continue
            try:
                pos = float(traci.vehicle.getLanePosition(vid))
                speed = float(traci.vehicle.getSpeed(vid))
            except Exception:
                continue
            if speed < 3.0:
                continue
            by_lane.setdefault(lane, []).append((pos, vid))
        candidate_groups = [sorted(v, reverse=True) for v in by_lane.values() if len(v) >= 2]
        if not candidate_groups:
            return None
        # Choose the lane with the most vehicles, then the leading vehicle in that lane.
        candidate_groups.sort(key=len, reverse=True)
        return candidate_groups[0][0][1]

    def _snapshot_vehicles(self, traci) -> Dict[str, VehicleState]:
        ids = list(traci.vehicle.getIDList())
        # Synthetic index is derived from lane position order per lane; lower index means further ahead.
        by_lane: Dict[str, List[Tuple[float, str]]] = {}
        for vid in ids:
            try:
                lane = traci.vehicle.getLaneID(vid)
                pos = float(traci.vehicle.getLanePosition(vid))
                by_lane.setdefault(lane, []).append((pos, vid))
            except Exception:
                continue
        rank: Dict[str, int] = {}
        for lane, entries in by_lane.items():
            for idx, (_, vid) in enumerate(sorted(entries, reverse=True)):
                rank[vid] = idx
        states: Dict[str, VehicleState] = {}
        for vid in ids:
            try:
                xy = traci.vehicle.getPosition(vid)
                lane_rank = rank.get(vid, 9999)
                states[vid] = VehicleState(
                    vid=vid,
                    index=lane_rank,
                    x_m=float(xy[0]),
                    speed_mps=float(traci.vehicle.getSpeed(vid)),
                    accel_mps2=float(traci.vehicle.getAcceleration(vid)),
                )
            except Exception:
                continue
        return states

    def _broadcast_sumo(
        self,
        now_s: float,
        traci,
        channel: V2VChannel,
        sender_id: str,
        origin_id: str,
        created_time_s: float,
        hop: int,
        event_log: EventLog,
        reached: set[str],
    ) -> None:
        if hop > channel.max_hops or sender_id not in traci.vehicle.getIDList():
            return
        sender_pos = traci.vehicle.getPosition(sender_id)
        sender_lane = traci.vehicle.getLaneID(sender_id)
        sender_lane_pos = traci.vehicle.getLanePosition(sender_id)
        sender_state = VehicleState(sender_id, index=0, x_m=float(sender_pos[0]), speed_mps=float(traci.vehicle.getSpeed(sender_id)))
        for rid in traci.vehicle.getIDList():
            if rid == sender_id or rid in reached:
                continue
            try:
                receiver_pos = traci.vehicle.getPosition(rid)
                dist = _euclidean(sender_pos, receiver_pos)
                if dist > channel.communication_range_m:
                    continue
                # Prefer warning following vehicles on the same lane behind sender.
                same_lane = traci.vehicle.getLaneID(rid) == sender_lane
                behind = same_lane and traci.vehicle.getLanePosition(rid) < sender_lane_pos
                if not behind and hop == 1:
                    # For direct warning, avoid sending to vehicles that are not clearly affected.
                    continue
                fake_receiver = VehicleState(rid, index=1, x_m=sender_state.x_m + 1.0, speed_mps=float(traci.vehicle.getSpeed(rid)))
                channel.broadcast_to_followers(now_s, sender_state, [fake_receiver], origin_id, created_time_s, hop, event_log)
            except Exception:
                continue

    def run_case(self, case: Dict, sumocfg: str | Path, channel_cfg: Dict, out_dir: str | Path) -> CaseMetrics:
        add_sumo_tools_to_path()
        try:
            import traci  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Cannot import traci. Install SUMO and set SUMO_HOME, or run demo mode.") from exc

        out_dir = ensure_dir(out_dir)
        event_log = EventLog()
        sumo_binary = find_executable("sumo-gui" if self.gui else "sumo")
        step_length = float(self.global_cfg.get("step_length_s", 0.1))
        duration = float(self.global_cfg.get("duration_s", 90.0))
        seed = int(self.global_cfg.get("seed", 42))
        channel = V2VChannel(
            communication_range_m=float(channel_cfg.get("communication_range_m", 150.0)),
            delay_s=float(channel_cfg.get("delay_s", 0.15)),
            loss_probability=float(channel_cfg.get("loss_probability", 0.0)),
            rebroadcast_delay_s=float(channel_cfg.get("rebroadcast_delay_s", 0.05)),
            max_hops=int(channel_cfg.get("max_hops", 1)),
            rng=self.rng,
        )
        incident_enabled = bool(case.get("incident_enabled", True))
        warning_enabled = bool(case.get("warning_enabled", False))
        multi_hop = bool(case.get("multi_hop", False))
        incident_time = float(case.get("sumo_incident_time_s", 25.0))
        slow_down_duration = float(case.get("sumo_slowdown_duration_s", 2.0))
        warning_speed_factor = float(case.get("sumo_warning_speed_factor", 0.35))

        traci.start([
            sumo_binary,
            "-c", str(sumocfg),
            "--step-length", str(step_length),
            "--seed", str(seed),
            "--collision.action", "warn",
            "--collision.check-junctions", "true",
            "--time-to-teleport", "-1",
        ])

        incident_vehicle: Optional[str] = None
        incident_started = False
        reached: set[str] = set()
        target_receivers: set[str] = set()
        delivered_delays: list[float] = []
        collision_pairs: set[tuple[str, str]] = set()
        trajectory_rows: list[dict] = []

        try:
            steps = int(duration / step_length)
            for step in range(steps + 1):
                traci.simulationStep()
                now = round(step * step_length, 10)

                if incident_enabled and not incident_started and now >= incident_time:
                    incident_vehicle = self._select_incident_vehicle(traci)
                    if incident_vehicle:
                        incident_started = True
                        speed = float(traci.vehicle.getSpeed(incident_vehicle))
                        traci.vehicle.slowDown(incident_vehicle, 0.0, slow_down_duration)
                        event_log.add(now, "incident_started", vehicle=incident_vehicle, speed_mps=speed)
                        if warning_enabled:
                            # All same-lane behind vehicles at incident time are target receivers.
                            lane = traci.vehicle.getLaneID(incident_vehicle)
                            pos = traci.vehicle.getLanePosition(incident_vehicle)
                            for vid in traci.vehicle.getIDList():
                                if vid == incident_vehicle:
                                    continue
                                if traci.vehicle.getLaneID(vid) == lane and traci.vehicle.getLanePosition(vid) < pos:
                                    target_receivers.add(vid)
                            self._broadcast_sumo(now, traci, channel, incident_vehicle, incident_vehicle, now, 1, event_log, reached)
                    else:
                        event_log.add(now, "incident_waiting_for_vehicle")

                for msg in channel.deliver_due(now):
                    if msg.receiver_id not in traci.vehicle.getIDList():
                        continue
                    if msg.receiver_id not in reached:
                        reached.add(msg.receiver_id)
                        delay = now - msg.created_time_s
                        delivered_delays.append(delay)
                        current_speed = float(traci.vehicle.getSpeed(msg.receiver_id))
                        traci.vehicle.slowDown(msg.receiver_id, max(0.0, current_speed * warning_speed_factor), slow_down_duration)
                        event_log.add(now, "warning_received", receiver=msg.receiver_id, sender=msg.sender_id, origin_id=msg.origin_id, delay_s=round(delay, 4), hop=msg.hop)
                        if multi_hop and msg.hop < channel.max_hops:
                            self._broadcast_sumo(now, traci, channel, msg.receiver_id, msg.origin_id, msg.created_time_s, msg.hop + 1, event_log, reached)

                try:
                    colliding = list(traci.simulation.getCollidingVehiclesIDList())
                    for i in range(0, len(colliding), 2):
                        a = colliding[i]
                        b = colliding[i + 1] if i + 1 < len(colliding) else "unknown"
                        pair = tuple(sorted((a, b)))
                        if pair not in collision_pairs:
                            collision_pairs.add(pair)
                            event_log.add(now, "collision", vehicle_a=a, vehicle_b=b)
                except Exception:
                    pass

                for vid in traci.vehicle.getIDList():
                    try:
                        x, y = traci.vehicle.getPosition(vid)
                        trajectory_rows.append({
                            "time_s": now,
                            "vehicle_id": vid,
                            "x_m": float(x),
                            "y_m": float(y),
                            "speed_mps": float(traci.vehicle.getSpeed(vid)),
                            "lane_id": traci.vehicle.getLaneID(vid),
                            "edge_id": traci.vehicle.getRoadID(vid),
                            "warning_received": vid in reached,
                        })
                    except Exception:
                        continue
        finally:
            traci.close(False)

        pd.DataFrame(trajectory_rows).to_csv(out_dir / f"trajectories_{case['id']}.csv", index=False)
        write_events_csv(event_log, out_dir / f"events_{case['id']}.csv")
        avg_delay = sum(delivered_delays) / len(delivered_delays) if delivered_delays else None
        pdr = len(reached) / len(target_receivers) if target_receivers else None
        metrics = CaseMetrics(
            case_id=case["id"],
            case_name=case.get("name", case["id"]),
            collisions=len(collision_pairs),
            unique_warning_receivers=len(reached),
            target_receivers=len(target_receivers),
            warnings_sent=channel.warnings_sent,
            warnings_delivered=channel.warnings_delivered,
            lost_packets=channel.lost_packets,
            min_gap_m=float("nan"),
            first_warning_time_s=None,
            avg_delay_s=avg_delay,
            pdr=pdr,
            reaction_gain_s=None,
        )
        return metrics
