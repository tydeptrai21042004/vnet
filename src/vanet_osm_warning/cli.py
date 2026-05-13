from __future__ import annotations

import argparse
from pathlib import Path

from .config import ProjectConfig
from .metrics import ensure_dir, write_summary_csv
from .plots import plot_all_trajectories
from .report import write_markdown_report
from .sumo_tools import download_osm_by_bbox, preprocess_osm
from .synthetic_runner import SyntheticPlatoonRunner
from .traci_runner import SumoTraciRunner


def run_demo(args: argparse.Namespace) -> None:
    cfg = ProjectConfig.load(args.config)
    out_dir = ensure_dir(args.out)
    metrics = []
    runner = SyntheticPlatoonRunner(cfg.global_cfg, seed=int(cfg.global_cfg.get("seed", 42)))
    for case in cfg.cases:
        if args.case and case["id"] != args.case:
            continue
        sim_cfg = cfg.merged_synthetic_for_case(case)
        channel_cfg = cfg.merged_channel_for_case(case)
        print(f"[DEMO] Running {case['id']}")
        metrics.append(runner.run_case(case, sim_cfg, channel_cfg, out_dir))
    write_summary_csv(metrics, out_dir / "summary_metrics.csv")
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
    )
    print(f"[OK] SUMO config created: {sumocfg}")


def simulate_sumo(args: argparse.Namespace) -> None:
    cfg = ProjectConfig.load(args.config)
    out_dir = ensure_dir(args.out)
    metrics = []
    runner = SumoTraciRunner(cfg.global_cfg, seed=int(cfg.global_cfg.get("seed", 42)), gui=args.gui)
    for case in cfg.cases:
        if args.case and case["id"] != args.case:
            continue
        channel_cfg = cfg.merged_channel_for_case(case)
        print(f"[SUMO] Running {case['id']}")
        metrics.append(runner.run_case(case, args.sumocfg, channel_cfg, out_dir))
    write_summary_csv(metrics, out_dir / "summary_metrics.csv")
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
