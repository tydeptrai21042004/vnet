# VANET V2V/V2I Project — How to Run the `.sh` Scripts

This README explains how to use the two shell scripts in the VANET project:

```text
run_vanet_osm_ubuntu.sh
run_case_gui.sh
```

The scripts are designed for **Ubuntu / WSL Ubuntu**. They help you run the VANET accident-warning simulation in pure Python demo mode, SUMO mode, SUMO GUI mode, OpenStreetMap mode, V2V mode, V2I mode, hybrid mode, and packet-size/protocol comparison mode.

---

## 1. Required project structure

Run all commands from the root folder of the project, for example:

```bash
cd vnet-main
```

The folder should contain at least:

```text
vnet-main/
├── run_vanet_osm_ubuntu.sh
├── run_case_gui.sh
├── requirements.txt
├── configs/
│   └── default_cases.json
├── src/
│   └── vanet_osm_warning/
├── data/
│   ├── osm/
│   └── sumo/
└── results/
```

If the scripts do not have execute permission, run:

```bash
chmod +x run_vanet_osm_ubuntu.sh
chmod +x run_case_gui.sh
```

---

## 2. Main script: `run_vanet_osm_ubuntu.sh`

This is the main runner script. It supports:

- Python environment setup
- SUMO installation
- pure Python demo simulation
- OSM to SUMO preprocessing
- SUMO simulation without GUI
- SUMO simulation with GUI
- plotting results
- listing all configured experiment cases

General form:

```bash
./run_vanet_osm_ubuntu.sh <mode> [arguments]
```

If you run it without arguments:

```bash
./run_vanet_osm_ubuntu.sh
```

it defaults to:

```bash
./run_vanet_osm_ubuntu.sh demo
```

---

## 3. Environment variables used by the script

You normally do not need to change these, but they are useful when debugging.

| Variable | Default value | Meaning |
|---|---|---|
| `PYTHON_BIN` | `python3` | Python executable used to create the virtual environment. |
| `VENV_DIR` | `.venv` | Name of the Python virtual environment folder. |
| `CONFIG_FILE` | `configs/default_cases.json` | JSON file containing all simulation cases. |
| `SUMO_HOME` | `/usr/share/sumo` | SUMO installation directory. |
| `SUMOCFG` | `data/sumo/osm_map.sumocfg` | Default SUMO configuration file. |
| `MAP_NAME` | `osm_map` | Default name used when generating SUMO map files. |

Example using a custom config file:

```bash
CONFIG_FILE=configs/default_cases.json ./run_vanet_osm_ubuntu.sh list-cases
```

Example using another Python executable:

```bash
PYTHON_BIN=python3.10 ./run_vanet_osm_ubuntu.sh setup
```

---

# 4. Command explanation for `run_vanet_osm_ubuntu.sh`

## 4.1 `install-sumo`

Command:

```bash
./run_vanet_osm_ubuntu.sh install-sumo
```

Purpose:

Installs SUMO, SUMO tools, and SUMO documentation on Ubuntu/WSL using `apt`.

Internally, it runs commands similar to:

```bash
sudo apt update
sudo apt install -y sumo sumo-tools sumo-doc
```

It also sets:

```bash
SUMO_HOME=/usr/share/sumo
```

and appends this line to `~/.bashrc` if it is not already there:

```bash
export SUMO_HOME=/usr/share/sumo
```

Use this command only once, or whenever SUMO is missing.

---

## 4.2 `setup`

Command:

```bash
./run_vanet_osm_ubuntu.sh setup
```

Purpose:

Creates the Python virtual environment and installs project dependencies.

It does these steps:

1. Checks whether `configs/default_cases.json` exists.
2. Creates `.venv` if it does not exist.
3. Activates `.venv`.
4. Upgrades `pip`.
5. Installs dependencies from `requirements.txt`.
6. Adds `src/` and SUMO tools to `PYTHONPATH`.

