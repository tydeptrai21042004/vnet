from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import ensure_dir


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError):
        return pd.DataFrame()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _downsample_trajectories(df: pd.DataFrame, frame_step_s: float = 0.25) -> pd.DataFrame:
    if df.empty or "time_s" not in df.columns:
        return df
    out = df.copy()
    out["time_s"] = pd.to_numeric(out["time_s"], errors="coerce")
    out = out.dropna(subset=["time_s", "vehicle_id", "x_m", "y_m"])
    if out.empty:
        return out
    frame_step_s = max(float(frame_step_s), 0.05)
    out["frame"] = np.round(out["time_s"] / frame_step_s).astype(int)
    return out.sort_values("time_s").drop_duplicates(["frame", "vehicle_id"], keep="last")


def _event_payload(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events.empty:
        return []
    keep_events = {
        "incident_started", "v2v_packet_sent", "v2v_packet_lost",
        "v2i_packet_sent", "v2i_packet_lost", "warning_received",
        "duplicate_warning_ignored", "collision", "visual_danger_detected_network",
        "target_receivers_selected", "v2i_rsu_selected",
    }
    rows: list[dict[str, Any]] = []
    for _, row in events[events.get("event", pd.Series(dtype=str)).isin(keep_events)].iterrows():
        item = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        item["time_s"] = _safe_float(item.get("time_s"))
        if item.get("deliver_time_s") is not None:
            item["deliver_time_s"] = _safe_float(item.get("deliver_time_s"))
        rows.append(item)
    return rows


def _write_case_replay(traj_csv: Path, events_csv: Path, out_dir: Path, frame_step_s: float, case_meta: dict[str, Any] | None = None) -> Path | None:
    traj = _downsample_trajectories(_read_csv(traj_csv), frame_step_s)
    if traj.empty:
        return None
    events = _read_csv(events_csv)
    case_id = traj_csv.stem.replace("trajectories_", "")

    bool_cols = ["warning_received", "is_incident_vehicle"]
    for col in bool_cols:
        if col not in traj.columns:
            traj[col] = False
        traj[col] = traj[col].astype(str).str.lower().isin({"true", "1", "yes"})

    frames: dict[str, list[dict[str, Any]]] = {}
    for frame, group in traj.groupby("frame", sort=True):
        frames[str(int(frame))] = [
            {
                "id": str(r.vehicle_id),
                "x": _safe_float(r.x_m),
                "y": _safe_float(r.y_m),
                "speed": _safe_float(getattr(r, "speed_mps", 0.0)),
                "warned": bool(getattr(r, "warning_received", False)),
                "incident": bool(getattr(r, "is_incident_vehicle", False)),
            }
            for r in group.itertuples(index=False)
        ]

    x_min, x_max = float(traj["x_m"].min()), float(traj["x_m"].max())
    y_min, y_max = float(traj["y_m"].min()), float(traj["y_m"].max())
    pad_x = max((x_max - x_min) * 0.05, 10.0)
    pad_y = max((y_max - y_min) * 0.05, 10.0)
    case_meta = case_meta or {}
    payload = {
        "caseId": case_id,
        "caseMeta": case_meta,
        "frameStep": frame_step_s,
        "bounds": [x_min - pad_x, x_max + pad_x, y_min - pad_y, y_max + pad_y],
        "frames": frames,
        "events": _event_payload(events),
    }
    data_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VANET behavioral replay - {case_id}</title>
<style>
:root{{--bg:#0b1020;--panel:#121a2e;--text:#e8eefc;--muted:#9fb0d0;--accent:#4da3ff;--warn:#ffd166;--incident:#ff5d73;--normal:#9fb0d0;--line:#263452}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px system-ui,Segoe UI,sans-serif}}
header{{padding:16px 20px;border-bottom:1px solid var(--line)}} h1{{font-size:20px;margin:0 0 5px}} .sub{{color:var(--muted)}}
main{{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:14px;padding:14px;height:calc(100vh - 78px)}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}} #canvasWrap{{position:relative;min-height:520px}} canvas{{width:100%;height:100%;display:block}}
.controls{{position:absolute;left:12px;right:12px;bottom:12px;background:#0b1020dd;border:1px solid var(--line);border-radius:10px;padding:10px;display:grid;grid-template-columns:auto 1fr auto auto;gap:10px;align-items:center}}
button,select{{background:#1d2945;color:var(--text);border:1px solid #34496f;border-radius:7px;padding:7px 10px}} input[type=range]{{width:100%}}
.side{{display:grid;grid-template-rows:auto auto 1fr;gap:12px;padding:12px;overflow:auto}} .cards{{display:grid;grid-template-columns:1fr 1fr;gap:8px}} .card{{background:#0d1528;border:1px solid var(--line);border-radius:8px;padding:9px}} .value{{font-size:20px;font-weight:700}} .label{{font-size:12px;color:var(--muted)}}
.legend{{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted)}} .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}}
.event{{padding:7px 0;border-bottom:1px solid #22304c}} .event b{{color:#dbe8ff}} .event small{{color:var(--muted)}}
@media(max-width:900px){{main{{grid-template-columns:1fr;height:auto}}#canvasWrap{{height:65vh}}}}
</style></head>
<body><header><h1>VANET behavioral replay</h1><div class="sub">Case: <b>{case_id}</b> · <span id="caseMeta"></span></div></header>
<main><section id="canvasWrap" class="panel"><canvas id="sim"></canvas><div class="controls"><button id="play">▶ Play</button><input id="slider" type="range" min="0" max="1" value="0"><span id="clock">0.0 s</span><select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></div></section>
<aside class="panel side"><div class="legend"><span><i class="dot" style="background:var(--normal)"></i>Normal</span><span><i class="dot" style="background:var(--warn)"></i>Warned</span><span><i class="dot" style="background:var(--incident)"></i>Incident</span><span>Lines = packet transmissions</span></div><div class="cards"><div class="card"><div id="vehicles" class="value">0</div><div class="label">Active vehicles</div></div><div class="card"><div id="warned" class="value">0</div><div class="label">Warned vehicles</div></div><div class="card"><div id="avgSpeed" class="value">0</div><div class="label">Average speed (m/s)</div></div><div class="card"><div id="packets" class="value">0</div><div class="label">Packets sent so far</div></div></div><div><h3>Event timeline</h3><div id="events"></div></div></aside></main>
<script>
const D={data_json}; document.getElementById('caseMeta').textContent=[D.caseMeta.protocol,D.caseMeta.experiment_group,D.caseMeta.varied_factor,D.caseMeta.factor_value].filter(Boolean).join(' · ') || 'generated from non-GUI SUMO result CSV files'; const canvas=document.getElementById('sim'),ctx=canvas.getContext('2d');
const keys=Object.keys(D.frames).map(Number).sort((a,b)=>a-b), maxFrame=keys.length?keys[keys.length-1]:0;
const slider=document.getElementById('slider'); slider.max=maxFrame; let frame=0,playing=false,last=0;
function resize(){{const r=canvas.getBoundingClientRect();canvas.width=Math.max(640,Math.floor(r.width*devicePixelRatio));canvas.height=Math.max(480,Math.floor(r.height*devicePixelRatio));draw()}} addEventListener('resize',resize);
function pos(v){{const [xmin,xmax,ymin,ymax]=D.bounds;return [((v.x-xmin)/(xmax-xmin))*canvas.width,canvas.height-((v.y-ymin)/(ymax-ymin))*canvas.height]}}
function vehicleAt(id,f){{const a=D.frames[String(f)]||[];return a.find(v=>String(v.id)===String(id))}}
function drawGrid(){{ctx.strokeStyle='#1c2944';ctx.lineWidth=1;for(let i=1;i<10;i++){{ctx.beginPath();ctx.moveTo(i*canvas.width/10,0);ctx.lineTo(i*canvas.width/10,canvas.height);ctx.stroke();ctx.beginPath();ctx.moveTo(0,i*canvas.height/10);ctx.lineTo(canvas.width,i*canvas.height/10);ctx.stroke()}}}}
function draw(){{ctx.clearRect(0,0,canvas.width,canvas.height);drawGrid();const cars=D.frames[String(frame)]||[];const now=frame*D.frameStep;
 const transmissions=D.events.filter(e=>(e.event==='v2v_packet_sent'||e.event==='v2i_packet_sent')&&e.time_s<=now&&now-e.time_s<0.8);
 for(const e of transmissions){{const a=vehicleAt(e.sender,frame),b=vehicleAt(e.receiver,frame);if(a&&b){{const p=pos(a),q=pos(b);ctx.strokeStyle=e.event.startsWith('v2i')?'#80ed99':'#4da3ff';ctx.lineWidth=2*devicePixelRatio;ctx.globalAlpha=Math.max(0.15,1-(now-e.time_s)/0.8);ctx.beginPath();ctx.moveTo(...p);ctx.lineTo(...q);ctx.stroke();ctx.globalAlpha=1}}}}
 for(const v of cars){{const [x,y]=pos(v);ctx.beginPath();ctx.arc(x,y,(v.incident?8:6)*devicePixelRatio,0,Math.PI*2);ctx.fillStyle=v.incident?'#ff5d73':v.warned?'#ffd166':'#9fb0d0';ctx.fill();ctx.strokeStyle='#0b1020';ctx.lineWidth=1.5*devicePixelRatio;ctx.stroke();if(v.incident){{ctx.beginPath();ctx.arc(x,y,14*devicePixelRatio,0,Math.PI*2);ctx.strokeStyle='#ff5d73';ctx.stroke()}}}}
 document.getElementById('clock').textContent=now.toFixed(1)+' s';document.getElementById('vehicles').textContent=cars.length;document.getElementById('warned').textContent=cars.filter(v=>v.warned).length;document.getElementById('avgSpeed').textContent=(cars.reduce((s,v)=>s+v.speed,0)/Math.max(cars.length,1)).toFixed(1);document.getElementById('packets').textContent=D.events.filter(e=>(e.event==='v2v_packet_sent'||e.event==='v2i_packet_sent')&&e.time_s<=now).length;
 const recent=D.events.filter(e=>e.time_s<=now&&now-e.time_s<=6).slice(-12).reverse();document.getElementById('events').innerHTML=recent.map(e=>`<div class="event"><b>${{e.event}}</b><br><small>${{e.time_s.toFixed(2)}} s${{e.protocol?' · '+e.protocol:''}}${{e.sender?' · '+e.sender+' → '+e.receiver:''}}</small></div>`).join('')||'<div class="sub">No recent event</div>'}}
function tick(t){{if(playing){{const rate=Number(document.getElementById('speed').value);if(t-last>Math.max(20,1000*D.frameStep/rate)){{frame=frame>=maxFrame?0:frame+1;slider.value=frame;draw();last=t}}requestAnimationFrame(tick)}}}}
document.getElementById('play').onclick=()=>{{playing=!playing;document.getElementById('play').textContent=playing?'❚❚ Pause':'▶ Play';if(playing)requestAnimationFrame(tick)}};slider.oninput=()=>{{frame=Number(slider.value);draw()}};resize();
</script></body></html>'''
    out = out_dir / f"replay_{case_id}.html"
    out.write_text(html, encoding="utf-8")
    return out


def _plot_warning_propagation(results_dir: Path, out_dir: Path) -> None:
    plt.figure(figsize=(12, 6))
    plotted = False
    for event_file in sorted(results_dir.glob("events_*.csv")):
        events = _read_csv(event_file)
        if events.empty or "event" not in events.columns:
            continue
        got = events[events["event"] == "warning_received"].copy()
        if got.empty:
            continue
        got["time_s"] = pd.to_numeric(got["time_s"], errors="coerce")
        got = got.dropna(subset=["time_s"]).sort_values("time_s")
        got["cumulative_warned"] = np.arange(1, len(got) + 1)
        case_id = event_file.stem.replace("events_", "")
        plt.step(got["time_s"], got["cumulative_warned"], where="post", label=case_id)
        plotted = True
    if plotted:
        plt.xlabel("Simulation time (s)")
        plt.ylabel("Cumulative warned vehicles")
        plt.title("Warning propagation behavior by protocol/setup")
        plt.legend(fontsize=7, ncol=2)
        plt.tight_layout()
        plt.savefig(out_dir / "behavior_warning_propagation.png", dpi=180)
    plt.close()


def _plot_speed_response(results_dir: Path, out_dir: Path) -> None:
    plt.figure(figsize=(12, 6))
    plotted = False
    for traj_file in sorted(results_dir.glob("trajectories_*.csv")):
        traj = _read_csv(traj_file)
        if traj.empty or not {"time_s", "speed_mps"}.issubset(traj.columns):
            continue
        agg = traj.groupby("time_s", as_index=False)["speed_mps"].mean()
        case_id = traj_file.stem.replace("trajectories_", "")
        plt.plot(agg["time_s"], agg["speed_mps"], label=case_id, linewidth=1.4)
        plotted = True
    if plotted:
        plt.xlabel("Simulation time (s)")
        plt.ylabel("Fleet mean speed (m/s)")
        plt.title("Traffic response after incident and warning")
        plt.legend(fontsize=7, ncol=2)
        plt.tight_layout()
        plt.savefig(out_dir / "behavior_fleet_speed_response.png", dpi=180)
    plt.close()


def _load_case_catalog(config_path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not config_path:
        return {}
    path = Path(config_path)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    protocols = raw.get("protocols", {})
    channel_default = raw.get("channel_default", {})
    v2i_default = raw.get("v2i_default", {})
    synthetic = raw.get("synthetic_platoon", {})
    catalog: dict[str, dict[str, Any]] = {}
    for case in raw.get("cases", []):
        mode = str(case.get("communication_mode", "none"))
        pname = case.get("protocol") or case.get("v2i_protocol") or "NONE"
        section = dict(v2i_default if mode == "v2i" else channel_default)
        section.update(protocols.get(pname, {}))
        section.update(case.get("v2i", {}) if mode == "v2i" else case.get("channel", {}))
        syn = dict(synthetic)
        syn.update(case.get("synthetic_override", {}))
        catalog[str(case.get("id"))] = {
            "name": case.get("name", case.get("id")),
            "description_vi": case.get("description_vi", ""),
            "protocol": pname,
            "mode": mode,
            "experiment_group": case.get("experiment_group", "Other cases"),
            "varied_factor": case.get("varied_factor", "setup"),
            "factor_value": case.get("factor_value", "reference"),
            "packet_size_bytes": section.get("packet_size_bytes"),
            "communication_range_m": section.get("communication_range_m", section.get("rsu_range_m")),
            "loss_probability": section.get("loss_probability"),
            "bit_error_rate": section.get("bit_error_rate"),
            "base_delay_s": section.get("base_delay_s"),
            "queue_delay_s": section.get("queue_delay_s"),
            "rebroadcast_delay_s": section.get("rebroadcast_delay_s"),
            "max_hops": section.get("max_hops"),
            "num_vehicles": syn.get("num_vehicles"),
            "control_algorithm": case.get("control_algorithm", "none"),
        }
    return catalog


def _plot_grouped_behavior(results_dir: Path, out_dir: Path, catalog: dict[str, dict[str, Any]]) -> list[Path]:
    generated: list[Path] = []
    groups: dict[str, list[str]] = {}
    for case_id, meta in catalog.items():
        groups.setdefault(str(meta.get("experiment_group", "Other cases")), []).append(case_id)
    for group_name, case_ids in groups.items():
        available = [cid for cid in case_ids if (results_dir / f"events_{cid}.csv").exists()]
        if len(available) < 2:
            continue
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in group_name).strip("_")
        plt.figure(figsize=(11, 6))
        plotted = False
        for cid in available:
            events = _read_csv(results_dir / f"events_{cid}.csv")
            if events.empty or "event" not in events.columns:
                continue
            got = events[events["event"] == "warning_received"].copy()
            if got.empty:
                continue
            got["time_s"] = pd.to_numeric(got["time_s"], errors="coerce")
            got = got.dropna(subset=["time_s"]).sort_values("time_s")
            got["cumulative_warned"] = np.arange(1, len(got) + 1)
            label = f"{cid}: {catalog[cid].get('factor_value', '')}"
            plt.step(got["time_s"], got["cumulative_warned"], where="post", label=label)
            plotted = True
        if plotted:
            plt.xlabel("Simulation time (s)")
            plt.ylabel("Cumulative warned vehicles")
            plt.title(f"{group_name}: warning propagation")
            plt.legend(fontsize=7)
            plt.tight_layout()
            path = out_dir / f"group_{slug}_warning_propagation.png"
            plt.savefig(path, dpi=180)
            generated.append(path)
        plt.close()

        plt.figure(figsize=(11, 6))
        plotted = False
        for cid in available:
            traj = _read_csv(results_dir / f"trajectories_{cid}.csv")
            if traj.empty or not {"time_s", "speed_mps"}.issubset(traj.columns):
                continue
            agg = traj.groupby("time_s", as_index=False)["speed_mps"].mean()
            label = f"{cid}: {catalog[cid].get('factor_value', '')}"
            plt.plot(agg["time_s"], agg["speed_mps"], label=label, linewidth=1.4)
            plotted = True
        if plotted:
            plt.xlabel("Simulation time (s)")
            plt.ylabel("Fleet mean speed (m/s)")
            plt.title(f"{group_name}: vehicle response")
            plt.legend(fontsize=7)
            plt.tight_layout()
            path = out_dir / f"group_{slug}_speed_response.png"
            plt.savefig(path, dpi=180)
            generated.append(path)
        plt.close()
    return generated


def _write_index(files: list[Path], out_dir: Path, catalog: dict[str, dict[str, Any]]) -> Path:
    groups: dict[str, list[Path]] = {}
    for path in files:
        cid = path.stem.replace("replay_", "")
        groups.setdefault(str(catalog.get(cid, {}).get("experiment_group", "Other cases")), []).append(path)
    sections: list[str] = []
    for group, paths in groups.items():
        cards: list[str] = []
        for path in paths:
            cid = path.stem.replace("replay_", "")
            meta = catalog.get(cid, {})
            params: list[str] = []
            fields = (("protocol", "Protocol"), ("packet_size_bytes", "Packet"), ("communication_range_m", "Range"), ("bit_error_rate", "BER"), ("loss_probability", "Base loss"), ("queue_delay_s", "Queue delay"), ("rebroadcast_delay_s", "Rebroadcast"), ("max_hops", "Hops"), ("num_vehicles", "Vehicles"), ("control_algorithm", "Control"))
            for key, label in fields:
                value = meta.get(key)
                if value is not None:
                    params.append(f"<span><b>{label}:</b> {value}</span>")
            cards.append(
                f'<article><h3><a href="{path.name}">{cid}</a></h3>'
                f'<p>{meta.get("name", cid)}</p>'
                f'<div class="factor">Changed factor: <b>{meta.get("varied_factor", "setup")}</b> = {meta.get("factor_value", "reference")}</div>'
                f'<div class="params">{"".join(params)}</div></article>'
            )
        sections.append(f'<section><h2>{group}</h2><div class="grid">{"".join(cards)}</div></section>')
    body = "".join(sections)
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>30-case VANET behavior laboratory</title>
<style>body{{font:15px system-ui;max-width:1500px;margin:30px auto;padding:0 22px;background:#f5f7fb;color:#172033}}h1{{margin-bottom:6px}}.intro{{color:#53627a}}section{{margin:30px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px}}article{{background:white;border:1px solid #dbe2ee;border-radius:12px;padding:15px;box-shadow:0 3px 12px #18243a0d}}h3{{margin:0 0 7px}}a{{color:#1769aa}}p{{min-height:38px}}.factor{{background:#eef5ff;padding:8px;border-radius:7px;margin:8px 0}}.params{{display:flex;flex-wrap:wrap;gap:6px}}.params span{{font-size:12px;background:#f1f3f6;padding:5px 7px;border-radius:999px}}</style></head>
<body><h1>30-case VANET behavior laboratory</h1><p class="intro">Cases are grouped by controlled experiment. Open a replay to see vehicle motion, exact warning order, packet links and losses, visual-danger timing, and braking response. Compare cases inside the same group to attribute behavior to the listed parameter rather than only to the V2V/V2I label.</p>{body}</body></html>'''
    index = out_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    return index


def generate_behavior_visualizations(results_dir: str | Path, frame_step_s: float = 0.25, config_path: str | Path | None = None) -> list[Path]:
    results_dir = Path(results_dir)
    out_dir = ensure_dir(results_dir / "behavior_visualization")
    catalog = _load_case_catalog(config_path)
    replay_files: list[Path] = []
    for traj_csv in sorted(results_dir.glob("trajectories_*.csv")):
        case_id = traj_csv.stem.replace("trajectories_", "")
        replay = _write_case_replay(traj_csv, results_dir / f"events_{case_id}.csv", out_dir, frame_step_s, catalog.get(case_id))
        if replay is not None:
            replay_files.append(replay)
    _plot_warning_propagation(results_dir, out_dir)
    _plot_speed_response(results_dir, out_dir)
    _plot_grouped_behavior(results_dir, out_dir, catalog)
    if replay_files:
        _write_index(replay_files, out_dir, catalog)
    if catalog:
        (out_dir / "case_catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    return replay_files
