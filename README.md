# VANET V2V/V2I Road Accident Warning Simulation with SUMO

This project implements a modular simulation framework for the research topic:

> **Cảnh báo tai nạn giao thông đường bộ sử dụng mạng VANET: mô phỏng V2V, V2I và Hybrid V2V--V2I bằng SUMO/TraCI, đồng thời đánh giá ảnh hưởng của giao thức truyền thông và kích thước gói tin.**

The code supports two execution modes:

1. **Pure Python demo mode**: quick platoon simulation without SUMO. Use this first to verify the communication logic, metrics, packet-size effect, and plots.
2. **SUMO/TraCI mode**: runs the same warning/control cases on a SUMO road network converted from OpenStreetMap.

The implementation now covers the requested research content:

| Research requirement | Implemented? | Where |
|---|---:|---|
| V2V communication mechanism | Yes | `src/vanet_osm_warning/channel.py` |
| SUMO simulation of V2V control algorithms | Yes | `src/vanet_osm_warning/traci_runner.py` |
| Impact of communication protocol and packet size | Yes | `protocol`, `packet_size_bytes`, `data_rate_bps`, `channel_load`, `bytes_sent`, `packet_pdr` |
| Vehicle-to-Infrastructure V2I comparison | Yes | `src/vanet_osm_warning/v2i_channel.py` |
| Hybrid V2V + V2I comparison | Yes | `communication_mode = hybrid` in config |

---

## 1. Main features

### 1.1 Communication modes

The simulator supports four communication modes:

| Mode | Meaning |
|---|---|
| `none` | Accident occurs, but no warning is transmitted. |
| `v2v` | Vehicle-to-Vehicle warning. Supports direct and multi-hop broadcast. |
| `v2i` | Vehicle sends warning to Roadside Unit, then RSU broadcasts warning to vehicles. |
| `hybrid` | V2V and V2I are both active. |

### 1.2 Protocol and packet-size model

Each warning packet has communication parameters:

```json
{
  "protocol": "DSRC_80211p",
  "data_rate_bps": 6000000,
  "base_delay_s": 0.02,
  "processing_delay_s": 0.005,
  "queue_delay_s": 0.0,
  "header_size_bytes": 48,
  "payload_size_bytes": 252,
  "packet_size_bytes": 300,
  "loss_probability": 0.02
}
```

Transmission delay is computed as:

```text
T_tx = 8 * packet_size_bytes / data_rate_bps
```

Total one-hop V2V delay is approximately:

```text
T_v2v = base_delay + T_tx + processing_delay + queue_delay
```

Total V2I delay is approximately:

```text
T_v2i = uplink_delay + RSU_processing_delay + downlink_delay
```

So larger packets increase:

- transmission delay,
- bytes sent,
- channel load,
- communication overhead.

### 1.3 Control algorithms after warning reception

When a vehicle receives a warning, the simulator can apply different control policies:

| Control algorithm | Meaning |
|---|---|
| `preemptive_brake` | Vehicle brakes early with a fixed warning deceleration. |
| `ttc_adaptive` | Vehicle uses a TTC/gap-aware braking rule. This is closer to a simple V2V control algorithm. |
| `emergency_brake` | Vehicle applies strong braking after receiving warning. |

In SUMO mode, these policies are applied through `traci.vehicle.slowDown(...)`.

---

## 2. Project structure

```text
vnet-main/
├── README.md
├── requirements.txt
├── main.py
├── run_vanet_osm_ubuntu.sh
├── run_case_gui.sh
├── configs/
│   ├── default_cases.json
│   └── v2v_v2i_packet_cases.json
├── data/
│   ├── osm/
│   └── sumo/
├── docs/
│   ├── DESIGN.md
│   └── REPORT_TEMPLATE.md
├── scripts/
│   └── export_osm_example.md
└── src/vanet_osm_warning/
    ├── cli.py
    ├── config.py
    ├── models.py
    ├── protocols.py
    ├── channel.py
    ├── v2i_channel.py
    ├── collision_warning.py
    ├── synthetic_runner.py
    ├── traci_runner.py
    ├── sumo_tools.py
    ├── metrics.py
    ├── plots.py
    └── report.py
```