Run this before simulation if you want to prepare the environment manually.

---

## 4.3 `list-cases`

Command:

```bash
./run_vanet_osm_ubuntu.sh list-cases
```

Purpose:

Prints all experiment cases defined in:

```text
configs/default_cases.json
```

It shows information such as:

- case ID
- communication mode
- protocol
- packet size
- case name/description

Use this before running experiments so you know the exact case IDs.

Example output style:

```text
Available cases in configs/default_cases.json:

 1. C0_normal_no_incident
    mode=none, protocol=-, packet=- bytes
    Normal traffic without accident

 2. C3_v2v_multihop_dsrc_300B
    mode=v2v, protocol=DSRC_80211p, packet=300 bytes
    Multi-hop V2V accident warning
```

---

## 4.4 `demo`

Command:

```bash
./run_vanet_osm_ubuntu.sh demo
```

Purpose:

Runs the pure Python synthetic simulation using all cases in `configs/default_cases.json`.

This mode does **not** require SUMO. It is the easiest way to test the project.

Output folder:

```text
results/demo/
```

Generated outputs include:

```text
results/demo/summary_metrics.csv
results/demo/summary_report.md
results/demo/events_<case_id>.csv
results/demo/trajectories_<case_id>.csv
results/demo/plots/*.png
```

Run only one case:

```bash
./run_vanet_osm_ubuntu.sh demo C5_hybrid_v2v_v2i_300B
```

This saves output to:

```text
results/demo_C5_hybrid_v2v_v2i_300B/
```

Run one case and choose output folder:

```bash
./run_vanet_osm_ubuntu.sh demo C5_hybrid_v2v_v2i_300B results/demo_hybrid
```

Meaning:

| Argument | Meaning |
|---|---|
| `demo` | Run synthetic Python simulation. |
| `C5_hybrid_v2v_v2i_300B` | Run only this case. |
| `results/demo_hybrid` | Save results to this folder. |

---

## 4.5 `plot`

Command:

```bash
./run_vanet_osm_ubuntu.sh plot results/demo
```

Purpose:

Regenerates plots from an existing results folder.

The folder should contain:

```text
summary_metrics.csv
```

Example:

```bash
./run_vanet_osm_ubuntu.sh plot results/demo
```

Output:

```text
results/demo/plots/
```

If no folder is given, the default is:

```bash
./run_vanet_osm_ubuntu.sh plot
```

which means:

```bash
./run_vanet_osm_ubuntu.sh plot results/demo
```

---

## 4.6 `preprocess-osm`

Command:

```bash
./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_area.osm osm_map
```

Purpose:

Converts an OpenStreetMap file into SUMO files.

Input:

```text
data/osm/my_area.osm
```

Output folder:

```text
data/sumo/
```

Expected generated files:

```text
data/sumo/osm_map.net.xml
data/sumo/osm_map.rou.xml
data/sumo/osm_map.sumocfg
```

Meaning:

| Argument | Meaning |
|---|---|
| `preprocess-osm` | Convert OSM map to SUMO map. |
| `data/osm/my_area.osm` | Your OSM input file. |
| `osm_map` | Name used for generated SUMO files. |

After this command, you can run:

```bash
./run_vanet_osm_ubuntu.sh sumo C3_v2v_multihop_dsrc_300B data/sumo/osm_map.sumocfg results/sumo_c3
```

or:

```bash
./run_case_gui.sh
```

---

## 4.7 `osm-file`

Command:

```bash
./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm all results/osm_all
```

Purpose:

Runs the full pipeline:

```text
OSM file → SUMO map generation → SUMO simulation → result export
```

It uses the OSM file directly and runs SUMO simulation without GUI.

Meaning:

| Argument | Meaning |
|---|---|
| `osm-file` | Run OSM-based SUMO simulation. |
| `data/osm/my_area.osm` | Input OSM map. |
| `all` | Run all cases. |
| `results/osm_all` | Save results here. |

