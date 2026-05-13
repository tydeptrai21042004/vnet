#!/usr/bin/env bash
set -e

# ============================================================
# VANET SUMO GUI Case Runner
# Shows all simulation cases and lets user choose one.
# ============================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ---------- Check virtual environment ----------
if [ ! -d ".venv" ]; then
    echo "[ERROR] .venv not found."
    echo "Run this first:"
    echo "  ./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm"
    exit 1
fi

# ---------- Check SUMO config ----------
SUMOCFG="data/sumo/osm_map.sumocfg"

if [ ! -f "$SUMOCFG" ]; then
    echo "[ERROR] SUMO config not found: $SUMOCFG"
    echo "Run preprocessing first:"
    echo "  ./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm"
    exit 1
fi

# ---------- Environment ----------
source .venv/bin/activate
export SUMO_HOME=/usr/share/sumo
export PYTHONPATH="$PWD/src:$SUMO_HOME/tools:$PYTHONPATH"

# ---------- Case list ----------
CASES=(
    "C0_normal_no_incident_baseline"
    "C1_sudden_brake_no_warning_baseline"
    "C2_sudden_brake_direct_v2v"
    "C3_platoon_no_warning_baseline"
    "C4_platoon_direct_v2v_limited_range"
    "C5_platoon_multihop_broadcast"
    "C6_v2v_delay_loss_stress"
)

DESCRIPTIONS=(
    "Normal traffic, no accident, no warning baseline"
    "Sudden brake accident case, no VANET warning"
    "Sudden brake case with direct V2V warning"
    "Vehicle platoon, sudden brake, no warning baseline"
    "Vehicle platoon, direct V2V warning with limited range"
    "Vehicle platoon, multi-hop V2V broadcast warning"
    "V2V warning with delay and packet-loss stress test"
)

echo ""
echo "============================================================"
echo " VANET Accident Warning - SUMO GUI Runner"
echo "============================================================"
echo ""

for i in "${!CASES[@]}"; do
    printf " [%d] %-45s - %s\n" "$((i+1))" "${CASES[$i]}" "${DESCRIPTIONS[$i]}"
done

echo ""
echo " [A] Run all cases one by one in GUI"
echo " [Q] Quit"
echo ""

read -rp "Choose case number / A / Q: " CHOICE

case "$CHOICE" in
    q|Q)
        echo "[INFO] Quit."
        exit 0
        ;;
    a|A)
        echo "[INFO] Running all cases in GUI mode..."
        for CASE_ID in "${CASES[@]}"; do
            echo ""
            echo "============================================================"
            echo "[RUN GUI] $CASE_ID"
            echo "============================================================"

            python -m vanet_osm_warning.cli simulate-sumo \
              --config configs/default_cases.json \
              --sumocfg "$SUMOCFG" \
              --out "results/gui_${CASE_ID}" \
              --case "$CASE_ID" \
              --gui

            echo ""
            read -rp "Press Enter to continue to the next case..."
        done
        ;;
    *)
        if ! [[ "$CHOICE" =~ ^[0-9]+$ ]]; then
            echo "[ERROR] Invalid choice: $CHOICE"
            exit 1
        fi

        INDEX=$((CHOICE - 1))

        if [ "$INDEX" -lt 0 ] || [ "$INDEX" -ge "${#CASES[@]}" ]; then
            echo "[ERROR] Choice out of range: $CHOICE"
            exit 1
        fi

        CASE_ID="${CASES[$INDEX]}"

        echo ""
        echo "============================================================"
        echo "[RUN GUI] $CASE_ID"
        echo "============================================================"

        python -m vanet_osm_warning.cli simulate-sumo \
          --config configs/default_cases.json \
          --sumocfg "$SUMOCFG" \
          --out "results/gui_${CASE_ID}" \
          --case "$CASE_ID" \
          --gui
        ;;
esac

echo ""
echo "[OK] GUI simulation finished."
echo "Results saved in:"
echo "  results/gui_<case_name>/"