#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'

printf '\n[1/3] Kiểm tra cấu hình và thực thi nhanh đủ 30 case...\n'
pytest -q tests/test_no_sumo_30_cases.py

printf '\n[2/3] Kiểm tra riêng bộ tạo replay hành vi...\n'
pytest -q tests/test_behavior_visualization.py

printf '\n[3/3] Kiểm tra các unit test lõi không phụ thuộc SUMO...\n'
pytest -q \
  tests/test_channel_and_metrics.py \
  tests/test_config_cases.py \
  tests/test_research_validity.py \
  tests/test_scalability_and_case_matrix.py

printf '\nOK: Bộ kiểm thử NO-SUMO đã hoàn thành.\n'
printf 'Các kiểm tra bao gồm đủ 30 case, single-case CLI, Excel/CSV, replay HTML, channel và metrics.\n'
