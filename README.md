# VANET Road Accident Warning with OpenStreetMap + SUMO

This package is a modular implementation for the thesis topic:

> **Cảnh báo tai nạn giao thông đường bộ sử dụng mạng VANET**

It supports two running modes:

1. **Demo mode**: pure Python platoon simulation, no SUMO required. Use this first to verify the VANET logic, metrics, plots, and reports.
2. **OSM/SUMO mode**: input is an OpenStreetMap `.osm/.osm.xml` map or a bounding box. The pipeline preprocesses the map into SUMO files, runs the VANET warning simulation through TraCI, and generates result plots.

---

## 1. Project structure

```text
vanet_osm_modular/
├── README.md
├── requirements.txt
├── run_vanet_osm_ubuntu.sh
├── main.py
├── configs/
│   └── default_cases.json
├── docs/
│   └── DESIGN.md
├── scripts/
│   └── export_osm_example.md
├── data/
│   ├── osm/                 # Put exported OpenStreetMap files here
│   └── sumo/                # Generated SUMO network/route/config files
├── results/                 # Simulation outputs
└── src/vanet_osm_warning/
    ├── cli.py
    ├── config.py
    ├── models.py
    ├── collision_warning.py
    ├── channel.py
    ├── synthetic_runner.py
    ├── sumo_tools.py
    ├── traci_runner.py
    ├── metrics.py
    ├── plots.py
    └── report.py
```

---

## 2. Quick run on Ubuntu without SUMO

```bash
chmod +x run_vanet_osm_ubuntu.sh
./run_vanet_osm_ubuntu.sh demo
```

Outputs:

```text
results/demo/summary_metrics.csv
results/demo/summary_report.md
results/demo/events_<case_id>.csv
results/demo/trajectories_<case_id>.csv
results/demo/plots/*.png
```

This mode is useful for checking the logic before using a real OpenStreetMap map.

---

## 3. Install SUMO on Ubuntu

```bash
./run_vanet_osm_ubuntu.sh install-sumo
```

Or manually:

```bash
sudo apt update
sudo apt install -y sumo sumo-tools sumo-doc
export SUMO_HOME=/usr/share/sumo
```

Add this to `~/.bashrc`:

```bash
export SUMO_HOME=/usr/share/sumo
```

---

## 4. Run with an OpenStreetMap file

### Step 1: Export a small OSM map

Export from OpenStreetMap and save it as:

```text
data/osm/my_area.osm.xml
```

A small map is recommended. For example, one road segment, one intersection, or a small district block.

### Step 2: Run the full OSM pipeline

```bash
./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm.xml
```

The script will:

1. convert OSM to SUMO network `.net.xml`,
2. generate route file `.rou.xml`,
3. generate SUMO config `.sumocfg`,
4. run all VANET cases,
5. output CSV, Markdown report, and plots.

---

## 5. Run with OSM bounding box

This requires internet and `osmnx`.

```bash
./run_vanet_osm_ubuntu.sh bbox 10.755,106.665,10.765,106.680
```

Format:

```text
south,west,north,east
```

Keep the bounding box small. Large OSM maps can make SUMO conversion slow.

---

## 6. Manual commands

Activate Python path:

```bash
export PYTHONPATH=$PWD/src:$PYTHONPATH
```

Run demo:

```bash
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --out results/demo
```

Preprocess OSM:

```bash
python -m vanet_osm_warning.cli preprocess-osm \
  --osm-file data/osm/my_area.osm.xml \
  --map-name my_area \
  --out data/sumo \
  --end 600 \
  --period 1.0
```

Run SUMO simulation:

```bash
python -m vanet_osm_warning.cli simulate-sumo \
  --config configs/default_cases.json \
  --sumocfg data/sumo/my_area.sumocfg \
  --out results/osm
```

Run SUMO GUI:

```bash
python -m vanet_osm_warning.cli simulate-sumo \
  --config configs/default_cases.json \
  --sumocfg data/sumo/my_area.sumocfg \
  --out results/osm_gui \
  --gui
```

Regenerate plots:

```bash
python -m vanet_osm_warning.cli plot --results results/demo
```

---

## 7. Case design

| Case ID | Description | Purpose |
|---|---|---|
| `C0_normal_no_incident_baseline` | Normal traffic, no sudden braking | Simulation sanity baseline |
| `C1_sudden_brake_no_warning_baseline` | Front vehicle suddenly brakes, no VANET warning | Main baseline |
| `C2_sudden_brake_direct_v2v` | Sudden braking with direct V2V warning | Compare warning vs no warning |
| `C3_platoon_no_warning_baseline` | Long platoon, no warning | Baseline for propagation |
| `C4_platoon_direct_v2v_limited_range` | Long platoon, one-hop V2V only | Show direct V2V limitation |
| `C5_platoon_multihop_broadcast` | Long platoon, multi-hop V2V broadcast | Test warning propagation |
| `C6_v2v_delay_loss_stress` | Warning with high delay/loss | Network stress test |

---

## 8. What to include in the thesis result section

Recommended tables:

1. Collision count by case.
2. Warning PDR by case.
3. Average warning delay by case.
4. Minimum gap by case.
5. Reaction gain by case.

Recommended figures:

1. `summary_collisions_by_case.png`
2. `summary_pdr_by_case.png`
3. `summary_delay_by_case.png`
4. `summary_min_gap_by_case.png`
5. `trajectory_<case_id>.png`
6. `speed_<case_id>.png`

Suggested conclusion:

> Compared with the no-warning baseline, the VANET V2V warning cases reduce the number of collisions and increase reaction time. Direct V2V is effective only when vehicles are inside the communication range. For a long platoon, multi-hop broadcast improves warning coverage. However, high delay and packet loss degrade performance, showing that VANET safety applications require reliable and low-latency communication.
