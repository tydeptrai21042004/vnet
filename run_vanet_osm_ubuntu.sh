#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# VANET V2V/V2I Experiment Runner for Ubuntu/WSL
# Supports:
#   - pure Python demo cases
#   - OSM -> SUMO preprocessing
#   - SUMO/TraCI simulation, with or without GUI
#   - V2V, V2I, Hybrid, protocol, and packet-size cases
# ============================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
CONFIG_FILE="${CONFIG_FILE:-configs/default_cases.json}"
DEFAULT_SUMOCFG="${SUMOCFG:-data/sumo/osm_map.sumocfg}"
DEFAULT_MAP_NAME="${MAP_NAME:-osm_map}"

MODE="${1:-demo}"
if [ "$#" -gt 0 ]; then
  shift
fi

print_usage() {
  cat <<USAGE
VANET V2V/V2I runner

Usage:
  $0 install-sumo
  $0 setup
  $0 list-cases
  $0 demo [case_id|all] [out_dir]
  $0 plot [results_dir]

  $0 preprocess-osm <osm_file> [map_name]
  $0 osm-file <osm_file> [case_id|all] [out_dir]
  $0 osm-file-gui <osm_file> [case_id|all] [out_dir]

  $0 bbox <south,west,north,east> [case_id|all] [out_dir]
  $0 bbox-gui <south,west,north,east> [case_id|all] [out_dir]

  $0 sumo [case_id|all] [sumocfg] [out_dir]
  $0 sumo-gui [case_id|all] [sumocfg] [out_dir]

Examples:
  $0 demo
  $0 demo C5_hybrid_v2v_v2i_300B results/demo_hybrid
  $0 list-cases

  $0 install-sumo
  $0 preprocess-osm data/osm/my_area.osm osm_map
  $0 sumo C3_v2v_multihop_dsrc_300B data/sumo/osm_map.sumocfg results/sumo_c3
  $0 sumo-gui C4_v2i_lte_5g_300B data/sumo/osm_map.sumocfg results/gui_c4

  $0 osm-file data/osm/my_area.osm all results/osm_all
  $0 bbox 10.755,106.665,10.765,106.680 all results/osm_bbox

Environment variables:
  PYTHON_BIN     Python executable, default: python3
  VENV_DIR       Virtual environment folder, default: .venv
  CONFIG_FILE    Case config JSON, default: configs/default_cases.json
  SUMO_HOME      SUMO home, default when needed: /usr/share/sumo
  SUMOCFG        Default SUMO config, default: data/sumo/osm_map.sumocfg
  MAP_NAME       Default map name, default: osm_map
  MIN_VEHICLES   Minimum generated vehicles before fallback, default: 30
  FORCE_FALLBACK Set true to skip randomTrips and force visible fallback routes
USAGE
}

setup_venv() {
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] Config file not found: $CONFIG_FILE"
    exit 1
  fi

  if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Creating virtual environment: $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  echo "[INFO] Installing/updating Python dependencies..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt

  export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"
  if [ -n "${SUMO_HOME:-}" ] && [ -d "$SUMO_HOME/tools" ]; then
    export PYTHONPATH="$SUMO_HOME/tools:$PYTHONPATH"
  elif [ -d /usr/share/sumo/tools ]; then
    export PYTHONPATH="/usr/share/sumo/tools:$PYTHONPATH"
  fi
}

install_sumo() {
  echo "[INFO] Installing SUMO packages. You may be asked for sudo password."
  sudo apt update
  sudo apt install -y sumo sumo-tools sumo-doc

  if [ -d /usr/share/sumo ]; then
    export SUMO_HOME=/usr/share/sumo
    if ! grep -q '^export SUMO_HOME=/usr/share/sumo$' "$HOME/.bashrc" 2>/dev/null; then
      echo 'export SUMO_HOME=/usr/share/sumo' >> "$HOME/.bashrc"
    fi
  fi

  echo "[OK] SUMO installed. SUMO_HOME=${SUMO_HOME:-not_set}"
  echo "[INFO] You can now run: $0 setup"
}

ensure_sumo_env() {
  export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
  if [ -d "$SUMO_HOME/tools" ]; then
    export PYTHONPATH="$SUMO_HOME/tools:${PYTHONPATH:-}"
  fi

  if ! command -v sumo >/dev/null 2>&1; then
    echo "[ERROR] SUMO executable not found."
    echo "Install it first with:"
    echo "  $0 install-sumo"
    exit 1
  fi
}

