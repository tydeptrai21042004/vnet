#!/usr/bin/env bash
set -euo pipefail

# GUI test for the new uploaded map.
# By default it runs one representative hybrid case so you can visually see the accident.
# To run all cases in GUI, set CASE_ID=all.
# Example:
#   ./test_new_map_with_gui.sh
#   CASE_ID=all ./test_new_map_with_gui.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

MAP_FILE="${MAP_FILE:-data/osm/map_td.osm}"
MAP_NAME="${MAP_NAME:-map_td}"
CASE_ID="${CASE_ID:-C5_hybrid_v2v_v2i_300B}"
OUT_DIR="${OUT_DIR:-results/map_td_gui_${CASE_ID}}"
SUMO_DIR="${SUMO_DIR:-data/sumo}"
MIN_VEHICLES="${MIN_VEHICLES:-50}"
FORCE_FALLBACK="${FORCE_FALLBACK:-false}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ ! -f "$MAP_FILE" ]; then
  echo "[ERROR] Map file not found: $MAP_FILE"
  exit 2
fi

if ! command -v sumo-gui >/dev/null 2>&1; then
  echo "[ERROR] sumo-gui is not installed or not in PATH."
  echo "Install it with: ./run_vanet_osm_ubuntu.sh install-sumo"
  exit 3
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

echo "[3/5] Check SUMO scenario"
python scripts/check_sumo_scenario.py "$SUMOCFG"

echo "[4/5] Run GUI case: $CASE_ID"
./run_vanet_osm_ubuntu.sh sumo-gui "$CASE_ID" "$SUMOCFG" "$OUT_DIR"

echo "[5/5] Validate outputs"
python scripts/validate_results.py "$OUT_DIR"
python scripts/assert_accident_cases.py "$OUT_DIR"

echo ""
echo "[OK] GUI new-map test passed."
echo "[OK] Results folder: $OUT_DIR"
echo "[OK] Excel workbook: $OUT_DIR/results.xlsx"
echo "[OK] Check incident location in: $OUT_DIR/incident_locations.csv"