### Important files added or upgraded

| File | Purpose |
|---|---|
| `protocols.py` | Computes protocol/packet-size delay. |
| `v2i_channel.py` | Implements RSU and V2I warning dissemination. |
| `channel.py` | Upgraded V2V channel with packet size, protocol, bytes sent, PDR, and channel load support. |
| `synthetic_runner.py` | Now supports `none`, `v2v`, `v2i`, and `hybrid`. |
| `traci_runner.py` | SUMO/TraCI support for V2V, V2I, hybrid, and control algorithms. |
| `configs/default_cases.json` | Full V2V/V2I/packet-size experiment matrix. |

---

## 3. Installation

### 3.1 Create environment

```bash
cd vnet-main
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export PYTHONPATH=$PWD/src:$PYTHONPATH
```

### 3.2 Install SUMO on Ubuntu

```bash
sudo apt update
sudo apt install -y sumo sumo-tools sumo-doc
export SUMO_HOME=/usr/share/sumo
```

Add to `~/.bashrc`:

```bash
export SUMO_HOME=/usr/share/sumo
```

---

## 4. Quick run without SUMO

Run the full demo experiment:

```bash
chmod +x run_vanet_osm_ubuntu.sh
./run_vanet_osm_ubuntu.sh demo
```

Or manually:

```bash
export PYTHONPATH=$PWD/src:$PYTHONPATH
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --out results/demo
```

Outputs:

```text
results/demo/summary_metrics.csv
results/demo/summary_report.md
results/demo/events_<case_id>.csv
results/demo/trajectories_<case_id>.csv
results/demo/plots/*.png
```

---

## 5. Run a single case

Example: run only the hybrid V2V+V2I case.

```bash
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --out results/hybrid_only \
  --case C5_hybrid_v2v_v2i_300B
```

Example: run only the V2I packet-size stress case.

```bash
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --out results/v2i_1400B \
  --case C11_v2i_packet_1400B
```

---

## 6. SUMO / OpenStreetMap mode

### 6.1 Use an exported OSM file

Put your OSM map here:

```text
data/osm/my_area.osm.xml
```

Then run:

```bash
./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm.xml
```

This performs:

1. OSM to SUMO network conversion.
2. Route generation.
3. SUMO configuration generation.
4. SUMO/TraCI simulation for all cases.
5. CSV, Markdown, and plot generation.

### 6.2 Manual SUMO commands

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

Or use the interactive GUI runner:

```bash
chmod +x run_case_gui.sh
./run_case_gui.sh
```

---

## 7. Experiment cases

The default config contains these cases:

| Case ID | Mode | Purpose |
|---|---|---|
| `C0_normal_no_incident` | none | Normal traffic sanity check. |
| `C1_accident_no_warning` | none | Accident baseline without warning. |
| `C2_v2v_direct_dsrc_300B` | V2V | Direct one-hop V2V warning. |
| `C3_v2v_multihop_dsrc_300B` | V2V | Multi-hop V2V warning. |
| `C4_v2i_lte_5g_300B` | V2I | RSU-based V2I warning. |
| `C5_hybrid_v2v_v2i_300B` | Hybrid | Combined V2V and V2I warning. |
| `C6_v2v_multihop_packet_100B` | V2V | Packet-size test: 100 bytes. |
| `C7_v2v_multihop_packet_600B` | V2V | Packet-size test: 600 bytes. |
| `C8_v2v_multihop_packet_1400B` | V2V | Packet-size test: 1400 bytes. |
| `C9_v2i_packet_100B` | V2I | V2I packet-size test: 100 bytes. |
| `C10_v2i_packet_600B` | V2I | V2I packet-size test: 600 bytes. |
| `C11_v2i_packet_1400B` | V2I | V2I packet-size test: 1400 bytes. |
| `C12_v2v_cv2x_packet_600B` | V2V | Protocol comparison: C-V2X-like V2V. |

