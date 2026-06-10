from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .channel import V2VChannel
from .metrics import ensure_dir, write_events_csv
from .models import CaseMetrics, EventLog, VehicleState, WarningMessage
from .sumo_tools import add_sumo_tools_to_path, find_executable
from .v2i_channel import RSU, V2IChannel


def _euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class SumoTraciRunner:
    """SUMO/TraCI runner for OSM maps.

    The runner injects a sudden-braking incident, simulates V2V, V2I, or hybrid
    warning dissemination, applies a warning-based control algorithm through
    TraCI, and records safety/network metrics.
    """

    def __init__(self, global_cfg: Dict, seed: int = 42, gui: bool = False):
        self.global_cfg = global_cfg
        self.rng = random.Random(seed)
        self.gui = gui

    def _build_v2v_channel(self, channel_cfg: Dict) -> V2VChannel:
        packet_size = int(channel_cfg.get("packet_size_bytes", int(channel_cfg.get("header_size_bytes", 48)) + int(channel_cfg.get("payload_size_bytes", 252))))
        return V2VChannel(
            communication_range_m=float(channel_cfg.get("communication_range_m", 150.0)),
            delay_s=float(channel_cfg.get("delay_s", channel_cfg.get("base_delay_s", 0.15))),
            loss_probability=float(channel_cfg.get("loss_probability", 0.0)),
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
            rng=self.rng,
        )

    def _configured_rsus(self, rsus_cfg: List[Dict], v2i_cfg: Dict) -> List[RSU]:
        rsu_range = float(v2i_cfg.get("rsu_range_m", v2i_cfg.get("range_m", 500.0)))
        return [
            RSU(
                rsu_id=str(r.get("id", r.get("rsu_id", f"RSU_{idx}"))),
                x_m=float(r.get("x_m", r.get("x", 0.0))),
                y_m=float(r.get("y_m", r.get("y", 0.0))),
                range_m=float(r.get("range_m", r.get("range", rsu_range))),
            )
            for idx, r in enumerate(rsus_cfg)
        ]

    def _auto_rsus_from_sumo(self, traci, v2i_cfg: Dict) -> List[RSU]:
        rsu_range = float(v2i_cfg.get("rsu_range_m", v2i_cfg.get("range_m", 500.0)))
        max_auto = int(v2i_cfg.get("max_auto_rsus", 20))
        rsus: List[RSU] = []
        try:
            for jid in list(traci.junction.getIDList()):
                if len(rsus) >= max_auto:
                    break
                if str(jid).startswith(":"):
                    continue
                x, y = traci.junction.getPosition(jid)
                rsus.append(RSU(rsu_id=f"RSU_{jid}", x_m=float(x), y_m=float(y), range_m=rsu_range))
        except Exception:
            pass
        return rsus

    @staticmethod
    def _communication_mode(case: Dict) -> str:
        if not bool(case.get("warning_enabled", False)):
            return "none"
        return str(case.get("communication_mode", "v2v")).lower()

    def _select_incident_vehicle(self, traci) -> Optional[str]:
        by_lane: Dict[str, List[Tuple[float, str]]] = {}
        for vid in traci.vehicle.getIDList():
            lane = traci.vehicle.getLaneID(vid)
            if not lane or lane.startswith(":"):
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
        candidate_groups.sort(key=len, reverse=True)
        return candidate_groups[0][0][1]

    def _vehicle_state(self, traci, vid: str, index: int = 0) -> VehicleState:
        x, y = traci.vehicle.getPosition(vid)
        return VehicleState(
            vid=vid,
            index=index,
            x_m=float(x),
            y_m=float(y),
            speed_mps=float(traci.vehicle.getSpeed(vid)),
            accel_mps2=float(traci.vehicle.getAcceleration(vid)),
        )

    def _broadcast_sumo_v2v(
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
        sender_state = self._vehicle_state(traci, sender_id, index=0)
        for rid in traci.vehicle.getIDList():
            if rid == sender_id or rid in reached:
                continue
            try:
                receiver_pos = traci.vehicle.getPosition(rid)
                dist = _euclidean(sender_pos, receiver_pos)
                if dist > channel.communication_range_m:
                    continue
                same_lane = traci.vehicle.getLaneID(rid) == sender_lane
                behind = same_lane and traci.vehicle.getLanePosition(rid) < sender_lane_pos
                if not behind and hop == 1:
                    continue
                fake_receiver = self._vehicle_state(traci, rid, index=1)
                channel.broadcast_to_followers(now_s, sender_state, [fake_receiver], origin_id, created_time_s, hop, event_log)
            except Exception:
                continue

    def _broadcast_sumo_v2i(
        self,
        now_s: float,
        traci,
        v2i: V2IChannel,
        incident_vehicle: str,
        target_receivers: set[str],
        created_time_s: float,
        event_log: EventLog,
    ) -> None:
        if incident_vehicle not in traci.vehicle.getIDList():
            return
        try:
            origin = self._vehicle_state(traci, incident_vehicle, index=0)
            vehicles = [origin]
            for vid in sorted(target_receivers):
                if vid in traci.vehicle.getIDList():
                    vehicles.append(self._vehicle_state(traci, vid, index=1))
            v2i.broadcast_warning(now_s, origin, vehicles, created_time_s, event_log, target_followers_only=True)
        except Exception as exc:
            event_log.add(now_s, "v2i_broadcast_error", error=str(exc))

    def _apply_warning_control(
        self,
        traci,
        vehicle_id: str,
        control_algorithm: str,
        warning_speed_factor: float,
        slow_down_duration: float,
    ) -> None:
        current_speed = float(traci.vehicle.getSpeed(vehicle_id))
        alg = control_algorithm.lower()
        if alg in {"emergency_brake", "hard_brake"}:
            target_speed = 0.0
        elif alg in {"ttc_adaptive", "adaptive_ttc", "gap_control"}:
            # SUMO version of the adaptive rule: select a lower target speed, but do not
            # necessarily force a full stop. This approximates a warning-driven CACC action.
            target_speed = max(0.0, current_speed * min(warning_speed_factor, 0.45))
        else:
            target_speed = max(0.0, current_speed * warning_speed_factor)
        traci.vehicle.slowDown(vehicle_id, target_speed, slow_down_duration)

    @staticmethod
    def _deliver_warning(
        now: float,
        msg: WarningMessage,
        reached: set[str],
        delivered_delays: list[float],
        event_log: EventLog,
    ) -> bool:
        if msg.receiver_id in reached:
            event_log.add(now, "duplicate_warning_ignored", receiver=msg.receiver_id, sender=msg.sender_id, link_type=msg.link_type)
            return False
        reached.add(msg.receiver_id)
        scheduled_delay = msg.deliver_time_s - msg.created_time_s
        delivered_delays.append(scheduled_delay)
        event_log.add(
            now,
            "warning_received",
            receiver=msg.receiver_id,
            sender=msg.sender_id,
            origin_id=msg.origin_id,
            delay_s=round(scheduled_delay, 6),
            hop=msg.hop,
            link_type=msg.link_type,
            protocol=msg.protocol,
            packet_size_bytes=msg.packet_size_bytes,
        )
        return True

    def run_case(
        self,
        case: Dict,
        sumocfg: str | Path,
        channel_cfg: Dict,
        out_dir: str | Path,
        v2i_cfg: Optional[Dict] = None,
        rsus_cfg: Optional[List[Dict]] = None,
    ) -> CaseMetrics:
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
        channel = self._build_v2v_channel(channel_cfg)
        configured_rsus = self._configured_rsus(rsus_cfg or [], v2i_cfg or {})
        v2i = self._build_v2i_channel(v2i_cfg or {}, configured_rsus)

        incident_enabled = bool(case.get("incident_enabled", True))
        warning_enabled = bool(case.get("warning_enabled", False))
        multi_hop = bool(case.get("multi_hop", False))
        communication_mode = self._communication_mode(case)
        control_algorithm = str(case.get("control_algorithm", "preemptive_brake" if warning_enabled else "none"))
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

        if not v2i.rsus and bool((v2i_cfg or {}).get("auto_rsus_from_junctions", True)):
            v2i.rsus.extend(self._auto_rsus_from_sumo(traci, v2i_cfg or {}))
            event_log.add(0.0, "v2i_auto_rsus_created", count=len(v2i.rsus))

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
                        event_log.add(
                            now,
                            "incident_started",
                            vehicle=incident_vehicle,
                            speed_mps=speed,
                            communication_mode=communication_mode,
                            control_algorithm=control_algorithm,
                        )
                        lane = traci.vehicle.getLaneID(incident_vehicle)
                        pos = traci.vehicle.getLanePosition(incident_vehicle)
                        for vid in traci.vehicle.getIDList():
                            if vid == incident_vehicle:
                                continue
                            try:
                                if traci.vehicle.getLaneID(vid) == lane and traci.vehicle.getLanePosition(vid) < pos:
                                    target_receivers.add(vid)
                            except Exception:
                                continue
                        if warning_enabled:
                            if communication_mode in {"v2v", "hybrid"}:
                                self._broadcast_sumo_v2v(now, traci, channel, incident_vehicle, incident_vehicle, now, 1, event_log, reached)
                            if communication_mode in {"v2i", "hybrid"}:
                                self._broadcast_sumo_v2i(now, traci, v2i, incident_vehicle, target_receivers, now, event_log)
                    else:
                        event_log.add(now, "incident_waiting_for_vehicle")

                for msg in channel.deliver_due(now):
                    if msg.receiver_id not in traci.vehicle.getIDList():
                        continue
                    accepted = self._deliver_warning(now, msg, reached, delivered_delays, event_log)
                    if accepted:
                        self._apply_warning_control(traci, msg.receiver_id, control_algorithm, warning_speed_factor, slow_down_duration)
                        if multi_hop and msg.hop < channel.max_hops:
                            self._broadcast_sumo_v2v(now, traci, channel, msg.receiver_id, msg.origin_id, msg.created_time_s, msg.hop + 1, event_log, reached)

                for msg in v2i.deliver_due(now):
                    if msg.receiver_id not in traci.vehicle.getIDList():
                        continue
                    accepted = self._deliver_warning(now, msg, reached, delivered_delays, event_log)
                    if accepted:
                        self._apply_warning_control(traci, msg.receiver_id, control_algorithm, warning_speed_factor, slow_down_duration)
                        if communication_mode == "hybrid" and bool(case.get("hybrid_rebroadcast_from_v2i", False)):
                            self._broadcast_sumo_v2v(now, traci, channel, msg.receiver_id, msg.origin_id, msg.created_time_s, 1, event_log, reached)

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
        max_delay = max(delivered_delays) if delivered_delays else None
        receiver_coverage = len(reached) / len(target_receivers) if target_receivers else None
        total_warnings_sent = channel.warnings_sent + v2i.warnings_sent
        total_warnings_delivered = channel.warnings_delivered + v2i.warnings_delivered
        total_lost_packets = channel.lost_packets + v2i.lost_packets
        total_bytes_sent = channel.bytes_sent + v2i.bytes_sent
        total_bytes_delivered = channel.bytes_delivered + v2i.bytes_delivered
        packet_pdr = total_warnings_delivered / total_warnings_sent if total_warnings_sent else None
        v2v_load = (channel.bytes_sent * 8.0) / max(duration * channel.data_rate_bps, 1.0)
        v2i_load = (v2i.bytes_sent * 8.0) / max(duration * v2i.data_rate_bps, 1.0)
        channel_load = v2v_load + v2i_load if total_bytes_sent else None
        protocol = channel.protocol if communication_mode == "v2v" else v2i.protocol if communication_mode == "v2i" else f"{channel.protocol}+{v2i.protocol}" if communication_mode == "hybrid" else "NONE"
        packet_size_bytes = channel.total_packet_size_bytes if communication_mode == "v2v" else v2i.total_packet_size_bytes if communication_mode == "v2i" else max(channel.total_packet_size_bytes, v2i.total_packet_size_bytes) if communication_mode == "hybrid" else None
        data_rate_bps = channel.data_rate_bps if communication_mode == "v2v" else v2i.data_rate_bps if communication_mode == "v2i" else min(channel.data_rate_bps, v2i.data_rate_bps) if communication_mode == "hybrid" else None

        return CaseMetrics(
            case_id=case["id"],
            case_name=case.get("name", case["id"]),
            communication_mode=communication_mode,
            protocol=protocol,
            packet_size_bytes=packet_size_bytes,
            control_algorithm=control_algorithm,
            collisions=len(collision_pairs),
            unique_warning_receivers=len(reached),
            target_receivers=len(target_receivers),
            warnings_sent=total_warnings_sent,
            warnings_delivered=total_warnings_delivered,
            lost_packets=total_lost_packets,
            min_gap_m=float("nan"),
            first_warning_time_s=min([row["time_s"] for row in event_log.rows if row.get("event") == "warning_received"], default=None),
            avg_delay_s=avg_delay,
            max_delay_s=max_delay,
            packet_pdr=packet_pdr,
            receiver_coverage=receiver_coverage,
            pdr=packet_pdr,
            reaction_gain_s=None,
            bytes_sent=total_bytes_sent,
            bytes_delivered=total_bytes_delivered,
            channel_load=channel_load,
            data_rate_bps=data_rate_bps,
            v2v_warnings_sent=channel.warnings_sent,
            v2v_warnings_delivered=channel.warnings_delivered,
            v2v_lost_packets=channel.lost_packets,
            v2v_bytes_sent=channel.bytes_sent,
            v2i_warnings_sent=v2i.warnings_sent,
            v2i_warnings_delivered=v2i.warnings_delivered,
            v2i_lost_packets=v2i.lost_packets,
            v2i_bytes_sent=v2i.bytes_sent,
            rsu_count=len(v2i.rsus) if communication_mode in {"v2i", "hybrid"} else 0,
        )