Run only one case:

```bash
./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm C4_v2i_lte_5g_300B results/osm_v2i
```

This means:

```text
Use my_area.osm, run only V2I case C4, and save result to results/osm_v2i.
```

---

## 4.8 `osm-file-gui`

Command:

```bash
./run_vanet_osm_ubuntu.sh osm-file-gui data/osm/my_area.osm C4_v2i_lte_5g_300B results/osm_gui_v2i
```

Purpose:

Same as `osm-file`, but opens the SUMO GUI.

Use this when you want to visually watch the simulation.

Meaning:

| Argument | Meaning |
|---|---|
| `osm-file-gui` | Run OSM-based SUMO simulation with GUI. |
| `data/osm/my_area.osm` | Input OSM map. |
| `C4_v2i_lte_5g_300B` | Run only this V2I case. |
| `results/osm_gui_v2i` | Save outputs here. |

---

## 4.9 `bbox`

Command:

```bash
./run_vanet_osm_ubuntu.sh bbox 10.755,106.665,10.765,106.680 all results/osm_bbox
```

Purpose:

Downloads or builds a SUMO scenario from a bounding box and runs simulation without GUI.

The bounding box format is:

```text
south,west,north,east
```

Example for an area in Ho Chi Minh City:

```text
10.755,106.665,10.765,106.680
```

Meaning:

| Argument | Meaning |
|---|---|
| `bbox` | Build/run SUMO simulation from map bounding box. |
| `10.755,106.665,10.765,106.680` | Map boundary: south, west, north, east. |
| `all` | Run all cases. |
| `results/osm_bbox` | Save result folder. |

Run one case:

```bash
./run_vanet_osm_ubuntu.sh bbox 10.755,106.665,10.765,106.680 C3_v2v_multihop_dsrc_300B results/bbox_v2v
```

---

## 4.10 `bbox-gui`

Command:

```bash
./run_vanet_osm_ubuntu.sh bbox-gui 10.755,106.665,10.765,106.680 C5_hybrid_v2v_v2i_300B results/bbox_gui_hybrid
```

Purpose:

Same as `bbox`, but opens the SUMO GUI.

Use this to visually inspect V2V, V2I, or hybrid cases on a map area.

---

## 4.11 `sumo`

Command:

```bash
./run_vanet_osm_ubuntu.sh sumo C3_v2v_multihop_dsrc_300B data/sumo/osm_map.sumocfg results/sumo_c3
```

Purpose:

Runs SUMO simulation from an existing `.sumocfg` file without GUI.

Use this after you already generated a SUMO configuration file with `preprocess-osm` or `osm-file`.

Meaning:

| Argument | Meaning |
|---|---|
| `sumo` | Run SUMO simulation without GUI. |
| `C3_v2v_multihop_dsrc_300B` | Case ID to run. Use `all` for all cases. |
| `data/sumo/osm_map.sumocfg` | SUMO config file. |
| `results/sumo_c3` | Output folder. |

Run all cases:

```bash
./run_vanet_osm_ubuntu.sh sumo all data/sumo/osm_map.sumocfg results/sumo_all
```

---

## 4.12 `sumo-gui` or `gui`

Command:

```bash
./run_vanet_osm_ubuntu.sh sumo-gui C4_v2i_lte_5g_300B data/sumo/osm_map.sumocfg results/gui_c4
```

or:

```bash
./run_vanet_osm_ubuntu.sh gui C4_v2i_lte_5g_300B data/sumo/osm_map.sumocfg results/gui_c4
```

Purpose:

Runs SUMO simulation with the graphical interface.

Use this when you want to see cars moving in SUMO GUI.

Meaning:

| Argument | Meaning |
|---|---|
| `sumo-gui` / `gui` | Run SUMO with GUI. |
| `C4_v2i_lte_5g_300B` | Run the V2I case. |
| `data/sumo/osm_map.sumocfg` | SUMO config file. |
| `results/gui_c4` | Save results here. |