---

## 8. How to compare V2V and V2I

Use the same accident scenario and compare these cases:

```text
C1_accident_no_warning
C2_v2v_direct_dsrc_300B
C3_v2v_multihop_dsrc_300B
C4_v2i_lte_5g_300B
C5_hybrid_v2v_v2i_300B
```

Recommended comparison table:

| Metric | Meaning | Better value |
|---|---|---|
| `collisions` | Number of collision events | lower |
| `receiver_coverage` | Warned target vehicles / target vehicles | higher |
| `packet_pdr` | Delivered packets / sent packets | higher |
| `avg_delay_s` | Average warning delay | lower |
| `max_delay_s` | Worst warning delay | lower |
| `bytes_sent` | Communication overhead | lower |
| `channel_load` | Estimated used channel capacity | lower |
| `min_gap_m` | Minimum bumper-to-bumper gap | higher |

Important distinction:

```text
packet_pdr = warnings_delivered / warnings_sent
receiver_coverage = unique_warning_receivers / target_receivers
```

These are not the same. A system can have many dropped packets but still warn every vehicle if there are redundant transmissions.

---

## 9. How to evaluate packet-size impact

Use these cases:

```text
C6_v2v_multihop_packet_100B
C7_v2v_multihop_packet_600B
C8_v2v_multihop_packet_1400B
C9_v2i_packet_100B
C10_v2i_packet_600B
C11_v2i_packet_1400B
```

After running the demo, check:

```text
results/demo/summary_metrics.csv
results/demo/plots/packet_size_vs_delay.png
results/demo/plots/packet_size_vs_packet_pdr.png
results/demo/plots/summary_bytes_sent_by_case.png
results/demo/plots/summary_channel_load_by_case.png
```

In the report, explain:

- Larger packet size increases `bytes_sent`.
- Larger packet size increases `channel_load`.
- Larger packet size increases theoretical transmission delay.
- Under packet loss, larger overhead can reduce communication efficiency.
- Safety impact should be discussed through `collisions`, `receiver_coverage`, and `avg_delay_s`.

---

## 10. How to edit protocol parameters

Open:

```text
configs/default_cases.json
```

Edit the `protocols` block:

```json
"DSRC_80211p": {
  "data_rate_bps": 6000000,
  "base_delay_s": 0.02,
  "processing_delay_s": 0.005,
  "packet_size_bytes": 300,
  "communication_range_m": 70.0,
  "loss_probability": 0.02
}
```

To make packet size have a stronger delay effect in the experiment, you can test lower data rate or add queueing delay:

```json
"channel": {
  "packet_size_bytes": 1400,
  "data_rate_bps": 1000000,
  "queue_delay_s": 0.02
}
```

---

## 11. How to configure V2I RSUs

### 11.1 Pure Python demo mode

If no RSU is manually provided, the demo automatically places RSUs near the platoon and incident point.

To manually set RSUs, add this to a case:

```json
"rsus": [
  {
    "id": "RSU_1",
    "x_m": 300.0,
    "y_m": 0.0,
    "range_m": 500.0
  }
]
```

### 11.2 SUMO mode

By default, SUMO mode can automatically create RSUs at junction positions:

```json
"v2i_default": {
  "auto_rsus_from_junctions": true,
  "max_auto_rsus": 20,
  "rsu_range_m": 500.0
}
```

If you want fixed RSUs in SUMO, use map coordinates:

```json
"rsus": [
  {
    "id": "RSU_A",
    "x_m": 1234.5,
    "y_m": 678.9,
    "range_m": 500.0
  }
]
```

You can inspect SUMO coordinates in SUMO-GUI by clicking junctions/vehicles.

---

## 12. Output files

After running:

```bash
python -m vanet_osm_warning.cli demo --config configs/default_cases.json --out results/demo
```

You get:

