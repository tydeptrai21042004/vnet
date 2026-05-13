from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


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


def run_cmd(cmd: list[str], cwd: str | Path | None = None) -> None:
    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


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
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("OSMnx is required for bbox download. Install with: pip install osmnx") from exc
    graph = ox.graph_from_bbox(north, south, east, west, network_type="drive", simplify=False)
    ox.save_graph_xml(graph, filepath=str(out_file))
    return out_file


def osm_to_sumo_net(osm_file: str | Path, net_file: str | Path) -> Path:
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
        "--remove-edges.by-vclass", "rail_slow,rail_fast,bicycle,pedestrian",
        "--remove-edges.isolated",
        "--no-turnarounds",
    ]
    run_cmd(cmd)
    return net_file


def make_random_routes(net_file: str | Path, route_file: str | Path, end_s: int = 600, period_s: float = 1.0, seed: int = 42) -> Path:
    add_sumo_tools_to_path()
    route_file = Path(route_file)
    route_file.parent.mkdir(parents=True, exist_ok=True)
    sumo_home = os.environ.get("SUMO_HOME")
    random_trips_candidates = []
    if sumo_home:
        random_trips_candidates.append(Path(sumo_home) / "tools" / "randomTrips.py")
    random_trips_candidates.append(Path("/usr/share/sumo/tools/randomTrips.py"))
    random_trips = next((p for p in random_trips_candidates if p.exists()), None)
    if random_trips is None:
        raise RuntimeError("Cannot find randomTrips.py. Install sumo-tools or set SUMO_HOME.")
    cmd = [
        sys.executable,
        str(random_trips),
        "-n", str(net_file),
        "-r", str(route_file),
        "-e", str(end_s),
        "--period", str(period_s),
        "--seed", str(seed),
        "--validate",
        "--fringe-factor", "5",
    ]
    run_cmd(cmd)
    return route_file


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


def preprocess_osm(osm_file: str | Path, out_dir: str | Path, map_name: str, end_s: int, period_s: float, seed: int, step_length_s: float) -> Path:
    out_dir = Path(out_dir)
    net_file = out_dir / f"{map_name}.net.xml"
    route_file = out_dir / f"{map_name}.rou.xml"
    sumocfg_file = out_dir / f"{map_name}.sumocfg"
    osm_to_sumo_net(osm_file, net_file)
    make_random_routes(net_file, route_file, end_s=end_s, period_s=period_s, seed=seed)
    write_sumocfg(net_file, route_file, sumocfg_file, end_s=end_s, step_length_s=step_length_s)
    return sumocfg_file