---

# 5. GUI script: `run_case_gui.sh`

The second script is a simpler interactive GUI runner.

It reads case IDs automatically from:

```text
configs/default_cases.json
```

It is useful after you already have a SUMO config file:

```text
data/sumo/osm_map.sumocfg
```

Create that file first with:

```bash
./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_area.osm osm_map
```

or:

```bash
./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm all results/osm
```

---

## 5.1 Start the interactive GUI menu

Command:

```bash
./run_case_gui.sh
```

Purpose:

Shows a menu like:

```text
[ 1] C0_normal_no_incident
[ 2] C1_accident_no_warning
[ 3] C2_v2v_direct_dsrc_300B
[ 4] C3_v2v_multihop_dsrc_300B
[ 5] C4_v2i_lte_5g_300B
[ 6] C5_hybrid_v2v_v2i_300B
...
[A] Run all cases one by one in GUI
[Q] Quit
```

Then you can type:

```text
1
```

or:

```text
A
```

or:

```text
Q
```

Meaning:

| Input | Meaning |
|---|---|
| number | Run one selected case. |
| `A` | Run all cases one by one in SUMO GUI. |
| `Q` | Quit. |

---

## 5.2 Run one GUI case directly by case ID

Command:

```bash
./run_case_gui.sh C4_v2i_lte_5g_300B
```

Purpose:

Runs the selected case directly in SUMO GUI without showing the menu.

Output folder:

```text
results/gui_C4_v2i_lte_5g_300B/
```

---

## 5.3 Run one GUI case directly by number

Command:

```bash
./run_case_gui.sh 5
```

Purpose:

Runs the 5th case in `configs/default_cases.json`.

This is useful when you already know the menu index.

---

## 5.4 Run all GUI cases directly

Command:

```bash
./run_case_gui.sh all
```

Purpose:

Runs all cases one by one in SUMO GUI.

After each case, the script waits for you to press Enter before opening the next case.

---

# 6. Recommended workflow

## 6.1 Fast test without SUMO

Use this first to confirm the code works:

```bash
./run_vanet_osm_ubuntu.sh setup
./run_vanet_osm_ubuntu.sh list-cases
./run_vanet_osm_ubuntu.sh demo
```

Check result:

```bash
ls results/demo
```

Important files:

```text
results/demo/summary_metrics.csv
results/demo/summary_report.md
results/demo/plots/
```

---

## 6.2 Run one V2V case

```bash
./run_vanet_osm_ubuntu.sh demo C3_v2v_multihop_dsrc_300B results/demo_v2v
```

This tests multi-hop V2V warning.

---

## 6.3 Run one V2I case

```bash
./run_vanet_osm_ubuntu.sh demo C4_v2i_lte_5g_300B results/demo_v2i
```

This tests infrastructure-assisted warning through RSU.

---

## 6.4 Run one hybrid V2V + V2I case

```bash
./run_vanet_osm_ubuntu.sh demo C5_hybrid_v2v_v2i_300B results/demo_hybrid
```

This tests both V2V and V2I together.

---

## 6.5 Run packet-size comparison

Example small packet:

```bash
./run_vanet_osm_ubuntu.sh demo C3_v2v_multihop_dsrc_300B results/packet_300B
```

Example large packet:

```bash
./run_vanet_osm_ubuntu.sh demo C8_v2v_multihop_packet_1400B results/packet_1400B
```

Then compare:

```text
packet_pdr
receiver_coverage
avg_warning_delay_s
bytes_sent
channel_load
collisions
```

These metrics are saved in:

```text
summary_metrics.csv
```

---

## 6.6 Full SUMO workflow with OSM file

Step 1: Install SUMO:

```bash
./run_vanet_osm_ubuntu.sh install-sumo
```

Step 2: Prepare Python environment:

```bash
./run_vanet_osm_ubuntu.sh setup
```

Step 3: Put your OSM map here:

