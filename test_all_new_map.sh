#!/usr/bin/env bash
set -euo pipefail

# Master validation script.
# It first runs fast unit/demo tests, then runs the new-map SUMO headless test.
# GUI is optional because it needs a display.
# Usage:
#   ./test_all_new_map.sh
#   WITH_GUI=true ./test_all_new_map.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

./test_demo_and_unit.sh
./test_new_map_without_gui.sh

if [ "${WITH_GUI:-false}" = "true" ]; then
  ./test_new_map_with_gui.sh
else
  echo "[INFO] Skipping GUI test. Run WITH_GUI=true ./test_all_new_map.sh to include it."
fi

echo "[OK] All requested tests completed."