ensure_sumo_gui() {
  ensure_sumo_env
  if ! command -v sumo-gui >/dev/null 2>&1; then
    echo "[ERROR] sumo-gui executable not found."
    echo "Install SUMO GUI with:"
    echo "  $0 install-sumo"
    exit 1
  fi
}

preprocess_extra_args() {
  printf '%s\n' "--min-vehicles" "${MIN_VEHICLES:-30}"
  if [ "${FORCE_FALLBACK:-false}" = "true" ]; then
    printf '%s\n' "--force-fallback"
  fi
}

case_option() {
  local case_id="${1:-all}"
  if [ -n "$case_id" ] && [ "$case_id" != "all" ]; then
    printf '%s\n' "--case" "$case_id"
  fi
}

list_cases() {
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] Config file not found: $CONFIG_FILE"
    exit 1
  fi

  CONFIG_FILE_PY="$CONFIG_FILE" "$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path
cfg_path = Path(os.environ["CONFIG_FILE_PY"])
with cfg_path.open("r", encoding="utf-8") as f:
    cfg = json.load(f)
print(f"Available cases in {cfg_path}:\n")
for i, c in enumerate(cfg.get("cases", []), 1):
    mode = c.get("communication_mode", "none")
    proto = c.get("protocol", c.get("v2i_protocol", "-"))
    pkt = c.get("channel", c.get("v2i", {})).get("packet_size_bytes", "-")
    name = c.get("name", "")
    print(f"{i:2d}. {c['id']}")
    print(f"    mode={mode}, protocol={proto}, packet={pkt} bytes")
    print(f"    {name}")
PY
}

run_demo() {
  local case_id="${1:-all}"
  local out_dir="${2:-results/demo}"
  if [ "$case_id" != "all" ]; then
    out_dir="${2:-results/demo_${case_id}}"
  fi

  setup_venv
  local case_args=()
  if [ "$case_id" != "all" ]; then
    case_args=(--case "$case_id")
  fi

  python -m vanet_osm_warning.cli demo \
    --config "$CONFIG_FILE" \
    --out "$out_dir" \
    "${case_args[@]}"

  echo "[OK] Demo completed: $out_dir"
}

preprocess_osm_file() {
  local osm_file="${1:-}"
  local map_name="${2:-$DEFAULT_MAP_NAME}"

  if [ -z "$osm_file" ]; then
    echo "Usage: $0 preprocess-osm <osm_file> [map_name]"
    exit 1
  fi
  if [ ! -f "$osm_file" ]; then
    echo "[ERROR] OSM file not found: $osm_file"
    exit 1
  fi

  setup_venv
  ensure_sumo_env

  mapfile -t extra_args < <(preprocess_extra_args)

  python -m vanet_osm_warning.cli preprocess-osm \
    --osm-file "$osm_file" \
    --map-name "$map_name" \
    --out data/sumo \
    "${extra_args[@]}"

  echo "[OK] SUMO config created: data/sumo/${map_name}.sumocfg"
}

run_osm_file() {
  local osm_file="${1:-}"
  local case_id="${2:-all}"
  local out_dir="${3:-results/osm}"
  local gui_flag="${4:-false}"

  if [ -z "$osm_file" ]; then
    echo "Usage: $0 osm-file <osm_file> [case_id|all] [out_dir]"
    exit 1
  fi
  if [ ! -f "$osm_file" ]; then
    echo "[ERROR] OSM file not found: $osm_file"
    exit 1
  fi

  setup_venv
  if [ "$gui_flag" = "true" ]; then
    ensure_sumo_gui
  else
    ensure_sumo_env
  fi

  local case_args=()
  if [ "$case_id" != "all" ]; then
    case_args=(--case "$case_id")
    out_dir="${3:-results/osm_${case_id}}"
  fi

  local gui_args=()
  if [ "$gui_flag" = "true" ]; then
    gui_args=(--gui)
  fi

  mapfile -t extra_args < <(preprocess_extra_args)

  python -m vanet_osm_warning.cli run-osm \
    --config "$CONFIG_FILE" \
    --osm-file "$osm_file" \
    --map-name "$DEFAULT_MAP_NAME" \
    --out data/sumo \
    --results "$out_dir" \
    "${extra_args[@]}" \
    "${case_args[@]}" \
    "${gui_args[@]}"

  echo "[OK] OSM/SUMO run completed: $out_dir"
}

