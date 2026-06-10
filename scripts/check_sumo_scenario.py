#!/usr/bin/env python3
"""Quick sanity check for a generated SUMO scenario.

Usage:
  python scripts/check_sumo_scenario.py data/sumo/osm_map.sumocfg
  python scripts/check_sumo_scenario.py data/sumo/osm_map.net.xml data/sumo/osm_map.rou.xml
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def resolve_from_sumocfg(sumocfg: Path) -> tuple[Path, Path]:
    root = ET.parse(sumocfg).getroot()
    input_node = root.find("input")
    if input_node is None:
        raise SystemExit(f"No <input> node in {sumocfg}")
    net_node = input_node.find("net-file")
    route_node = input_node.find("route-files")
    if net_node is None or route_node is None:
        raise SystemExit(f"Missing <net-file> or <route-files> in {sumocfg}")
    base = sumocfg.parent
    return (base / net_node.get("value", "")).resolve(), (base / route_node.get("value", "")).resolve()


def lane_allows_passenger(lane: ET.Element) -> bool:
    allow = lane.get("allow")
    disallow = lane.get("disallow")
    if allow:
        return "passenger" in allow.split() or "private" in allow.split() or "all" in allow.split()
    if disallow:
        blocked = set(disallow.split())
        return "passenger" not in blocked and "private" not in blocked and "all" not in blocked
    return True


def count_edges(net_file: Path) -> int:
    root = ET.parse(net_file).getroot()
    count = 0
    for edge in root.findall("edge"):
        eid = edge.get("id", "")
        if not eid or eid.startswith(":") or edge.get("function") in {"internal", "crossing", "walkingarea"}:
            continue
        lanes = edge.findall("lane")
        if lanes and any(lane_allows_passenger(lane) for lane in lanes):
            count += 1
    return count


def count_vehicles(route_file: Path) -> tuple[int, float | None, float | None, int]:
    root = ET.parse(route_file).getroot()
    vehicles = root.findall("vehicle")
    trips = root.findall("trip")
    departs: list[float] = []
    for node in vehicles + trips:
        try:
            departs.append(float(node.get("depart", "0")))
        except ValueError:
            pass
    first = min(departs) if departs else None
    last = max(departs) if departs else None
    in_first_90 = sum(1 for d in departs if d <= 90.0)
    return len(vehicles) + len(trips), first, last, in_first_90


def main() -> None:
    if len(sys.argv) == 2:
        net_file, route_file = resolve_from_sumocfg(Path(sys.argv[1]).resolve())
    elif len(sys.argv) == 3:
        net_file = Path(sys.argv[1]).resolve()
        route_file = Path(sys.argv[2]).resolve()
    else:
        raise SystemExit(__doc__)

    if not net_file.exists():
        raise SystemExit(f"Net file not found: {net_file}")
    if not route_file.exists():
        raise SystemExit(f"Route file not found: {route_file}")

    edges = count_edges(net_file)
    vehicles, first, last, in_first_90 = count_vehicles(route_file)
    print(f"net_file={net_file}")
    print(f"route_file={route_file}")
    print(f"usable_passenger_edges={edges}")
    print(f"vehicles_or_trips={vehicles}")
    print(f"first_depart={first}")
    print(f"last_depart={last}")
    print(f"departures_in_first_90s={in_first_90}")

    if edges <= 0:
        raise SystemExit("ERROR: no passenger-car edges. Your OSM export is not usable for car traffic.")
    if vehicles <= 0:
        raise SystemExit("ERROR: route file has zero vehicles/trips.")
    if in_first_90 <= 0:
        raise SystemExit("ERROR: no vehicle departs in first 90 seconds, so GUI may look empty.")
    print("OK: scenario should show cars in SUMO/SUMO-GUI.")


if __name__ == "__main__":
    main()
