#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# update_osm_and_run.sh
# Purpose:
#   Update a new .osm map, regenerate SUMO files, ensure vehicles exist,
#   use fallback route generation if needed, then launch SUMO GUI.
#
# Usage:
#   ./update_osm_and_run.sh /path/to/my_new_map.osm
#
# Optional:
#   ./update_osm_and_run.sh /path/to/my_new_map.osm CASE_NAME RESULT_DIR
#
# Example:
#   ./update_osm_and_run.sh ~/Downloads/my_new_map.osm
#   ./update_osm_and_run.sh ~/Downloads/my_new_map.osm C5_hybrid_v2v_v2i_300B results/gui_c5
#
# Note:
#   Put this file in the repo root, same level as:
#     run_vanet_osm_ubuntu.sh
#     run_case_gui.sh
#     data/
#     scripts/
# ============================================================

MAP_NAME="osm_map"
DEFAULT_CASE_NAME="C5_hybrid_v2v_v2i_300B"
DEFAULT_RESULT_DIR="results/gui_c5"

OSM_SRC="${1:-}"
CASE_NAME="${2:-$DEFAULT_CASE_NAME}"
RESULT_DIR="${3:-$DEFAULT_RESULT_DIR}"

SUMO_DIR="data/sumo"
OSM_DIR="data/osm"

NET_FILE="${SUMO_DIR}/${MAP_NAME}.net.xml"
ROUTE_FILE="${SUMO_DIR}/${MAP_NAME}.rou.xml"
TRIPS_FILE="${SUMO_DIR}/${MAP_NAME}.trips.xml"
SUMOCFG_FILE="${SUMO_DIR}/${MAP_NAME}.sumocfg"

print_step() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

print_error() {
    echo
    echo "[ERROR] $1" >&2
}

print_ok() {
    echo "[OK] $1"
}

if [[ -z "$OSM_SRC" ]]; then
    print_error "Bạn chưa truyền file .osm."
    echo
    echo "Cách dùng:"
    echo "  ./update_osm_and_run.sh /path/to/my_new_map.osm"
    echo
    echo "Ví dụ:"
    echo "  ./update_osm_and_run.sh ~/Downloads/my_new_map.osm"
    exit 1
fi

# Expand ~ manually if needed
OSM_SRC="${OSM_SRC/#\~/$HOME}"

if [[ ! -f "$OSM_SRC" ]]; then
    print_error "Không tìm thấy file OSM: $OSM_SRC"
    exit 1
fi

if [[ "${OSM_SRC##*.}" != "osm" ]]; then
    echo "[WARNING] File không có đuôi .osm: $OSM_SRC"
    echo "Script vẫn tiếp tục chạy, nhưng bạn nên kiểm tra lại file đầu vào."
fi

# Move to repo root: the directory containing this script.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "run_vanet_osm_ubuntu.sh" ]]; then
    print_error "Không thấy run_vanet_osm_ubuntu.sh. Hãy đặt script này trong thư mục gốc của repo."
    exit 1
fi

mkdir -p "$OSM_DIR" "$SUMO_DIR" "$RESULT_DIR"

chmod +x run_vanet_osm_ubuntu.sh || true
if [[ -f "run_case_gui.sh" ]]; then
    chmod +x run_case_gui.sh || true
fi

# Copy OSM into data/osm so the repo keeps a stable local copy.
OSM_BASENAME="$(basename "$OSM_SRC")"
OSM_DST="${OSM_DIR}/${OSM_BASENAME}"

print_step "BƯỚC 1: Copy map OSM mới vào repo"

# Avoid copying file to itself
OSM_SRC_ABS="$(realpath "$OSM_SRC")"
OSM_DST_ABS="$(realpath -m "$OSM_DST")"

if [[ "$OSM_SRC_ABS" != "$OSM_DST_ABS" ]]; then
    cp "$OSM_SRC" "$OSM_DST"
    print_ok "Đã copy: $OSM_SRC -> $OSM_DST"
else
    print_ok "File đã nằm trong $OSM_DIR: $OSM_DST"
fi

print_step "BƯỚC 2: Xóa map SUMO cũ để tránh bị lẫn file"

rm -f "$NET_FILE" "$ROUTE_FILE" "$TRIPS_FILE" "$SUMOCFG_FILE"

# Also remove optional helper files if they exist
rm -f "${SUMO_DIR}/${MAP_NAME}.poly.xml" \
      "${SUMO_DIR}/${MAP_NAME}.add.xml" \
      "${SUMO_DIR}/${MAP_NAME}.log" \
      "${SUMO_DIR}/${MAP_NAME}.alt.xml" || true