| Output | Meaning |
|---|---|
| `summary_metrics.csv` | Main result table. |
| `summary_report.md` | Auto-generated Markdown report. |
| `events_<case_id>.csv` | Event log: incident, packet sent/lost, warning received, collision. |
| `trajectories_<case_id>.csv` | Vehicle trajectory and speed over time. |
| `plots/summary_collisions_by_case.png` | Collision comparison. |
| `plots/summary_packet_pdr_by_case.png` | Packet-level delivery ratio. |
| `plots/summary_receiver_coverage_by_case.png` | Vehicle warning coverage. |
| `plots/summary_delay_by_case.png` | Average warning delay. |
| `plots/summary_bytes_sent_by_case.png` | Communication overhead. |
| `plots/summary_channel_load_by_case.png` | Estimated channel load. |
| `plots/packet_size_vs_delay.png` | Packet-size impact on delay. |
| `plots/packet_size_vs_packet_pdr.png` | Packet-size impact on packet PDR. |

---

## 13. Recommended thesis/report section

You can write the research content like this:

```text
The study evaluates road accident warning in VANET using SUMO/TraCI simulation.
The proposed simulator compares three communication architectures: V2V, V2I,
and hybrid V2V--V2I. In the V2V model, the accident vehicle broadcasts an
emergency braking message to nearby vehicles, and multi-hop rebroadcast is used
to extend warning coverage. In the V2I model, the accident vehicle sends the
warning to a roadside unit, and the RSU broadcasts it to vehicles in its
coverage region. The hybrid model activates both mechanisms.

The impact of communication protocol and packet size is evaluated by modeling
packet size, data rate, base delay, processing delay, loss probability, bytes
sent, packet-level delivery ratio, and estimated channel load. Safety is
measured using collision count, warning coverage, warning delay, reaction gain,
and minimum vehicle gap.
```

---

## 14. Suggested conclusion interpretation

A typical conclusion should be:

```text
The no-warning baseline produces the highest collision risk because following
vehicles react only after local visual detection. Direct V2V warning reduces
risk for nearby vehicles but is limited by communication range. Multi-hop V2V
improves warning coverage in long platoons, although it increases the number of
transmitted packets. V2I provides infrastructure-assisted coverage through RSUs,
but its performance depends on RSU placement and communication delay. The hybrid
V2V--V2I approach provides the most robust warning coverage because it combines
low-latency local dissemination with infrastructure-assisted broadcasting.
Packet-size experiments show that larger warning messages increase communication
overhead and channel load, which should be considered when designing VANET
safety messages.
```

---

## 15. Notes and limitations

- The protocol models are abstract engineering models, not full PHY/MAC simulators.
- For a more realistic network study, integrate ns-3, Veins, OMNeT++, or Plexe.
- The current implementation is suitable for a university project/thesis simulation where SUMO is used for traffic behavior and a Python model is used for V2X communication delay/loss.
- The pure Python demo is deterministic and easy to test; SUMO mode depends on the selected map, vehicle flow, and SUMO route generation.

---

## Patch note: fixed accident location and Excel export

This version includes a practical correction for project defense/testing:

- SUMO accident-enabled cases now keep trying until `incident_started` is actually created.
- SUMO incident location is fixed/configurable through `sumo_fixed_incident` in `configs/default_cases.json`.
- If the exact fixed location has no vehicle, the code waits and then uses a controlled fallback so accident cases do not become empty.
- Every run exports `results.xlsx`, `incident_locations.csv`, and `validation_report.csv`.
- `run_case_gui.sh all` now produces one combined GUI result workbook in `results/gui_all/results.xlsx` instead of separate one-row summaries only.

For the new uploaded map, use:

```bash
./run_vanet_osm_ubuntu.sh osm-file data/osm/map_td.osm all results/osm_map_td
python scripts/validate_results.py results/osm_map_td
```

Open:

```text
results/osm_map_td/results.xlsx
```

The `incident_locations` sheet shows the accident time, vehicle, edge, lane, lane position, and SUMO x-y coordinates for each case.
