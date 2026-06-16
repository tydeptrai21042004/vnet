#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CONFIG="${CONFIG:-configs/no_sumo_30_cases.json}"
OUT="${OUT:-results/no_sumo_30_cases}"
SEEDS="${SEEDS:-42}"

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

python main.py no-sumo \
  --config "$CONFIG" \
  --out "$OUT" \
  --seeds "$SEEDS"

echo
echo "NO-SUMO simulation complete."
echo "Interactive dashboard: $OUT/behavior_visualization/index.html"
echo "Excel workbook:       $OUT/results.xlsx"
echo "Static plots:         $OUT/plots/"
