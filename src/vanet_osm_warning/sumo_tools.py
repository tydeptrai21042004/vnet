from __future__ import annotations

import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional


PASSENGER_CLASSES = {
    "passenger",
    "private",
    "taxi",
    "bus",
    "delivery",
    "truck",
    "motorcycle",
}


class SumoPreprocessError(RuntimeError):
    """Raised when a SUMO preprocessing step cannot create a usable scenario."""


def add_sumo_tools_to_path() -> None:
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        tools = Path(sumo_home) / "tools"
        if tools.exists() and str(tools) not in sys.path:
            sys.path.append(str(tools))


def find_executable(name: str) -> str:
    exe = shutil.which(name)
    if exe:
        return exe
    raise RuntimeError(
        f"Cannot find '{name}'. Install SUMO first: sudo apt update && sudo apt install -y sumo sumo-tools sumo-doc"
    )


def run_cmd(cmd: list[str], cwd: str | Path | None = None, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    print("[RUN]", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.returncode != 0 and not allow_fail:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)
    return proc


def download_osm_by_bbox(south: float, west: float, north: float, east: float, out_file: str | Path) -> Path:
    """Download an OSM XML file using OSMnx.

    Requires internet access and the optional osmnx package. For reliability in
    a thesis environment, exporting a small .osm file manually from
    openstreetmap.org is often easier.
    """
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        import osmnx as ox
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("OSMnx is required for bbox download. Install with: pip install osmnx") from exc
    graph = ox.graph_from_bbox(north, south, east, west, network_type="drive", simplify=False)
    ox.save_graph_xml(graph, filepath=str(out_file))
    return out_file


def osm_to_sumo_net(osm_file: str | Path, net_file: str | Path) -> Path:
    """Convert OSM to a SUMO network that keeps passenger-car edges.

    The previous version removed several vClasses but did not explicitly keep
    passenger edges or reduce the network to a usable connected component. That
    often left disconnected fragments, which caused randomTrips/duarouter to
    discard most or all generated trips. This version is intentionally stricter
    for VANET car traffic.
    """
    osm_file = Path(osm_file)
    net_file = Path(net_file)
    net_file.parent.mkdir(parents=True, exist_ok=True)
    netconvert = find_executable("netconvert")
    cmd = [
        netconvert,
        "--osm-files", str(osm_file),
        "--output-file", str(net_file),
        "--geometry.remove",
        "--roundabouts.guess",
        "--ramps.guess",
        "--junctions.join",
        "--tls.guess-signals",
        "--keep-edges.by-vclass", "passenger",
        "--keep-edges.components", "1",
        "--remove-edges.isolated",
        "--no-turnarounds",
    ]
    run_cmd(cmd)
    return net_file


def _find_random_trips_script() -> Path:
    sumo_home = os.environ.get("SUMO_HOME")
    candidates: list[Path] = []
    if sumo_home:
        candidates.append(Path(sumo_home) / "tools" / "randomTrips.py")
    candidates.extend([
        Path("/usr/share/sumo/tools/randomTrips.py"),
        Path("/usr/local/share/sumo/tools/randomTrips.py"),
    ])
    random_trips = next((p for p in candidates if p.exists()), None)
    if random_trips is None:
        raise RuntimeError("Cannot find randomTrips.py. Install sumo-tools or set SUMO_HOME.")
    return random_trips


def _xml_vehicle_count(route_file: str | Path) -> int:
    route_file = Path(route_file)
    if not route_file.exists() or route_file.stat().st_size == 0:
        return 0
    try:
        root = ET.parse(route_file).getroot()
    except ET.ParseError:
        return 0
    return len(root.findall("vehicle")) + len(root.findall("trip"))


def _lane_allows_passenger(lane: ET.Element) -> bool:
    allow = lane.get("allow")
    disallow = lane.get("disallow")
    if allow:
        allowed = set(allow.split())
        return bool(allowed.intersection(PASSENGER_CLASSES)) or "all" in allowed
    if disallow:
        blocked = set(disallow.split())
        return "passenger" not in blocked and "private" not in blocked and "all" not in blocked
    # No restriction in SUMO means open to regular vehicle classes.
    return True


def _edge_length(edge: ET.Element) -> float:
    lengths = []
    for lane in edge.findall("lane"):
        try:
            lengths.append(float(lane.get("length", "0")))
        except ValueError:
            continue
    return max(lengths) if lengths else 0.0


def _usable_edges_from_net(net_file: str | Path) -> list[str]:
    """Return non-internal edges usable by passenger vehicles.

    This parser is intentionally independent of SUMO libraries, so it can also
    run on systems where only the net XML exists.
    """
    root = ET.parse(net_file).getroot()
    edges: list[tuple[str, float]] = []
    for edge in root.findall("edge"):
        edge_id = edge.get("id", "")
        if not edge_id or edge_id.startswith(":"):
            continue
        if edge.get("function") in {"internal", "crossing", "walkingarea"}:
            continue
        lanes = edge.findall("lane")
        if not lanes:
            continue
        if not any(_lane_allows_passenger(lane) for lane in lanes):
            continue
        length = _edge_length(edge)
        if length <= 1.0:
            continue
        edges.append((edge_id, length))
    # Longer edges keep vehicles visible for more GUI frames.
    edges.sort(key=lambda item: item[1], reverse=True)
    return [edge_id for edge_id, _ in edges]


def _connected_edge_pairs_from_net(net_file: str | Path, usable_edges: Iterable[str]) -> list[tuple[str, str]]:
    """Find direct edge pairs from <connection from=... to=...> entries."""
    usable = set(usable_edges)
    root = ET.parse(net_file).getroot()
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for conn in root.findall("connection"):
        src = conn.get("from", "")
        dst = conn.get("to", "")
        if src in usable and dst in usable and src != dst:
            pair = (src, dst)
            if pair not in seen:
                pairs.append(pair)
                seen.add(pair)
    return pairs


def _write_fallback_single_edge_routes(
    net_file: str | Path,
    route_file: str | Path,
    end_s: int,
    period_s: float,
    target_vehicle_count: int,
) -> Path:
    """Write a guaranteed route file even when randomTrips cannot route.

    A single-edge route is valid in SUMO and is the most robust fallback for a
    bad/disconnected/new OSM map. It guarantees that cars are inserted if the
    network has at least one passenger edge. Vehicles are distributed across the
    longest passenger edges and depart from t=0, so the GUI shows traffic early.
    """
    route_file = Path(route_file)
    route_file.parent.mkdir(parents=True, exist_ok=True)
    usable_edges = _usable_edges_from_net(net_file)
    if not usable_edges:
        raise SumoPreprocessError(
            "The generated SUMO net has no usable passenger-car edges. "
            "Check that your OSM export includes drivable roads, not only buildings/footpaths."
        )

    pairs = _connected_edge_pairs_from_net(net_file, usable_edges)
    routes: list[tuple[str, list[str]]] = []
    # Prefer two-edge routes if they exist, but keep single-edge fallback for all maps.
    # Use a small set of long/connected routes so traffic is dense enough to be visible
    # and so the incident selector can usually find at least two cars on one lane.
    for i, (src, dst) in enumerate(pairs[:10]):
        routes.append((f"r_pair_{i}", [src, dst]))
    for i, edge_id in enumerate(usable_edges[:10]):
        routes.append((f"r_edge_{i}", [edge_id]))

    if not routes:
        raise SumoPreprocessError("No route can be written because no usable edge was found.")

    # Make many vehicles, with early departures, but avoid overloading tiny maps.
    safe_period = max(0.2, float(period_s))
    count_by_end = int(max(1, end_s / safe_period))
    vehicle_count = max(30, min(max(target_vehicle_count, count_by_end), 2000))

    with route_file.open("w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<routes>\n')
        f.write('    <vType id="car" vClass="passenger" accel="2.6" decel="4.5" sigma="0.5" length="4.5" minGap="2.5" maxSpeed="13.9" color="0,0,255"/>\n')
        for route_id, edge_ids in routes:
            f.write(f'    <route id="{route_id}" edges="{" ".join(edge_ids)}"/>\n')
        for i in range(vehicle_count):
            depart = i * safe_period
            if depart > end_s:
                # Keep extra vehicles inside the first part of the simulation instead of after GUI stop time.
                depart = (i % max(1, int(end_s / safe_period))) * safe_period
            route_id = routes[i % len(routes)][0]
            f.write(
                f'    <vehicle id="veh_{i}" type="car" route="{route_id}" '
                f'depart="{depart:.2f}" departLane="best" departSpeed="max" departPos="random_free"/>\n'
            )
        f.write('</routes>\n')

    print(
        f"[FALLBACK] Wrote {vehicle_count} visible passenger vehicles to {route_file} "
        f"using {len(routes)} route(s)."
    )
    return route_file


def make_random_routes(
    net_file: str | Path,
    route_file: str | Path,
    end_s: int = 600,
    period_s: float = 1.0,
    seed: int = 42,
    min_vehicles: int = 30,
    force_fallback: bool = False,
) -> Path:
    """Create routes and guarantee at least some visible cars.

    Strategy:
      1. Try randomTrips with passenger-only options.
      2. If it fails or produces too few vehicles, retry with more permissive settings.
      3. If still empty, write deterministic single-edge fallback routes.
    """
    add_sumo_tools_to_path()
    route_file = Path(route_file)
    route_file.parent.mkdir(parents=True, exist_ok=True)

    if force_fallback:
        return _write_fallback_single_edge_routes(
            net_file=net_file,
            route_file=route_file,
            end_s=end_s,
            period_s=period_s,
            target_vehicle_count=min_vehicles,
        )

    try:
        random_trips = _find_random_trips_script()
    except RuntimeError as exc:
        print(f"[WARN] {exc}")
        print("[WARN] Falling back to deterministic visible routes.")
        return _write_fallback_single_edge_routes(net_file, route_file, end_s, period_s, min_vehicles)

    trip_file = route_file.with_name(route_file.name.replace(".rou.xml", ".trips.xml"))

    attempts = [
        [
            sys.executable,
            str(random_trips),
            "-n", str(net_file),
            "-o", str(trip_file),
            "-r", str(route_file),
            "-b", "0",
            "-e", str(end_s),
            "--period", str(period_s),
            "--seed", str(seed),
            "--validate",
            "--vehicle-class", "passenger",
            "--edge-permission", "passenger",
            "--fringe-factor", "10",
            "--min-distance", "20",
        ],
        [
            sys.executable,
            str(random_trips),
            "-n", str(net_file),
            "-o", str(trip_file),
            "-r", str(route_file),
            "-b", "0",
            "-e", str(end_s),
            "--period", str(max(0.2, period_s / 2.0)),
            "--seed", str(seed),
            "--validate",
            "--vehicle-class", "passenger",
            "--edge-permission", "passenger",
            "--fringe-factor", "1",
            "--min-distance", "1",
        ],
    ]

    for idx, cmd in enumerate(attempts, start=1):
        if route_file.exists():
            route_file.unlink()
        proc = run_cmd(cmd, allow_fail=True)
        vehicle_count = _xml_vehicle_count(route_file)
        print(f"[CHECK] randomTrips attempt {idx}: return_code={proc.returncode}, vehicles={vehicle_count}")
        if proc.returncode == 0 and vehicle_count >= min_vehicles:
            print(f"[OK] Route file created with {vehicle_count} vehicles: {route_file}")
            return route_file

    print(
        f"[WARN] randomTrips did not create at least {min_vehicles} vehicles. "
        "Writing deterministic visible fallback routes instead."
    )
    return _write_fallback_single_edge_routes(net_file, route_file, end_s, period_s, min_vehicles)


def write_sumocfg(
    net_file: str | Path,
    route_file: str | Path,
    sumocfg_file: str | Path,
    end_s: int = 600,
    step_length_s: float = 0.1,
) -> Path:
    sumocfg_file = Path(sumocfg_file)
    sumocfg_file.parent.mkdir(parents=True, exist_ok=True)

    # SUMO resolves paths inside .sumocfg relative to the .sumocfg folder.
    # Therefore, write paths relative to the folder containing the config file.
    cfg_dir = sumocfg_file.parent.resolve()
    net_value = os.path.relpath(Path(net_file).resolve(), start=cfg_dir)
    route_value = os.path.relpath(Path(route_file).resolve(), start=cfg_dir)

    text = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{net_value}"/>
        <route-files value="{route_value}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{end_s}"/>
        <step-length value="{step_length_s}"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <collision.check-junctions value="true"/>
        <time-to-teleport value="-1"/>
    </processing>
</configuration>
"""
    sumocfg_file.write_text(text, encoding="utf-8")
    return sumocfg_file


def summarize_sumo_files(net_file: str | Path, route_file: str | Path) -> dict[str, int]:
    usable_edges = _usable_edges_from_net(net_file) if Path(net_file).exists() else []
    return {
        "usable_passenger_edges": len(usable_edges),
        "vehicles": _xml_vehicle_count(route_file),
    }


def preprocess_osm(
    osm_file: str | Path,
    out_dir: str | Path,
    map_name: str,
    end_s: int,
    period_s: float,
    seed: int,
    step_length_s: float,
    min_vehicles: int = 30,
    force_fallback: bool = False,
) -> Path:
    out_dir = Path(out_dir)
    net_file = out_dir / f"{map_name}.net.xml"
    route_file = out_dir / f"{map_name}.rou.xml"
    sumocfg_file = out_dir / f"{map_name}.sumocfg"
    osm_to_sumo_net(osm_file, net_file)
    make_random_routes(
        net_file,
        route_file,
        end_s=end_s,
        period_s=period_s,
        seed=seed,
        min_vehicles=min_vehicles,
        force_fallback=force_fallback,
    )
    write_sumocfg(net_file, route_file, sumocfg_file, end_s=end_s, step_length_s=step_length_s)
    summary = summarize_sumo_files(net_file, route_file)
    print(
        "[SUMMARY] "
        f"usable_passenger_edges={summary['usable_passenger_edges']}, "
        f"vehicles={summary['vehicles']}, "
        f"sumocfg={sumocfg_file}"
    )
    return sumocfg_file
