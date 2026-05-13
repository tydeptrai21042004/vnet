#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-demo}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

setup_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"
}

install_sumo() {
  echo "[INFO] Installing SUMO packages. You may be asked for sudo password."
  sudo apt update
  sudo apt install -y sumo sumo-tools sumo-doc
  if [ -d /usr/share/sumo ]; then
    echo "export SUMO_HOME=/usr/share/sumo" >> "$HOME/.bashrc"
    export SUMO_HOME=/usr/share/sumo
  fi
  echo "[OK] SUMO installed. Current SUMO_HOME=${SUMO_HOME:-not_set}"
}

case "$MODE" in
  install-sumo)
    install_sumo
    ;;
  demo)
    setup_venv
    python -m vanet_osm_warning.cli demo --config configs/default_cases.json --out results/demo
    ;;
  osm-file)
    # Usage: ./run_vanet_osm_ubuntu.sh osm-file data/osm/my_map.osm.xml
    OSM_FILE="${2:-}"
    if [ -z "$OSM_FILE" ]; then
      echo "Usage: $0 osm-file data/osm/my_map.osm.xml"
      exit 1
    fi
    setup_venv
    export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
    python -m vanet_osm_warning.cli run-osm \
      --config configs/default_cases.json \
      --osm-file "$OSM_FILE" \
      --map-name osm_map \
      --out data/sumo \
      --results results/osm
    ;;
  bbox)
    # Usage: ./run_vanet_osm_ubuntu.sh bbox 10.755,106.665,10.765,106.680
    BBOX="${2:-}"
    if [ -z "$BBOX" ]; then
      echo "Usage: $0 bbox south,west,north,east"
      echo "Example: $0 bbox 10.755,106.665,10.765,106.680"
      exit 1
    fi
    setup_venv
    export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
    python -m vanet_osm_warning.cli run-osm \
      --config configs/default_cases.json \
      --bbox "$BBOX" \
      --map-name osm_bbox \
      --out data/sumo \
      --results results/osm
    ;;
  plot)
    setup_venv
    python -m vanet_osm_warning.cli plot --results "${2:-results/demo}"
    ;;
  *)
    echo "Unknown mode: $MODE"
    echo "Modes: install-sumo | demo | osm-file <map.osm.xml> | bbox <south,west,north,east> | plot [results_dir]"
    exit 1
    ;;
esac