print_ok "Đã xóa file SUMO cũ của map name: ${MAP_NAME}"

print_step "BƯỚC 3: Preprocess OSM mới thành SUMO"

echo "Lệnh đang chạy:"
echo "  ./run_vanet_osm_ubuntu.sh preprocess-osm $OSM_DST $MAP_NAME"
echo

./run_vanet_osm_ubuntu.sh preprocess-osm "$OSM_DST" "$MAP_NAME"

print_step "BƯỚC 4: Kiểm tra scenario và số lượng xe"

if [[ ! -f "$SUMOCFG_FILE" ]]; then
    print_error "Không tạo được file SUMOCFG: $SUMOCFG_FILE"
    echo "Có thể netconvert/randomTrips.py bị lỗi hoặc SUMO chưa được cài đúng."
    exit 1
fi

if [[ -f "scripts/check_sumo_scenario.py" ]]; then
    python scripts/check_sumo_scenario.py "$SUMOCFG_FILE" || true
else
    echo "[WARNING] Không thấy scripts/check_sumo_scenario.py, bỏ qua bước kiểm tra chi tiết."
fi

VEHICLE_COUNT=0
if [[ -f "$ROUTE_FILE" ]]; then
    VEHICLE_COUNT="$(grep -c "<vehicle" "$ROUTE_FILE" || true)"
else
    echo "[WARNING] Không thấy route file: $ROUTE_FILE"
fi

echo
echo "Số lượng vehicle hiện tại trong route file: $VEHICLE_COUNT"

print_step "BƯỚC 5: Nếu chưa có xe, chạy fallback mode"

if [[ "$VEHICLE_COUNT" -le 0 ]]; then
    echo "Route file đang có 0 vehicle hoặc không hợp lệ."
    echo "Chạy lại preprocess với FORCE_FALLBACK=true để ép tạo xe."
    echo
    echo "Lệnh đang chạy:"
    echo "  FORCE_FALLBACK=true ./run_vanet_osm_ubuntu.sh preprocess-osm $OSM_DST $MAP_NAME"
    echo

    FORCE_FALLBACK=true ./run_vanet_osm_ubuntu.sh preprocess-osm "$OSM_DST" "$MAP_NAME"

    echo
    echo "Kiểm tra lại sau fallback..."

    if [[ -f "scripts/check_sumo_scenario.py" ]]; then
        python scripts/check_sumo_scenario.py "$SUMOCFG_FILE" || true
    fi

    if [[ -f "$ROUTE_FILE" ]]; then
        VEHICLE_COUNT="$(grep -c "<vehicle" "$ROUTE_FILE" || true)"
    else
        VEHICLE_COUNT=0
    fi

    echo
    echo "Số lượng vehicle sau fallback: $VEHICLE_COUNT"
else
    print_ok "Route file đã có xe, không cần fallback."
fi

if [[ "$VEHICLE_COUNT" -le 0 ]]; then
    print_error "Sau fallback vẫn không có vehicle."
    echo
    echo "Nguyên nhân thường gặp:"
    echo "  1. File OSM không có đường cho passenger car."
    echo "  2. Map quá nhỏ hoặc toàn đường private/pedestrian/bicycle."
    echo "  3. SUMO/netconvert không import được cạnh đường hợp lệ."
    echo
    echo "Bạn nên mở file network để kiểm tra:"
    echo "  sumo-gui $SUMOCFG_FILE"
    echo
    echo "Hoặc thử một OSM map lớn hơn có đường xe hơi."
    exit 1
fi

print_ok "Đã có vehicle trong route file: $ROUTE_FILE"
print_ok "Số lượng vehicle: $VEHICLE_COUNT"

print_step "BƯỚC 6: Chạy SUMO GUI"

echo "Scenario:"
echo "  CASE_NAME   = $CASE_NAME"
echo "  SUMOCFG     = $SUMOCFG_FILE"
echo "  RESULT_DIR  = $RESULT_DIR"
echo

echo "Lệnh đang chạy:"
echo "  ./run_vanet_osm_ubuntu.sh sumo-gui $CASE_NAME $SUMOCFG_FILE $RESULT_DIR"
echo

./run_vanet_osm_ubuntu.sh sumo-gui "$CASE_NAME" "$SUMOCFG_FILE" "$RESULT_DIR"

print_ok "Hoàn tất."
