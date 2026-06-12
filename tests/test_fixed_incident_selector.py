from __future__ import annotations

from dataclasses import dataclass

from vanet_osm_warning.traci_runner import SumoTraciRunner


@dataclass
class FakeVehicleRow:
    vid: str
    lane_id: str
    edge_id: str
    lane_pos: float
    x: float
    y: float
    speed: float = 10.0
    accel: float = 0.0


class FakeVehicleAPI:
    def __init__(self, rows: list[FakeVehicleRow]):
        self.rows = {row.vid: row for row in rows}

    def getIDList(self):
        return list(self.rows.keys())

    def getLaneID(self, vid):
        return self.rows[vid].lane_id

    def getRoadID(self, vid):
        return self.rows[vid].edge_id

    def getLanePosition(self, vid):
        return self.rows[vid].lane_pos

    def getPosition(self, vid):
        row = self.rows[vid]
        return (row.x, row.y)

    def getSpeed(self, vid):
        return self.rows[vid].speed

    def getAcceleration(self, vid):
        return self.rows[vid].accel


class FakeLaneAPI:
    def __init__(self, lengths: dict[str, float], edges: dict[str, str]):
        self.lengths = lengths
        self.edges = edges

    def getLength(self, lane_id):
        return self.lengths[lane_id]

    def getEdgeID(self, lane_id):
        return self.edges[lane_id]


class FakeTraci:
    def __init__(self, rows: list[FakeVehicleRow]):
        self.vehicle = FakeVehicleAPI(rows)
        self.lane = FakeLaneAPI(
            lengths={"E1_0": 300.0, "E2_0": 300.0},
            edges={"E1_0": "E1", "E2_0": "E2"},
        )


def test_configured_fixed_location_selects_nearest_vehicle() -> None:
    traci = FakeTraci(
        [
            FakeVehicleRow("veh_far", "E1_0", "E1", 50.0, 50.0, 0.0),
            FakeVehicleRow("veh_near", "E1_0", "E1", 104.0, 104.0, 0.0),
            FakeVehicleRow("veh_other_lane", "E2_0", "E2", 100.0, 100.0, 10.0),
        ]
    )
    runner = SumoTraciRunner({}, seed=1)
    vid, details, reason = runner._select_fixed_incident_vehicle(
        traci,
        now=25.0,
        incident_time=25.0,
        incident_cfg={
            "enabled": True,
            "edge_id": "E1",
            "lane_id": "E1_0",
            "position_m": 100.0,
            "search_radius_m": 10.0,
            "fallback_after_s": 8.0,
            "min_speed_mps": 1.0,
        },
    )
    assert vid == "veh_near"
    assert reason == "fixed_location_match"
    assert details["fixed_incident"] is True
    assert details["fixed_lane_id"] == "E1_0"
    assert abs(details["nearest_distance_m"] - 4.0) < 1e-9


def test_fixed_location_waits_then_fallback_selects_nearest_on_lane() -> None:
    traci = FakeTraci([FakeVehicleRow("veh_far", "E1_0", "E1", 40.0, 40.0, 0.0)])
    runner = SumoTraciRunner({}, seed=1)
    cfg = {
        "enabled": True,
        "edge_id": "E1",
        "lane_id": "E1_0",
        "position_m": 200.0,
        "search_radius_m": 5.0,
        "fallback_after_s": 8.0,
        "min_speed_mps": 1.0,
    }

    vid, details, reason = runner._select_fixed_incident_vehicle(traci, now=25.0, incident_time=25.0, incident_cfg=cfg)
    assert vid is None
    assert reason == "waiting_for_vehicle_near_fixed_location"
    assert details["fixed_incident"] is True

    vid, details, reason = runner._select_fixed_incident_vehicle(traci, now=34.0, incident_time=25.0, incident_cfg=cfg)
    assert vid == "veh_far"
    assert reason == "fallback_after_nearest_fixed_lane_vehicle"
    assert details["fixed_incident"] is True


def test_auto_fixed_location_resolves_densest_lane() -> None:
    traci = FakeTraci(
        [
            FakeVehicleRow("veh_1", "E1_0", "E1", 40.0, 40.0, 0.0),
            FakeVehicleRow("veh_2", "E1_0", "E1", 60.0, 60.0, 0.0),
            FakeVehicleRow("veh_3", "E2_0", "E2", 150.0, 150.0, 10.0),
        ]
    )
    runner = SumoTraciRunner({}, seed=1)
    rows = runner._vehicle_snapshot(traci)
    fixed = runner._resolve_fixed_location(traci, rows, {"enabled": True, "auto_position_ratio": 0.5})
    assert fixed is not None
    assert fixed["lane_id"] == "E1_0"
    assert fixed["edge_id"] == "E1"
    assert fixed["position_m"] == 150.0
    assert fixed["selection_mode"] == "auto_fixed_location"
