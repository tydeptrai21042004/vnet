from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import ProjectConfig
from .aggregation import aggregate_replications
from .metrics import ensure_dir, write_result_exports
from .plots import plot_all_trajectories
from .behavior_viz import generate_behavior_visualizations
from .report import write_markdown_report
from .sumo_tools import download_osm_by_bbox, preprocess_osm
from .synthetic_runner import SyntheticPlatoonRunner
from .traci_runner import SumoTraciRunner

logger = logging.getLogger(__name__)


def _resolve_seeds(cfg: ProjectConfig, seeds_arg: str | None) -> list[int]:
    if seeds_arg:
        return [int(x.strip()) for x in seeds_arg.split(",") if x.strip()]
    configured = cfg.global_cfg.get("seeds")
    if configured:
        return [int(x) for x in configured]
    return [int(cfg.global_cfg.get("seed", 42))]


def run_demo(args: argparse.Namespace) -> None:
    cfg = ProjectConfig.load(args.config)
    out_dir = ensure_dir(args.out)
    all_metrics = []
    seeds = _resolve_seeds(cfg, getattr(args, "seeds", None))
    for seed in seeds:
        seed_dir = ensure_dir(out_dir / "replications" / f"seed_{seed}") if len(seeds) > 1 else out_dir
        for case in cfg.cases:
            if args.case and case["id"] != args.case:
                continue
            runner = SyntheticPlatoonRunner(cfg.global_cfg, seed=seed)  # common random numbers across cases
            logger.info("[DEMO seed=%s] Running %s", seed, case["id"])
            all_metrics.append(runner.run_case(case, cfg.merged_synthetic_for_case(case), cfg.merged_channel_for_case(case), seed_dir, v2i_cfg=cfg.merged_v2i_for_case(case), rsus_cfg=cfg.rsus_for_case(case)))
    metrics, replication_df = aggregate_replications(all_metrics) if len(seeds) > 1 else (all_metrics, None)
    if replication_df is not None:
        replication_df.to_csv(out_dir / "multi_seed_statistics.csv", index=False)
    write_result_exports(metrics, out_dir)
    write_markdown_report(metrics, out_dir / "summary_report.md")
    plot_source = out_dir if len(seeds) == 1 else out_dir / "replications" / f"seed_{seeds[0]}"
    plot_all_trajectories(plot_source)
    generate_behavior_visualizations(plot_source, config_path=args.config)
    logger.info("[OK] Demo results saved to: %s", out_dir)


def preprocess(args: argparse.Namespace) -> None:
    out_dir = ensure_dir(args.out)
    osm_file = args.osm_file
    if args.bbox:
        south, west, north, east = [float(x) for x in args.bbox.split(",")]
        osm_file = out_dir / f"{args.map_name}.osm.xml"
        logger.info("[OSM] Downloading bbox south=%s west=%s north=%s east=%s", south, west, north, east)
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
    logger.info("[OK] SUMO config created: %s", sumocfg)


def simulate_sumo(args: argparse.Namespace) -> None:
    cfg = ProjectConfig.load(args.config)
    out_dir = ensure_dir(args.out)
    all_metrics = []
    seeds = _resolve_seeds(cfg, getattr(args, "seeds", None))
    for seed in seeds:
        seed_dir = ensure_dir(out_dir / "replications" / f"seed_{seed}") if len(seeds) > 1 else out_dir
        for case in cfg.cases:
            if args.case and case["id"] != args.case:
                continue
            runner = SumoTraciRunner(cfg.global_cfg, seed=seed, gui=args.gui)
            case_runtime = dict(case)
            case_runtime["sumo_fixed_incident"] = cfg.sumo_incident_for_case(case)
            logger.info("[SUMO seed=%s] Running %s", seed, case_runtime["id"])
            all_metrics.append(runner.run_case(case_runtime, args.sumocfg, cfg.merged_channel_for_case(case_runtime), seed_dir, v2i_cfg=cfg.merged_v2i_for_case(case_runtime), rsus_cfg=cfg.rsus_for_case(case_runtime)))
    metrics, replication_df = aggregate_replications(all_metrics) if len(seeds) > 1 else (all_metrics, None)
    if replication_df is not None:
        replication_df.to_csv(out_dir / "multi_seed_statistics.csv", index=False)
    write_result_exports(metrics, out_dir)
    write_markdown_report(metrics, out_dir / "summary_report.md")
    plot_all_trajectories(out_dir if len(seeds) == 1 else out_dir / "replications" / f"seed_{seeds[0]}")
    logger.info("[OK] SUMO results saved to: %s", out_dir)


def run_osm(args: argparse.Namespace) -> None:
    preprocess(args)
    sumocfg = Path(args.out) / f"{args.map_name}.sumocfg"
    sim_args = argparse.Namespace(
        config=args.config,
        sumocfg=str(sumocfg),
        out=args.results,
        gui=args.gui,
        case=args.case,
        seeds=getattr(args, "seeds", None),
    )
    simulate_sumo(sim_args)


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Modular VANET accident-warning simulation with OSM/SUMO support")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="Run pure-Python demo cases without SUMO")
    d.add_argument("--config", default="configs/default_cases.json")
    d.add_argument("--out", default="results/demo")
    d.add_argument("--case", default=None)
    d.add_argument("--seeds", default=None, help="Comma-separated seeds; all cases use the same seed within each replication")
    d.set_defaults(func=run_demo)

    ns = sub.add_parser("no-sumo", help="Run the pure-Python cases and generate Excel, plots, and behavioral replays without SUMO")
    ns.add_argument("--config", default="configs/no_sumo_30_cases.json")
    ns.add_argument("--out", default="results/no_sumo_30_cases")
    ns.add_argument("--case", default=None, help="Optional single case ID; omit to run all configured cases")
    ns.add_argument("--seeds", default="42", help="Comma-separated seeds; use one seed for behavioral replay")
    ns.set_defaults(func=run_demo)

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
    sim.add_argument("--seeds", default=None, help="Comma-separated seeds")
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
    ro.add_argument("--seeds", default=None, help="Comma-separated seeds")
    ro.set_defaults(func=run_osm)

    pl = sub.add_parser("plot", help="Regenerate plots from result CSV files")
    pl.add_argument("--results", default="results/demo")
    pl.set_defaults(func=lambda args: plot_all_trajectories(args.results))

    vz = sub.add_parser("visualize-no-sumo", help="Regenerate behavioral replays from NO-SUMO CSV results")
    vz.add_argument("--results", default="results/no_sumo_30_cases")
    vz.add_argument("--frame-step", type=float, default=0.25)
    vz.add_argument("--config", default="configs/no_sumo_30_cases.json")
    vz.set_defaults(func=lambda args: generate_behavior_visualizations(args.results, args.frame_step, args.config))
    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    parser = make_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