```text
data/osm/my_area.osm
```

Step 4: Convert OSM to SUMO:

```bash
./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_area.osm osm_map
```

Step 5: Run SUMO without GUI:

```bash
./run_vanet_osm_ubuntu.sh sumo all data/sumo/osm_map.sumocfg results/sumo_all
```

Step 6: Run one case with GUI:

```bash
./run_vanet_osm_ubuntu.sh sumo-gui C4_v2i_lte_5g_300B data/sumo/osm_map.sumocfg results/gui_c4
```

or:

```bash
./run_case_gui.sh
```

---

# 7. What each result file means

After a run, you will see files like:

```text
summary_metrics.csv
summary_report.md
events_<case_id>.csv
trajectories_<case_id>.csv
plots/
```

| File/folder | Meaning |
|---|---|
| `summary_metrics.csv` | Main quantitative result table for all cases. |
| `summary_report.md` | Human-readable report summary. |
| `events_<case_id>.csv` | Event log: packet sent, packet lost, warning delivered, collision, etc. |
| `trajectories_<case_id>.csv` | Vehicle position/speed over time. |
| `plots/` | Auto-generated figures. |

Important metrics:

| Metric | Meaning |
|---|---|
| `collisions` | Number of collisions. Lower is better. |
| `packet_pdr` | Delivered packets / sent packets. Measures packet-level reliability. |
| `receiver_coverage` | Warned target vehicles / total target vehicles. Measures warning coverage. |
| `avg_warning_delay_s` | Average time from accident to warning reception. Lower is better. |
| `reaction_gain_s` | How much earlier the vehicle reacts due to VANET warning. Higher is better. |
| `bytes_sent` | Total network bytes transmitted. Lower means less overhead. |
| `channel_load` | Estimated communication load. Lower is better. |
| `communication_mode` | `none`, `v2v`, `v2i`, or `hybrid`. |
| `protocol` | Protocol model, such as DSRC-like, C-V2X-like, or LTE/5G-like. |
| `packet_size_bytes` | Warning message size in bytes. |

---

# 8. Meaning of communication modes

| Mode | Meaning |
|---|---|
| `none` | No communication. Baseline accident case. |
| `v2v` | Vehicle-to-Vehicle warning. Cars warn other cars directly. |
| `v2i` | Vehicle-to-Infrastructure warning. Car sends accident warning to RSU, then RSU broadcasts to vehicles. |
| `hybrid` | Both V2V and V2I are used together. |

---

# 9. Meaning of common case IDs

The exact cases come from `configs/default_cases.json`, but commonly used cases are:

| Case ID | Meaning |
|---|---|
| `C0_normal_no_incident` | Normal traffic, no accident. |
| `C1_accident_no_warning` | Accident/sudden brake, no VANET warning. |
| `C2_v2v_direct_dsrc_300B` | Direct V2V warning with DSRC-like protocol and 300-byte packet. |
| `C3_v2v_multihop_dsrc_300B` | Multi-hop V2V warning with DSRC-like protocol and 300-byte packet. |
| `C4_v2i_lte_5g_300B` | V2I warning through RSU with LTE/5G-like protocol and 300-byte packet. |
| `C5_hybrid_v2v_v2i_300B` | Hybrid V2V + V2I warning. |
| `C8_v2v_multihop_packet_1400B` | V2V packet-size stress case with 1400-byte packet. |
| `C11_v2i_packet_1400B` | V2I packet-size stress case with 1400-byte packet. |
| `C12_v2v_cv2x_packet_600B` | C-V2X-like V2V protocol case with 600-byte packet. |

To see the real list in your current config, run:

```bash
./run_vanet_osm_ubuntu.sh list-cases
```

---

# 10. Troubleshooting

## Problem: `Permission denied`

Error:

```text
bash: ./run_vanet_osm_ubuntu.sh: Permission denied
```

Fix:

```bash
chmod +x run_vanet_osm_ubuntu.sh
chmod +x run_case_gui.sh
```

---

## Problem: `.venv not found`

Fix:

```bash
./run_vanet_osm_ubuntu.sh setup
```

or simply run:

```bash
./run_vanet_osm_ubuntu.sh demo
```

The script will create `.venv` automatically.

---

## Problem: `sumo not found`

Fix:

```bash
./run_vanet_osm_ubuntu.sh install-sumo
```

Then check:

```bash
sumo --version
sumo-gui --version
```

---

## Problem: `SUMO config not found`

Error example:

```text
[ERROR] SUMO config not found: data/sumo/osm_map.sumocfg
```

Fix by preprocessing an OSM file:

```bash
./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_area.osm osm_map
```

Then run:

```bash
./run_case_gui.sh
```

---

## Problem: GUI does not open in WSL

If using WSL, SUMO GUI needs a graphical display.

On Windows 11 with WSLg, it usually works automatically.

Check:

```bash
echo $DISPLAY
```

If it is empty, GUI applications may not open. You can still run non-GUI SUMO:

```bash
./run_vanet_osm_ubuntu.sh sumo all data/sumo/osm_map.sumocfg results/sumo_all
```

---

## Problem: `traci` module not found

Fix:

```bash
export SUMO_HOME=/usr/share/sumo
export PYTHONPATH="$SUMO_HOME/tools:$PWD/src:$PYTHONPATH"
```

or run through the script instead of manually running Python:

```bash
./run_vanet_osm_ubuntu.sh sumo all data/sumo/osm_map.sumocfg results/sumo_all
```

---

# 11. Best commands to use for your report/thesis

For basic evidence:

```bash
./run_vanet_osm_ubuntu.sh demo
```

For V2V evidence:

```bash
./run_vanet_osm_ubuntu.sh demo C3_v2v_multihop_dsrc_300B results/report_v2v
```

For V2I evidence:

```bash
./run_vanet_osm_ubuntu.sh demo C4_v2i_lte_5g_300B results/report_v2i
```

For hybrid evidence:

```bash
./run_vanet_osm_ubuntu.sh demo C5_hybrid_v2v_v2i_300B results/report_hybrid
```

For packet-size comparison:

```bash
./run_vanet_osm_ubuntu.sh demo C3_v2v_multihop_dsrc_300B results/report_packet_300B
./run_vanet_osm_ubuntu.sh demo C8_v2v_multihop_packet_1400B results/report_packet_1400B
```

For SUMO GUI demonstration:

```bash
./run_vanet_osm_ubuntu.sh sumo-gui C5_hybrid_v2v_v2i_300B data/sumo/osm_map.sumocfg results/gui_hybrid
```

---

# 12. Short explanation for your report

You can describe the scripts like this:

```text
The script run_vanet_osm_ubuntu.sh automates the full experimental workflow, including Python environment preparation, SUMO installation, OpenStreetMap preprocessing, synthetic demo simulation, SUMO/TraCI simulation, and plot generation. It supports different communication modes, including no-warning baseline, V2V, V2I, and hybrid V2V–V2I scenarios. The script also supports protocol and packet-size evaluation through configurable cases in configs/default_cases.json.

The script run_case_gui.sh provides an interactive SUMO GUI runner. It reads the available cases directly from the JSON configuration file and allows the user to run one case or all cases visually in SUMO GUI. This is useful for demonstration and qualitative verification of accident-warning behavior.
```

---

# 13. Minimal command sequence

If you only want the fastest complete test:

```bash
chmod +x run_vanet_osm_ubuntu.sh run_case_gui.sh
./run_vanet_osm_ubuntu.sh setup
./run_vanet_osm_ubuntu.sh list-cases
./run_vanet_osm_ubuntu.sh demo
```

If you want SUMO GUI:

```bash
./run_vanet_osm_ubuntu.sh install-sumo
./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_area.osm osm_map
./run_case_gui.sh
```
