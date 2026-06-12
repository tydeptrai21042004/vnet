# Testing the corrected VANET/SUMO project

This repository now includes extra tests and run scripts for three levels of validation:

1. **Unit + demo validation** without SUMO or GUI.
2. **New-map headless SUMO validation** without GUI.
3. **New-map SUMO GUI validation** for visual checking before defense.

The uploaded map is already included at:

```text
data/osm/map_td.osm
```

---

## A. Fast test without SUMO and without GUI

Use this first on any machine:

```bash
./test_demo_and_unit.sh
```

This script performs:

```text
1. Create/update .venv
2. Install requirements + pytest
3. Compile all Python files
4. Run pytest unit tests
5. Run all 13 pure-Python demo cases
6. Export results.xlsx
7. Validate that accident-enabled cases C1-C12 have incident_started=True
```

Expected final output:

```text
[OK] Demo/unit validation passed.
[OK] Excel workbook: results/selftest_demo/results.xlsx
```

---

## B. Full new-map test without GUI

Use this on Ubuntu/WSL with SUMO installed:

```bash
./test_new_map_without_gui.sh
```

This script performs:

```text
1. Check data/osm/map_td.osm exists
2. Check sumo and netconvert are installed
3. Preprocess the new OSM map into SUMO files
4. Check generated SUMO scenario has vehicles
5. Run all 13 cases without GUI
6. Export results.xlsx
7. Validate every accident-enabled case has accident location
8. Validate warning-enabled cases send warning packets
```

Expected output:

```text
[OK] Headless new-map test passed.
[OK] Excel workbook: results/map_td_headless/results.xlsx
[OK] Incident locations: results/map_td_headless/incident_locations.csv
```

### Optional variables

```bash
MAP_FILE=data/osm/map_td.osm \
MAP_NAME=map_td \
OUT_DIR=results/map_td_headless \
MIN_VEHICLES=50 \
./test_new_map_without_gui.sh
```

If the route generated from OSM is too sparse, force deterministic fallback routes:

```bash
FORCE_FALLBACK=true ./test_new_map_without_gui.sh
```

---

## C. GUI visual test

Use this to visually show the accident in SUMO GUI:

```bash
./test_new_map_with_gui.sh
```

By default, it runs the representative hybrid case:

```text
C5_hybrid_v2v_v2i_300B
```

To run another case:

```bash
CASE_ID=C3_v2v_multihop_dsrc_300B ./test_new_map_with_gui.sh
```

To run all cases in GUI:

```bash
CASE_ID=all ./test_new_map_with_gui.sh
```

Expected output:

```text
[OK] GUI new-map test passed.
[OK] Excel workbook: results/map_td_gui_<case>/results.xlsx
```

---

## D. Master script

Run all non-GUI validations:

```bash
./test_all_new_map.sh
```

Run unit/demo + headless + GUI:

```bash
WITH_GUI=true ./test_all_new_map.sh
```

---

## E. Strict accident checker

After any run, check that every accident case has a defensible accident location:

```bash
python scripts/assert_accident_cases.py results/map_td_headless
```

For stricter checking of warning cases:

```bash
python scripts/assert_accident_cases.py results/map_td_headless --require-warning-for-warning-cases
```

The checker requires that accident-enabled cases have:

```text
incident_started=True
incident_time_s
lane_id
lane_position_m
x_m
y_m
```

This is the file to show when defending the simulation:

```text
results/map_td_headless/incident_locations.csv
results/map_td_headless/results.xlsx
```
