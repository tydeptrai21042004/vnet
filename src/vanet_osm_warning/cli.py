from __future__ import annotations

import argparse
from pathlib import Path

from .config import ProjectConfig
from .metrics import ensure_dir, write_result_exports
from .plots import plot_all_trajectories
from .report import write_markdown_report
from .sumo_tools import download_osm_by_bbox, preprocess_osm
from .synthetic_runner import SyntheticPlatoonRunner
from .traci_runner import SumoTraciRunner


def run_demo(args: argparse.Namespace) -> None:
    cfg = ProjectConfig.load(args.config)
    out_dir = ensure_dir(args.out)
    metrics = []
    base_seed = int(cfg.global_cfg.get("seed", 42))
    for idx, case in enumerate(cfg.cases):
        runner = SyntheticPlatoonRunner(cfg.global_cfg, seed=base_seed + idx)
        if args.case and case["id"] != args.case:
            continue
        sim_cfg = cfg.merged_synthetic_for_case(case)
        channel_cfg = cfg.merged_channel_for_case(case)
        print(f"[DEMO] Running {case['id']}")
        v2i_cfg = cfg.merged_v2i_for_case(case)
        rsus_cfg = cfg.rsus_for_case(case)
        metrics.append(runner.run_case(case, sim_cfg, channel_cfg, out_dir, v2i_cfg=v2i_cfg, rsus_cfg=rsus_cfg))
    write_result_exports(metrics, out_dir)
    write_markdown_report(metrics, out_dir / "summary_report.md")
    plot_all_trajectories(out_dir)
    print(f"[OK] Demo results saved to: {out_dir}")


def preprocess(args: argparse.Namespace) -> None:
    out_dir = ensure_dir(args.out)
    osm_file = args.osm_file
    if args.bbox:
        south, west, north, east = [float(x) for x in args.bbox.split(",")]
        osm_file = out_dir / f"{args.map_name}.osm.xml"
        print(f"[OSM] Downloading bbox south={south}, west={west}, north={north}, east={east}")
        download_osm_by_bbox(south, west, north, east, osm_file)
    if not osm_file:
        raise SystemExit("Provide --osm-file or --bbox south,west,north,east")
    sumocfg = preprocess_osm(
        osm_file=osm_file,
        out_dir=out_dir,
        map_name=args.map_name,
        end_s=args.end,
        period_s=args.period,
        seed=args.seed,
        step_length_s=args.step_length,
        min_vehicles=args.min_vehicles,
        force_fallback=args.force_fallback,
    )
    print(f"[OK] SUMO config created: {sumocfg}")


def simulate_sumo(args: argparse.Namespace) -> None:
    cfg = ProjectConfig.load(args.config)
    out_dir = ensure_dir(args.out)
    metrics = []
    base_seed = int(cfg.global_cfg.get("seed", 42))
    for idx, case in enumerate(cfg.cases):
        runner = SumoTraciRunner(cfg.global_cfg, seed=base_seed + idx, gui=args.gui)
        if args.case and case["id"] != args.case:
            continue
        case_runtime = dict(case)
        case_runtime["sumo_fixed_incident"] = cfg.sumo_incident_for_case(case)
        channel_cfg = cfg.merged_channel_for_case(case_runtime)
        print(f"[SUMO] Running {case_runtime['id']}")
        v2i_cfg = cfg.merged_v2i_for_case(case_runtime)
        rsus_cfg = cfg.rsus_for_case(case_runtime)
        metrics.append(runner.run_case(case_runtime, args.sumocfg, channel_cfg, out_dir, v2i_cfg=v2i_cfg, rsus_cfg=rsus_cfg))
    write_result_exports(metrics, out_dir)
    write_markdown_report(metrics, out_dir / "summary_report.md")
    plot_all_trajectories(out_dir)
    print(f"[OK] SUMO results saved to: {out_dir}")


def run_osm(args: argparse.Namespace) -> None:
    preprocess(args)
    sumocfg = Path(args.out) / f"{args.map_name}.sumocfg"
    sim_args = argparse.Namespace(
        config=args.config,
        sumocfg=str(sumocfg),
        out=args.results,
        gui=args.gui,
        case=args.case,
    )
    simulate_sumo(sim_args)


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Modular VANET accident-warning simulation with OSM/SUMO support")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="Run pure-Python demo cases without SUMO")
    d.add_argument("--config", default="configs/default_cases.json")
    d.add_argument("--out", default="results/demo")
    d.add_argument("--case", default=None)
    d.set_defaults(func=run_demo)

    pre = sub.add_parser("preprocess-osm", help="Convert OpenStreetMap input to SUMO network/routes/config")
    pre.add_argument("--osm-file", default=None, help="Path to exported .osm or .osm.xml file")
    pre.add_argument("--bbox", default=None, help="south,west,north,east. Requires internet + osmnx")
    pre.add_argument("--map-name", default="osm_map")
    pre.add_argument("--out", default="data/sumo")
    pre.add_argument("--end", type=int, default=600)
    pre.add_argument("--period", type=float, default=1.0)
    pre.add_argument("--seed", type=int, default=42)
    pre.add_argument("--step-length", type=float, default=0.1)
    pre.add_argument("--min-vehicles", type=int, default=30, help="Minimum vehicles required in the generated route file before fallback is used")
    pre.add_argument("--force-fallback", action="store_true", help="Skip randomTrips and directly write deterministic visible routes")
    pre.set_defaults(func=preprocess)

    sim = sub.add_parser("simulate-sumo", help="Run VANET cases on a SUMO .sumocfg")
    sim.add_argument("--config", default="configs/default_cases.json")
    sim.add_argument("--sumocfg", required=True)
    sim.add_argument("--out", default="results/osm")
    sim.add_argument("--case", default=None)
    sim.add_argument("--gui", action="store_true")
    sim.set_defaults(func=simulate_sumo)

    ro = sub.add_parser("run-osm", help="Preprocess OSM then run SUMO/TraCI VANET cases")
    ro.add_argument("--config", default="configs/default_cases.json")
    ro.add_argument("--osm-file", default=None)
    ro.add_argument("--bbox", default=None, help="south,west,north,east. Requires internet + osmnx")
    ro.add_argument("--map-name", default="osm_map")
    ro.add_argument("--out", default="data/sumo")
    ro.add_argument("--results", default="results/osm")
    ro.add_argument("--end", type=int, default=600)
    ro.add_argument("--period", type=float, default=1.0)
    ro.add_argument("--seed", type=int, default=42)
    ro.add_argument("--step-length", type=float, default=0.1)
    ro.add_argument("--min-vehicles", type=int, default=30, help="Minimum vehicles required in the generated route file before fallback is used")
    ro.add_argument("--force-fallback", action="store_true", help="Skip randomTrips and directly write deterministic visible routes")
    ro.add_argument("--case", default=None)
    ro.add_argument("--gui", action="store_true")
    ro.set_defaults(func=run_osm)

    pl = sub.add_parser("plot", help="Regenerate plots from result CSV files")
    pl.add_argument("--results", default="results/demo")
    pl.set_defaults(func=lambda args: plot_all_trajectories(args.results))
    return p


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
