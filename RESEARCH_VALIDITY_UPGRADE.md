# Research-validity upgrade

## Implemented corrections

- Common random numbers: every case uses the same seed inside each replication.
- Multi-seed execution: default seeds are `42, 43, 44, 45, 46`; override with `--seeds`.
- Per-replication files are stored under `replications/seed_<seed>/`.
- Root exports contain aggregated means; `multi_seed_statistics.csv` contains standard deviations.
- Synthetic collision contact constraint prevents vehicles passing through each other.
- `gap_m` is now interpreted as bumper-to-bumper clearance.
- Direct and multi-hop DSRC cases use the same TTC-adaptive controller.
- DSRC/C-V2X protocol comparison uses the same 600-byte packet, controller, multi-hop mode, and 70 m range.
- Packet loss combines base loss and BER-derived PER:
  `PER = 1 - (1 - BER)^(8 * packet_size_bytes)`.
- V2I accounting explicitly distinguishes one uplink and broadcast/unicast downlink behavior.
- Hybrid outputs include duplicate deliveries and useful-delivery ratio.
- `normalized_offered_load` replaces the ambiguous interpretation of `channel_load`; the old field remains as an alias.
- Synthetic and SUMO target-receiver selection use a bounded receiver radius and following-vehicle semantics.
- SUMO reports warning lead time relative to the first network visual-danger threshold.
- JSON configuration validation checks durations, steps, case IDs, modes, packet sizes, data rates, loss, and BER.
- Broad `except Exception` handlers were removed from source modules.
- CLI uses structured logging.
- Generated caches, result folders, and compiled Python files are excluded by `.gitignore`.

## Recommended commands

Run the default five-seed experiment:

```bash
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --out results/research_demo
```

Run selected seeds:

```bash
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --out results/research_demo \
  --seeds 42,43,44,45,46,47,48,49,50,51
```

Run SUMO without GUI:

```bash
python -m vanet_osm_warning.cli simulate-sumo \
  --config configs/default_cases.json \
  --sumocfg data/sumo/osm_map.sumocfg \
  --out results/sumo_research \
  --seeds 42,43,44,45,46
```

Run tests:

```bash
python -m pip install -e .
pytest -q
```

## Expanded scenario and scale matrix

The default synthetic platoon now contains 30 vehicles. Controlled density cases use 12, 30, and 50 vehicles, while `configs/stress_50cars_cases.json` runs the complete catalog with 50 vehicles.

The case catalog now includes 27 scenarios covering:

- no-incident and no-warning baselines;
- direct and multi-hop V2V under TTC-adaptive, preemptive, and emergency controllers;
- DSRC and C-V2X packet matrices at 100, 300, 600, and 1400 bytes where applicable;
- V2I broadcast-versus-unicast accounting;
- hybrid V2V/V2I redundancy accounting;
- low-, medium-, and high-density platoons.

Run only the 50-car density stress case:

```bash
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --case C24_density_high_50cars \
  --seeds 42,43,44,45,46 \
  --out results/stress_50cars
```

Run the full catalog with a 50-car default platoon:

```bash
python -m vanet_osm_warning.cli demo \
  --config configs/stress_50cars_cases.json \
  --out results/full_50cars
```
