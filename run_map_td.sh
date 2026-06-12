#!/usr/bin/env bash
set -euo pipefail

# Run the corrected fixed-incident SUMO experiment on the uploaded map.
# Output workbook: results/osm_map_td/results.xlsx

./run_vanet_osm_ubuntu.sh osm-file data/osm/map_td.osm all results/osm_map_td
python scripts/validate_results.py results/osm_map_td
