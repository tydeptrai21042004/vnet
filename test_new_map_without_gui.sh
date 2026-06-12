#!/usr/bin/env bash
set -euo pipefail

# Full headless test for the new uploaded map.
# Requires SUMO installed, but does NOT open GUI.
# It preprocesses data/osm/map_td.osm, checks generated SUMO routes,
# runs all 13 cases, validates every accident case, and writes results.xlsx.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

MAP_FILE="${MAP_FILE:-data/osm/map_td.osm}"
MAP_NAME="${MAP_NAME:-map_td}"
OUT_DIR="${OUT_DIR:-results/map_td_headless}"
SUMO_DIR="${SUMO_DIR:-data/sumo}"
MIN_VEHICLES="${MIN_VEHICLES:-50}"
FORCE_FALLBACK="${FORCE_FALLBACK:-false}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ ! -f "$MAP_FILE" ]; then
  echo "[ERROR] Map file not found: $MAP_FILE"
  echo "Set MAP_FILE=/path/to/map.osm or place the uploaded map at data/osm/map_td.osm"
  exit 2
fi

if ! command -v sumo >/dev/null 2>&1; then
  echo "[ERROR] SUMO is not installed or not in PATH."
  echo "Install it with: ./run_vanet_osm_ubuntu.sh install-sumo"
  exit 3
fi

if ! command -v netconvert >/dev/null 2>&1; then
  echo "[ERROR] netconvert is not installed or not in PATH."
  echo "Install SUMO tools with: ./run_vanet_osm_ubuntu.sh install-sumo"
  exit 4
fi

export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
export MAP_NAME
export MIN_VEHICLES
export FORCE_FALLBACK

rm -rf "$OUT_DIR"
mkdir -p "$SUMO_DIR"

echo "[1/5] Prepare Python environment"
./run_vanet_osm_ubuntu.sh setup
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

echo "[2/5] Preprocess new OSM map into SUMO files"
./run_vanet_osm_ubuntu.sh preprocess-osm "$MAP_FILE" "$MAP_NAME"

SUMOCFG="$SUMO_DIR/${MAP_NAME}.sumocfg"
if [ ! -f "$SUMOCFG" ]; then
  echo "[ERROR] SUMO config was not created: $SUMOCFG"
  exit 5
fi

echo "[3/5] Check SUMO scenario has usable edges and vehicles"
python scripts/check_sumo_scenario.py "$SUMOCFG"

echo "[4/5] Run all cases without GUI"
./run_vanet_osm_ubuntu.sh sumo all "$SUMOCFG" "$OUT_DIR"

echo "[5/5] Validate accident and Excel outputs"
python scripts/validate_results.py "$OUT_DIR"
python scripts/assert_accident_cases.py "$OUT_DIR" --require-warning-for-warning-cases

echo ""
echo "[OK] Headless new-map test passed."
echo "[OK] Results folder: $OUT_DIR"
echo "[OK] Excel workbook: $OUT_DIR/results.xlsx"
echo "[OK] Incident locations: $OUT_DIR/incident_locations.csv"
