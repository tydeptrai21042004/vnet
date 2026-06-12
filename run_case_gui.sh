#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# VANET SUMO GUI Case Runner
# Reads cases automatically from configs/default_cases.json.
# Supports V2V, V2I, Hybrid, packet-size, and protocol cases.
# ============================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
CONFIG_FILE="${CONFIG_FILE:-configs/default_cases.json}"
SUMOCFG="${SUMOCFG:-data/sumo/osm_map.sumocfg}"

setup_venv_if_needed() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] .venv not found. Creating it now..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r requirements.txt >/dev/null

  export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
  export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
  if [ -d "$SUMO_HOME/tools" ]; then
    export PYTHONPATH="$SUMO_HOME/tools:$PYTHONPATH"
  fi
}

check_inputs() {
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] Config file not found: $CONFIG_FILE"
    exit 1
  fi

  if [ ! -f "$SUMOCFG" ]; then
    echo "[ERROR] SUMO config not found: $SUMOCFG"
    echo "Create it first with one of these commands:"
    echo "  ./run_vanet_osm_ubuntu.sh preprocess-osm data/osm/my_area.osm osm_map"
    echo "  ./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm all results/osm"
    exit 1
  fi

  if ! command -v sumo-gui >/dev/null 2>&1; then
    echo "[ERROR] sumo-gui not found. Install SUMO first:"
    echo "  ./run_vanet_osm_ubuntu.sh install-sumo"
    exit 1
  fi
}

load_cases() {
  mapfile -t CASE_LINES < <(python - <<PY
import json
from pathlib import Path
cfg = json.loads(Path("$CONFIG_FILE").read_text(encoding="utf-8"))
for c in cfg.get("cases", []):
    cid = c.get("id", "")
    name = c.get("name", "")
    mode = c.get("communication_mode", "none")
    proto = c.get("protocol", c.get("v2i_protocol", "-"))
    packet = c.get("channel", c.get("v2i", {})).get("packet_size_bytes", "-")
    control = c.get("control_algorithm", "-")
    print(f"{cid}\t{name}\t{mode}\t{proto}\t{packet}\t{control}")
PY
)

  if [ "${#CASE_LINES[@]}" -eq 0 ]; then
    echo "[ERROR] No cases found in $CONFIG_FILE"
    exit 1
  fi
}

print_menu() {
  echo ""
  echo "============================================================"
  echo " VANET Accident Warning - SUMO GUI Runner"
  echo "============================================================"
  echo "Config : $CONFIG_FILE"
  echo "SUMO   : $SUMOCFG"
  echo ""

  for i in "${!CASE_LINES[@]}"; do
    IFS=$'\t' read -r cid name mode proto packet control <<< "${CASE_LINES[$i]}"
    printf " [%2d] %-36s | mode=%-6s | protocol=%-12s | packet=%-5s | control=%s\n" \
      "$((i + 1))" "$cid" "$mode" "$proto" "$packet" "$control"
    printf "      %s\n" "$name"
  done

  echo ""
  echo " [A] Run all cases one by one in GUI"
  echo " [Q] Quit"
  echo ""
}

run_gui_case() {
  local case_id="$1"
  local out_dir="results/gui_${case_id}"

  echo ""
  echo "============================================================"
  echo "[RUN GUI] $case_id"
  echo "============================================================"

  python -m vanet_osm_warning.cli simulate-sumo \
    --config "$CONFIG_FILE" \
    --sumocfg "$SUMOCFG" \
    --out "$out_dir" \
    --case "$case_id" \
    --gui

  echo "[OK] Single-case result saved in: $out_dir"
  echo "[INFO] A single-case run intentionally has only one summary row. Use './run_case_gui.sh all' for one combined Excel file."
}

run_gui_all_combined() {
  local out_dir="results/gui_all"

  echo ""
  echo "============================================================"
  echo "[RUN GUI] all cases with one combined result workbook"
  echo "============================================================"

  python -m vanet_osm_warning.cli simulate-sumo \
    --config "$CONFIG_FILE" \
    --sumocfg "$SUMOCFG" \
    --out "$out_dir" \
    --gui

  echo "[OK] Combined GUI results saved in: $out_dir"
  echo "[OK] Open this workbook: $out_dir/results.xlsx"
}

# Optional non-interactive usage:
#   ./run_case_gui.sh C4_v2i_lte_5g_300B
#   ./run_case_gui.sh C4_v2i_lte_5g_300B data/sumo/my_map.sumocfg
#   SUMOCFG=data/sumo/my_map.sumocfg ./run_case_gui.sh C4_v2i_lte_5g_300B
#   ./run_case_gui.sh all
REQUESTED="${1:-}"
if [ -n "${2:-}" ]; then
  SUMOCFG="$2"
fi

setup_venv_if_needed
check_inputs
load_cases
if [ -n "$REQUESTED" ]; then
  if [ "$REQUESTED" = "all" ] || [ "$REQUESTED" = "A" ] || [ "$REQUESTED" = "a" ]; then
    run_gui_all_combined
    exit 0
  fi

  if [[ "$REQUESTED" =~ ^[0-9]+$ ]]; then
    index=$((REQUESTED - 1))
    if [ "$index" -lt 0 ] || [ "$index" -ge "${#CASE_LINES[@]}" ]; then
      echo "[ERROR] Choice out of range: $REQUESTED"
      exit 1
    fi
    IFS=$'\t' read -r cid _ <<< "${CASE_LINES[$index]}"
    run_gui_case "$cid"
    exit 0
  fi

  found="false"
  for line in "${CASE_LINES[@]}"; do
    IFS=$'\t' read -r cid _ <<< "$line"
    if [ "$cid" = "$REQUESTED" ]; then
      found="true"
      run_gui_case "$cid"
      break
    fi
  done

  if [ "$found" = "false" ]; then
    echo "[ERROR] Case not found: $REQUESTED"
    echo "Run without arguments to see the menu."
    exit 1
  fi
  exit 0
fi

print_menu
read -rp "Choose case number / A / Q: " CHOICE

case "$CHOICE" in
  q|Q)
    echo "[INFO] Quit."
    exit 0
    ;;
  a|A)
    echo "[INFO] Running all cases in GUI mode with one combined output folder..."
    run_gui_all_combined
    ;;
  *)
    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]]; then
      echo "[ERROR] Invalid choice: $CHOICE"
      exit 1
    fi

    index=$((CHOICE - 1))
    if [ "$index" -lt 0 ] || [ "$index" -ge "${#CASE_LINES[@]}" ]; then
      echo "[ERROR] Choice out of range: $CHOICE"
      exit 1
    fi

    IFS=$'\t' read -r cid _ <<< "${CASE_LINES[$index]}"
    run_gui_case "$cid"
    ;;
esac

echo ""
echo "[OK] GUI simulation finished."
echo "Results are saved under: results/gui_<case_id>/"
