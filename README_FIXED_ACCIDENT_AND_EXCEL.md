# Fixed Accident Location + Excel Result Export

This patch fixes the three practical problems found during project testing:

1. **Excel looked empty** because the old code mainly exported CSV files and left warning metrics blank for no-warning baselines.
2. **SUMO accident cases could fail to start** when the runner could not find a moving vehicle at the exact incident time.
3. **Accident location was hard to defend** because the old SUMO selector chose a vehicle dynamically without logging a fixed map position.

## 1. New result files

After every `demo`, `simulate-sumo`, or `run-osm` run, the code now writes:

```text
summary_metrics.csv
incident_locations.csv
validation_report.csv
results.xlsx
events_<case_id>.csv
trajectories_<case_id>.csv
summary_report.md
plots/
```

Open this file for presentation/report checking:

```text
results.xlsx
```

It contains these sheets:

| Sheet | Purpose |
|---|---|
| `summary_for_excel` | Human-friendly summary. N/A cells are explained instead of looking empty. |
| `summary_numeric` | Numeric metrics for analysis/plots. |
| `incident_locations` | One row per case showing accident vehicle, time, edge, lane, lane position, x, y. |
| `validation_report` | Checks whether accident-enabled cases really triggered an accident. |
| `case_explanation` | Explains why C0/C1 have missing communication metrics by design. |
| `all_events` | Combined event logs from all cases. |

## 2. Fixed SUMO accident configuration

The config now includes:

```json
"sumo_fixed_incident": {
  "enabled": true,
  "edge_id": "",
  "lane_id": "",
  "position_m": null,
  "time_s": 25.0,
  "search_radius_m": 80.0,
  "fallback_after_s": 8.0,
  "min_speed_mps": 1.0,
  "target_radius_m": 600.0,
  "auto_position_ratio": 0.55,
  "wait_log_interval_s": 1.0,
  "slow_down_duration_s": 2.0
}
```

### How it works

- If `edge_id`, `lane_id`, and `position_m` are provided, the incident is triggered near that exact map location.
- If they are left empty, the runner auto-locks a deterministic fixed point on the densest active lane and logs it.
- If no vehicle reaches the exact fixed point, the runner waits.
- If the map is too sparse, after `fallback_after_s`, it chooses the nearest valid vehicle so the accident case is not empty.

This guarantees that accident-enabled SUMO cases have `incident_started=True` unless the SUMO map has no usable vehicles at all.

## 3. Using the new uploaded map

The uploaded map was copied into:

```text
data/osm/map_td.osm
```

Run with the new map:

```bash
./run_vanet_osm_ubuntu.sh osm-file data/osm/map_td.osm all results/osm_map_td
```

Then validate:

```bash
python scripts/validate_results.py results/osm_map_td
```

Expected validation summary:

```text
[OK] All accident-enabled cases have incident_started=True and no validation FAIL rows.
```

## 4. GUI usage

Single case GUI:

```bash
./run_case_gui.sh C4_v2i_lte_5g_300B
```

This intentionally creates only one summary row.

Combined GUI run for all cases:

```bash
./run_case_gui.sh all
```

This now writes one combined workbook:

```text
results/gui_all/results.xlsx
```

## 5. What to tell the teacher/panel

> In the corrected SUMO simulation, the accident is not an unclear random point. The runner uses a fixed incident configuration. For each accident-enabled case, it records the actual vehicle, time, edge ID, lane ID, lane position, and SUMO x-y coordinates in `incident_locations.csv` and `results.xlsx`. Therefore, all V2V, V2I, and hybrid cases can be compared using a traceable accident event.

## 6. Extra validation scripts added

Use these scripts to check the corrected version end to end:

```bash
./test_demo_and_unit.sh
./test_new_map_without_gui.sh
./test_new_map_with_gui.sh
./test_all_new_map.sh
```

For the fastest check that does not require SUMO:

```bash
./test_demo_and_unit.sh
```

For the real uploaded map without GUI:

```bash
./test_new_map_without_gui.sh
```

For GUI visualization:

```bash
./test_new_map_with_gui.sh
```

For strict accident validation after any run:

```bash
python scripts/assert_accident_cases.py results/map_td_headless --require-warning-for-warning-cases
```

More details are in:

```text
README_TESTING_NEW_MAP.md
```
