#!/usr/bin/env bash
set -euo pipefail

# Fast validation that does NOT require SUMO or GUI.
# It checks Python syntax, unit tests, all pure-Python demo cases, Excel export,
# and the accident validation report.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
OUT_DIR="${OUT_DIR:-results/selftest_demo}"

if [ ! -d "$VENV_DIR" ]; then
  echo "[INFO] Creating virtual environment: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -e .[dev]

export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

rm -rf "$OUT_DIR"

echo "[1/5] Compile Python files"
python -m compileall -q src main.py scripts tests

echo "[2/5] Run pytest suite"
pytest -q

echo "[3/5] Run all pure-Python demo cases"
python -m vanet_osm_warning.cli demo \
  --config configs/default_cases.json \
  --out "$OUT_DIR"

echo "[4/5] Validate generated demo results"
python scripts/validate_results.py "$OUT_DIR"

echo "[5/5] Check Excel workbook exists"
test -f "$OUT_DIR/results.xlsx"

echo ""
echo "[OK] Demo/unit validation passed."
echo "[OK] Output folder: $OUT_DIR"
echo "[OK] Excel workbook: $OUT_DIR/results.xlsx"
