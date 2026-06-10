# Patch notes: robust OSM preprocessing and visible cars

This patched version fixes the common issue where replacing `map.osm` and preprocessing it produces many SUMO warnings and then the GUI shows no cars.

## Main fixes

1. `src/vanet_osm_warning/sumo_tools.py`
   - Keeps passenger-car edges during `netconvert`.
   - Keeps the largest connected component.
   - Tries `randomTrips.py` with passenger-only route options.
   - Checks whether the generated route file actually contains vehicles.
   - If `randomTrips.py` fails or creates too few vehicles, it writes deterministic fallback routes with visible passenger cars.
   - The fallback uses valid single-edge or direct two-edge routes, so even disconnected or difficult OSM maps still show cars if the network has at least one drivable passenger edge.

2. `src/vanet_osm_warning/cli.py`
   - Adds:
     - `--min-vehicles`
     - `--force-fallback`

3. `run_vanet_osm_ubuntu.sh`
   - Passes robust preprocessing options automatically.
   - Supports:
     - `MIN_VEHICLES=...`
     - `FORCE_FALLBACK=true`

4. `run_case_gui.sh`
   - Allows passing a SUMO config as the second argument:
     ```bash
     ./run_case_gui.sh C5_hybrid_v2v_v2i_300B data/sumo/my_map.sumocfg
     ```

5. `scripts/check_sumo_scenario.py`
   - Adds a quick check to confirm that a generated scenario has usable passenger edges and vehicles departing early.

## Recommended commands

Use the same `osm_map` name to avoid loading the wrong config:

```bash
./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_new_map.osm osm_map
python scripts/check_sumo_scenario.py data/sumo/osm_map.sumocfg
./run_vanet_osm_ubuntu.sh sumo-gui C5_hybrid_v2v_v2i_300B data/sumo/osm_map.sumocfg results/gui_c5
```

If the map still gives many routing warnings, force deterministic visible cars:

```bash
FORCE_FALLBACK=true ./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_new_map.osm osm_map
python scripts/check_sumo_scenario.py data/sumo/osm_map.sumocfg
./run_vanet_osm_ubuntu.sh sumo-gui C5_hybrid_v2v_v2i_300B data/sumo/osm_map.sumocfg results/gui_c5
```

Or run GUI helper directly:

```bash
./run_case_gui.sh C5_hybrid_v2v_v2i_300B data/sumo/osm_map.sumocfg
```