run_bbox() {
  local bbox="${1:-}"
  local case_id="${2:-all}"
  local out_dir="${3:-results/osm_bbox}"
  local gui_flag="${4:-false}"

  if [ -z "$bbox" ]; then
    echo "Usage: $0 bbox <south,west,north,east> [case_id|all] [out_dir]"
    echo "Example: $0 bbox 10.755,106.665,10.765,106.680 all results/osm_bbox"
    exit 1
  fi

  setup_venv
  if [ "$gui_flag" = "true" ]; then
    ensure_sumo_gui
  else
    ensure_sumo_env
  fi

  local case_args=()
  if [ "$case_id" != "all" ]; then
    case_args=(--case "$case_id")
    out_dir="${3:-results/osm_bbox_${case_id}}"
  fi

  local gui_args=()
  if [ "$gui_flag" = "true" ]; then
    gui_args=(--gui)
  fi

  mapfile -t extra_args < <(preprocess_extra_args)

  python -m vanet_osm_warning.cli run-osm \
    --config "$CONFIG_FILE" \
    --bbox "$bbox" \
    --map-name osm_bbox \
    --out data/sumo \
    --results "$out_dir" \
    "${extra_args[@]}" \
    "${case_args[@]}" \
    "${gui_args[@]}"

  echo "[OK] BBox OSM/SUMO run completed: $out_dir"
}

run_sumo() {
  local case_id="${1:-all}"
  local sumocfg="${2:-$DEFAULT_SUMOCFG}"
  local out_dir="${3:-results/osm}"
  local gui_flag="${4:-false}"

  if [ ! -f "$sumocfg" ]; then
    echo "[ERROR] SUMO config not found: $sumocfg"
    echo "Create it first, for example:"
    echo "  $0 preprocess-osm data/osm/my_area.osm osm_map"
    exit 1
  fi

  setup_venv
  if [ "$gui_flag" = "true" ]; then
    ensure_sumo_gui
  else
    ensure_sumo_env
  fi

  local case_args=()
  if [ "$case_id" != "all" ]; then
    case_args=(--case "$case_id")
    out_dir="${3:-results/osm_${case_id}}"
  fi

  local gui_args=()
  if [ "$gui_flag" = "true" ]; then
    gui_args=(--gui)
  fi

  python -m vanet_osm_warning.cli simulate-sumo \
    --config "$CONFIG_FILE" \
    --sumocfg "$sumocfg" \
    --out "$out_dir" \
    "${case_args[@]}" \
    "${gui_args[@]}"

  echo "[OK] SUMO simulation completed: $out_dir"
}

run_plot() {
  local results_dir="${1:-results/demo}"
  setup_venv
  python -m vanet_osm_warning.cli plot --results "$results_dir"
  echo "[OK] Plots regenerated in: $results_dir/plots"
}

case "$MODE" in
  install-sumo)
    install_sumo
    ;;
  setup)
    setup_venv
    echo "[OK] Python environment is ready."
    ;;
  list-cases)
    list_cases
    ;;
  demo)
    run_demo "${1:-all}" "${2:-}"
    ;;
  preprocess-osm)
    preprocess_osm_file "${1:-}" "${2:-$DEFAULT_MAP_NAME}"
    ;;
  osm-file)
    run_osm_file "${1:-}" "${2:-all}" "${3:-results/osm}" false
    ;;
  osm-file-gui)
    run_osm_file "${1:-}" "${2:-all}" "${3:-results/osm_gui}" true
    ;;
  bbox)
    run_bbox "${1:-}" "${2:-all}" "${3:-results/osm_bbox}" false
    ;;
  bbox-gui)
    run_bbox "${1:-}" "${2:-all}" "${3:-results/osm_bbox_gui}" true
    ;;
  sumo)
    run_sumo "${1:-all}" "${2:-$DEFAULT_SUMOCFG}" "${3:-results/osm}" false
    ;;
  sumo-gui|gui)
    run_sumo "${1:-all}" "${2:-$DEFAULT_SUMOCFG}" "${3:-results/osm_gui}" true
    ;;
  plot)
    run_plot "${1:-results/demo}"
    ;;
  help|-h|--help)
    print_usage
    ;;
  *)
    echo "[ERROR] Unknown mode: $MODE"
    echo ""
    print_usage
    exit 1
    ;;
esac
