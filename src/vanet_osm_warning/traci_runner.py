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


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class SumoTraciRunner:
    """SUMO/TraCI runner for OSM maps.

    Important behavior in this corrected version:
      * accident-enabled cases keep waiting until an incident is actually started;
      * a fixed SUMO incident location is used when configured;
      * when the exact fixed point has no vehicle, a controlled fallback still
        starts the incident so accident-case outputs are not empty;
      * incident location fields are written to event logs, summary CSV, and Excel.
    """

    def __init__(self, global_cfg: Dict, seed: int = 42, gui: bool = False):
        self.global_cfg = global_cfg
        self.seed = seed
        self.rng = random.Random(seed)
        self.gui = gui

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
            loss_probability=float(v2i_cfg.get("loss_probability", 0.0)),
            bit_error_rate=float(v2i_cfg.get("bit_error_rate", 0.0)),
            downlink_accounting=str(v2i_cfg.get("downlink_accounting", "broadcast")),
            rng=self.rng,
        )

    def _configured_rsus(self, rsus_cfg: List[Dict], v2i_cfg: Dict) -> List[RSU]:
        default_range = float(v2i_cfg.get("rsu_range_m", v2i_cfg.get("range_m", 500.0)))
        return [
            RSU(
                rsu_id=str(r.get("id", f"RSU_{i}")),
                x_m=float(r.get("x_m", r.get("x", 0.0))),
                y_m=float(r.get("y_m", r.get("y", 0.0))),
                range_m=float(r.get("range_m", default_range)),
            )
            for i, r in enumerate(rsus_cfg)
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
        except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
            pass
        return rsus

    @staticmethod
    def _communication_mode(case: Dict) -> str:
        if not bool(case.get("warning_enabled", False)):
            return "none"
        return str(case.get("communication_mode", "v2v")).lower()

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

    def _vehicle_snapshot(self, traci) -> List[dict]:
        rows: List[dict] = []
        for vid in traci.vehicle.getIDList():
            try:
                lane_id = traci.vehicle.getLaneID(vid)
                edge_id = traci.vehicle.getRoadID(vid)
                if not lane_id or str(lane_id).startswith(":") or str(edge_id).startswith(":"):
                    continue
                x, y = traci.vehicle.getPosition(vid)
                rows.append(
                    {
                        "vid": vid,
                        "lane_id": lane_id,
                        "edge_id": edge_id,
                        "lane_pos": float(traci.vehicle.getLanePosition(vid)),
                        "speed": float(traci.vehicle.getSpeed(vid)),
                        "x": float(x),
                        "y": float(y),
                    }
                )
            except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                continue
        return rows

    def _lane_length(self, traci, lane_id: str) -> float:
        try:
            return float(traci.lane.getLength(lane_id))
        except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
            return 0.0

    def _edge_for_lane(self, traci, lane_id: str) -> str:
        try:
            return str(traci.lane.getEdgeID(lane_id))
        except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
            if "_" in lane_id:
                return lane_id.rsplit("_", 1)[0]
            return lane_id

    def _candidate_has_followers(self, rows: List[dict], cand: dict) -> bool:
        for row in rows:
            if row["vid"] == cand["vid"]:
                continue
            if row["lane_id"] == cand["lane_id"] and row["lane_pos"] < cand["lane_pos"]:
                return True
        return False

    def _select_incident_vehicle(self, traci) -> Optional[str]:
        """Legacy robust fallback selector: pick a moving vehicle on the densest lane."""
        by_lane: Dict[str, List[Tuple[float, str]]] = {}
        for row in self._vehicle_snapshot(traci):
            if row["speed"] < 1.0:
                continue
            by_lane.setdefault(row["lane_id"], []).append((row["lane_pos"], row["vid"]))
        candidate_groups = [sorted(v, reverse=True) for v in by_lane.values() if len(v) >= 1]
        if not candidate_groups:
            return None
        candidate_groups.sort(key=len, reverse=True)
        return candidate_groups[0][0][1]

    def _resolve_fixed_location(self, traci, rows: List[dict], incident_cfg: Dict) -> Optional[dict]:
        """Resolve configured or deterministic auto fixed location for the incident.

        Config can specify edge_id/lane_id/position_m. If lane/edge is left blank,
        the runner chooses the densest current lane and a fixed position on that
        lane. Because all cases use the same SUMO seed and the selection happens
        before any warning action, this auto location is deterministic across cases.
        """
        lane_id = str(incident_cfg.get("lane_id", "") or "").strip()
        edge_id = str(incident_cfg.get("edge_id", "") or "").strip()
        position_raw = incident_cfg.get("position_m", None)

        if lane_id or edge_id:
            matched = [r for r in rows if (not lane_id or r["lane_id"] == lane_id) and (not edge_id or r["edge_id"] == edge_id)]
            if not matched:
                return None
            if not lane_id:
                # Prefer the lane with the most vehicles on the configured edge.
                counts: Dict[str, int] = {}
                for r in matched:
                    counts[r["lane_id"]] = counts.get(r["lane_id"], 0) + 1
                lane_id = max(counts, key=counts.get)
            edge_id = edge_id or self._edge_for_lane(traci, lane_id)
            lane_len = self._lane_length(traci, lane_id)
            position_m = _safe_float(position_raw, lane_len * 0.55 if lane_len > 0 else 0.0)
            if lane_len > 0:
                position_m = min(max(position_m, 1.0), max(1.0, lane_len - 1.0))
            return {"lane_id": lane_id, "edge_id": edge_id, "position_m": position_m, "selection_mode": "configured_fixed_location"}

        # Auto fixed location: choose a lane with at least two cars when possible.
        by_lane: Dict[str, List[dict]] = {}
        for r in rows:
            by_lane.setdefault(r["lane_id"], []).append(r)
        if not by_lane:
            return None
        candidates = sorted(by_lane.items(), key=lambda item: (len(item[1]), max(x["speed"] for x in item[1])), reverse=True)
        lane_id, lane_rows = candidates[0]
        lane_len = self._lane_length(traci, lane_id)
        edge_id = self._edge_for_lane(traci, lane_id)
        if position_raw is not None:
            position_m = _safe_float(position_raw, lane_len * 0.55 if lane_len > 0 else max(r["lane_pos"] for r in lane_rows))
        elif lane_len > 0:
            position_m = min(max(20.0, lane_len * float(incident_cfg.get("auto_position_ratio", 0.55))), max(1.0, lane_len - 1.0))
        else:
            # Fallback to the middle of the currently occupied lane segment.
            positions = [r["lane_pos"] for r in lane_rows]
            position_m = sum(positions) / max(len(positions), 1)
        return {"lane_id": lane_id, "edge_id": edge_id, "position_m": position_m, "selection_mode": "auto_fixed_location"}

    def _select_fixed_incident_vehicle(
        self,
        traci,
        now: float,
        incident_time: float,
        incident_cfg: Dict,
    ) -> tuple[Optional[str], dict, str]:
        rows = self._vehicle_snapshot(traci)
        if not rows:
            return None, {}, "no_vehicle_loaded"

        min_speed = float(incident_cfg.get("min_speed_mps", 1.0))
        search_radius = float(incident_cfg.get("search_radius_m", 80.0))
        fallback_after = float(incident_cfg.get("fallback_after_s", 10.0))
        fixed = self._resolve_fixed_location(traci, rows, incident_cfg)

        # If no fixed location can be resolved, fall back to legacy selector.
        if not fixed:
            vid = self._select_incident_vehicle(traci)
            if not vid:
                return None, {}, "no_candidate_vehicle"
            cand = next((r for r in rows if r["vid"] == vid), None)
            details = dict(cand or {})
            details.update({"fixed_incident": False, "selection_mode": "fallback_legacy_no_fixed_location"})
            return vid, details, "fallback_legacy_no_fixed_location"

        lane_id = fixed["lane_id"]
        edge_id = fixed["edge_id"]
        position_m = float(fixed["position_m"])
        lane_rows = [r for r in rows if r["lane_id"] == lane_id and r["edge_id"] == edge_id and r["speed"] >= min_speed]
        if not lane_rows:
            # Relax edge matching because some SUMO road IDs can differ from lane edge IDs on internal conversions.
            lane_rows = [r for r in rows if r["lane_id"] == lane_id and r["speed"] >= min_speed]
        if not lane_rows:
            if now - incident_time >= fallback_after:
                vid = self._select_incident_vehicle(traci)
                cand = next((r for r in rows if r["vid"] == vid), None) if vid else None
                details = dict(cand or {})
                details.update({"fixed_incident": False, "selection_mode": "fallback_after_no_vehicle_on_fixed_lane"})
                return vid, details, "fallback_after_no_vehicle_on_fixed_lane"
            return None, {**fixed, "fixed_incident": True}, "waiting_no_vehicle_on_fixed_lane"

        def score(row: dict) -> tuple:
            distance = abs(float(row["lane_pos"]) - position_m)
            has_followers = 1 if self._candidate_has_followers(rows, row) else 0
            return (distance, -has_followers, -float(row["speed"]))

        best = sorted(lane_rows, key=score)[0]
        distance = abs(float(best["lane_pos"]) - position_m)
        if distance > search_radius and now - incident_time < fallback_after:
            return None, {**fixed, "nearest_distance_m": distance, "fixed_incident": True}, "waiting_for_vehicle_near_fixed_location"

        details = dict(best)
        details.update(
            {
                "fixed_incident": True,
                "fixed_edge_id": edge_id,
                "fixed_lane_id": lane_id,
                "fixed_position_m": position_m,
                "nearest_distance_m": distance,
                "selection_mode": fixed.get("selection_mode", "fixed_location"),
            }
        )
        reason = "fixed_location_match" if distance <= search_radius else "fallback_after_nearest_fixed_lane_vehicle"
        return best["vid"], details, reason

    def _collect_target_receivers(self, traci, incident_vehicle: str, event_log: EventLog, now: float, target_radius_m: float = 600.0) -> set[str]:
        target_receivers: set[str] = set()
        if incident_vehicle not in traci.vehicle.getIDList():
            return target_receivers
        try:
            lane = traci.vehicle.getLaneID(incident_vehicle)
            edge = traci.vehicle.getRoadID(incident_vehicle)
            pos = float(traci.vehicle.getLanePosition(incident_vehicle))
            x0, y0 = traci.vehicle.getPosition(incident_vehicle)
        except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
            return target_receivers

        # Primary target definition: vehicles behind the incident vehicle in the same lane.
        for vid in traci.vehicle.getIDList():
            if vid == incident_vehicle:
                continue
            try:
                if traci.vehicle.getLaneID(vid) == lane and float(traci.vehicle.getLanePosition(vid)) < pos:
                    target_receivers.add(vid)
            except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                continue

        if target_receivers:
            event_log.add(now, "target_receivers_selected", mode="same_lane_behind", count=len(target_receivers), lane_id=lane, edge_id=edge)
            return target_receivers

        # Secondary fallback: vehicles behind on the same edge, any lane.
        for vid in traci.vehicle.getIDList():
            if vid == incident_vehicle:
                continue
            try:
                if traci.vehicle.getRoadID(vid) == edge and float(traci.vehicle.getLanePosition(vid)) < pos:
                    target_receivers.add(vid)
            except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                continue
        if target_receivers:
            event_log.add(now, "target_receivers_selected", mode="same_edge_behind", count=len(target_receivers), lane_id=lane, edge_id=edge)
            return target_receivers

        # Last fallback for small/sparse maps: nearest active vehicles. This prevents
        # warning-enabled cases from producing empty coverage fields merely because
        # the generated route has no same-lane follower at the fixed point.
        candidates: list[tuple[float, str]] = []
        for vid in traci.vehicle.getIDList():
            if vid == incident_vehicle:
                continue
            try:
                x, y = traci.vehicle.getPosition(vid)
                dist = _euclidean((float(x0), float(y0)), (float(x), float(y)))
                if dist <= target_radius_m:
                    candidates.append((dist, vid))
            except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                continue
        candidates.sort()
        for _, vid in candidates[:25]:
            target_receivers.add(vid)
        event_log.add(now, "target_receivers_selected", mode="nearest_vehicle_fallback", count=len(target_receivers), lane_id=lane, edge_id=edge)
        return target_receivers

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
        try:
            sender_pos = traci.vehicle.getPosition(sender_id)
            sender_lane = traci.vehicle.getLaneID(sender_id)
            sender_lane_pos = float(traci.vehicle.getLanePosition(sender_id))
            sender_state = self._vehicle_state(traci, sender_id, index=0)
        except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
            return
        for rid in traci.vehicle.getIDList():
            if rid == sender_id or rid in reached:
                continue
            try:
                receiver_pos = traci.vehicle.getPosition(rid)
                dist = _euclidean(sender_pos, receiver_pos)
                if dist > channel.communication_range_m:
                    continue
                same_lane = traci.vehicle.getLaneID(rid) == sender_lane
                behind = same_lane and float(traci.vehicle.getLanePosition(rid)) < sender_lane_pos
                # For SUMO traffic, warning is mainly for following vehicles. If no
                # same-lane receiver exists, V2I/hybrid fallback still covers nearby cars.
                if not behind:
                    continue
                fake_receiver = self._vehicle_state(traci, rid, index=1)
                channel.broadcast_to_followers(now_s, sender_state, [fake_receiver], origin_id, created_time_s, hop, event_log)
            except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
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
        except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
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

    def _update_min_gap(self, traci, vehicle_length: float, current_min: float) -> float:
        by_lane: Dict[str, List[Tuple[float, str]]] = {}
        for vid in traci.vehicle.getIDList():
            try:
                lane = traci.vehicle.getLaneID(vid)
                if not lane or lane.startswith(":"):
                    continue
                by_lane.setdefault(lane, []).append((float(traci.vehicle.getLanePosition(vid)), vid))
            except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                continue
        for rows in by_lane.values():
            rows.sort(reverse=True)
            for i in range(len(rows) - 1):
                front_pos = rows[i][0]
                rear_pos = rows[i + 1][0]
                gap = front_pos - rear_pos - vehicle_length
                current_min = min(current_min, gap)
        return current_min

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
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Cannot import traci. Install SUMO and set SUMO_HOME, or run demo mode.") from exc

        out_dir = ensure_dir(out_dir)
        event_log = EventLog()
        sumo_binary = find_executable("sumo-gui" if self.gui else "sumo")
        step_length = float(self.global_cfg.get("step_length_s", 0.1))
        duration = float(self.global_cfg.get("duration_s", 90.0))
        seed = int(self.seed)
        vehicle_length = float(self.global_cfg.get("vehicle_length_m", 4.5))
        channel = self._build_v2v_channel(channel_cfg)
        configured_rsus = self._configured_rsus(rsus_cfg or [], v2i_cfg or {})
        v2i = self._build_v2i_channel(v2i_cfg or {}, configured_rsus)

        incident_enabled = bool(case.get("incident_enabled", True))
        warning_enabled = bool(case.get("warning_enabled", False))
        multi_hop = bool(case.get("multi_hop", False))
        communication_mode = self._communication_mode(case)
        control_algorithm = str(case.get("control_algorithm", "preemptive_brake" if warning_enabled else "none"))
        incident_cfg = dict(case.get("sumo_fixed_incident", {}))
        incident_time = float(case.get("sumo_incident_time_s", incident_cfg.get("time_s", 25.0)))
        slow_down_duration = float(case.get("sumo_slowdown_duration_s", incident_cfg.get("slow_down_duration_s", 2.0)))
        warning_speed_factor = float(case.get("sumo_warning_speed_factor", 0.35))
        wait_log_interval = float(incident_cfg.get("wait_log_interval_s", 1.0))
        target_radius_m = float(incident_cfg.get("target_radius_m", 600.0))

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
        incident_details: dict = {}
        reached: set[str] = set()
        target_receivers: set[str] = set()
        delivered_delays: list[float] = []
        collision_pairs: set[tuple[str, str]] = set()
        trajectory_rows: list[dict] = []
        min_gap = float("inf")
        last_wait_log = -1e9
        first_visual_danger_time: Optional[float] = None
        visual_gap = float(self.global_cfg.get("visual_detection_gap_m", 6.0))

        try:
            steps = int(duration / step_length)
            for _step in range(steps + 1):
                traci.simulationStep()
                try:
                    now = float(traci.simulation.getTime())
                except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                    now = round(_step * step_length, 10)

                min_gap = self._update_min_gap(traci, vehicle_length, min_gap)
                if incident_started and first_visual_danger_time is None and min_gap <= visual_gap:
                    first_visual_danger_time = now
                    event_log.add(now, "visual_danger_detected_network", min_gap_m=round(min_gap, 4))

                if incident_enabled and not incident_started and now >= incident_time:
                    incident_vehicle, incident_details, reason = self._select_fixed_incident_vehicle(traci, now, incident_time, incident_cfg)
                    if incident_vehicle:
                        incident_started = True
                        speed = float(traci.vehicle.getSpeed(incident_vehicle))
                        traci.vehicle.slowDown(incident_vehicle, 0.0, slow_down_duration)
                        lane = traci.vehicle.getLaneID(incident_vehicle)
                        edge = traci.vehicle.getRoadID(incident_vehicle)
                        lane_pos = float(traci.vehicle.getLanePosition(incident_vehicle))
                        x, y = traci.vehicle.getPosition(incident_vehicle)
                        incident_details.update(
                            {
                                "vid": incident_vehicle,
                                "speed": speed,
                                "lane_id": lane,
                                "edge_id": edge,
                                "lane_pos": lane_pos,
                                "x": float(x),
                                "y": float(y),
                                "selection_reason": reason,
                                "time_s": now,
                            }
                        )
                        event_log.add(
                            now,
                            "incident_started",
                            vehicle=incident_vehicle,
                            speed_mps=round(speed, 4),
                            communication_mode=communication_mode,
                            control_algorithm=control_algorithm,
                            edge_id=edge,
                            lane_id=lane,
                            lane_position_m=round(lane_pos, 4),
                            x_m=round(float(x), 4),
                            y_m=round(float(y), 4),
                            fixed_incident=bool(incident_details.get("fixed_incident", True)),
                            fixed_edge_id=incident_details.get("fixed_edge_id", incident_cfg.get("edge_id", "")),
                            fixed_lane_id=incident_details.get("fixed_lane_id", incident_cfg.get("lane_id", "")),
                            fixed_position_m=round(float(incident_details.get("fixed_position_m", incident_cfg.get("position_m", lane_pos) or lane_pos)), 4),
                            nearest_distance_m=round(float(incident_details.get("nearest_distance_m", 0.0)), 4),
                            selection_reason=reason,
                        )
                        target_receivers = self._collect_target_receivers(traci, incident_vehicle, event_log, now, target_radius_m=target_radius_m)
                        if warning_enabled:
                            if communication_mode in {"v2v", "hybrid"}:
                                self._broadcast_sumo_v2v(now, traci, channel, incident_vehicle, incident_vehicle, now, 1, event_log, reached)
                            if communication_mode in {"v2i", "hybrid"}:
                                self._broadcast_sumo_v2i(now, traci, v2i, incident_vehicle, target_receivers, now, event_log)
                    elif now - last_wait_log >= wait_log_interval:
                        last_wait_log = now
                        event_log.add(
                            now,
                            "incident_waiting_for_vehicle",
                            reason=reason,
                            fixed_edge_id=incident_details.get("edge_id", incident_cfg.get("edge_id", "")),
                            fixed_lane_id=incident_details.get("lane_id", incident_cfg.get("lane_id", "")),
                            fixed_position_m=incident_details.get("position_m", incident_cfg.get("position_m", "")),
                            nearest_distance_m=incident_details.get("nearest_distance_m", ""),
                        )

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
                except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
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
                            "lane_position_m": float(traci.vehicle.getLanePosition(vid)),
                            "warning_received": vid in reached,
                            "is_incident_vehicle": vid == incident_vehicle,
                        })
                    except (traci.TraCIException, RuntimeError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                        continue
        finally:
            traci.close(False)

        pd.DataFrame(trajectory_rows).to_csv(out_dir / f"trajectories_{case['id']}.csv", index=False)
        write_events_csv(event_log, out_dir / f"events_{case['id']}.csv")

        avg_delay = sum(delivered_delays) / len(delivered_delays) if delivered_delays else None
        max_delay = max(delivered_delays) if delivered_delays else None
        if target_receivers:
            receiver_coverage = len(reached.intersection(target_receivers)) / len(target_receivers)
        else:
            receiver_coverage = 0.0 if warning_enabled else None
        total_warnings_sent = channel.warnings_sent + v2i.warnings_sent
        total_warnings_delivered = channel.warnings_delivered + v2i.warnings_delivered
        total_lost_packets = channel.lost_packets + v2i.lost_packets
        total_bytes_sent = channel.bytes_sent + v2i.bytes_sent
        total_bytes_delivered = channel.bytes_delivered + v2i.bytes_delivered
        packet_pdr = total_warnings_delivered / total_warnings_sent if total_warnings_sent else (0.0 if warning_enabled else None)
        v2v_load = (channel.bytes_sent * 8.0) / max(duration * channel.data_rate_bps, 1.0)
        v2i_load = (v2i.bytes_sent * 8.0) / max(duration * v2i.data_rate_bps, 1.0)
        normalized_offered_load = v2v_load + v2i_load if total_bytes_sent else (0.0 if warning_enabled else None)
        duplicate_deliveries = max(0, total_warnings_delivered - len(reached))
        useful_delivery_ratio = len(reached) / total_warnings_delivered if total_warnings_delivered else None
        protocol = channel.protocol if communication_mode == "v2v" else v2i.protocol if communication_mode == "v2i" else f"{channel.protocol}+{v2i.protocol}" if communication_mode == "hybrid" else "NONE"
        packet_size_bytes = channel.total_packet_size_bytes if communication_mode == "v2v" else v2i.total_packet_size_bytes if communication_mode == "v2i" else max(channel.total_packet_size_bytes, v2i.total_packet_size_bytes) if communication_mode == "hybrid" else None
        data_rate_bps = channel.data_rate_bps if communication_mode == "v2v" else v2i.data_rate_bps if communication_mode == "v2i" else min(channel.data_rate_bps, v2i.data_rate_bps) if communication_mode == "hybrid" else None
        result_status = "OK"
        if incident_enabled and not incident_started:
            result_status = "ERROR_NO_INCIDENT"
        elif warning_enabled and target_receivers and total_warnings_sent <= 0:
            result_status = "ERROR_NO_WARNING_SENT"
        elif warning_enabled and not target_receivers:
            result_status = "WARNING_NO_TARGET_RECEIVERS"

        first_warning_time = min([row["time_s"] for row in event_log.rows if row.get("event") == "warning_received"], default=None)
        if math.isinf(min_gap):
            min_gap = float("nan")

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
            min_gap_m=min_gap,
            first_warning_time_s=first_warning_time,
            avg_delay_s=avg_delay,
            max_delay_s=max_delay,
            packet_pdr=packet_pdr,
            receiver_coverage=receiver_coverage,
            pdr=packet_pdr,
            reaction_gain_s=(first_visual_danger_time - first_warning_time) if first_visual_danger_time is not None and first_warning_time is not None else None,
            warning_lead_time_vs_visual_detection_s=(first_visual_danger_time - first_warning_time) if first_visual_danger_time is not None and first_warning_time is not None else None,
            duplicate_deliveries=duplicate_deliveries,
            useful_delivery_ratio=useful_delivery_ratio,
            bytes_sent=total_bytes_sent,
            bytes_delivered=total_bytes_delivered,
            channel_load=normalized_offered_load,
            normalized_offered_load=normalized_offered_load,
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
            rsu_count=len(v2i.rsus) if communication_mode in {"v2i", "hybrid"} else 0,
            incident_expected=incident_enabled,
            incident_started=incident_started,
            incident_vehicle=incident_vehicle,
            incident_time_s=incident_details.get("time_s", incident_time if incident_started else None),
            incident_edge_id=incident_details.get("edge_id") if incident_started else None,
            incident_lane_id=incident_details.get("lane_id") if incident_started else None,
            incident_lane_position_m=incident_details.get("lane_pos") if incident_started else None,
            incident_x_m=incident_details.get("x") if incident_started else None,
            incident_y_m=incident_details.get("y") if incident_started else None,
            result_status=result_status,
        )
