#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[Trend Gate] backend trend service/api tests"
PYTHONPATH=. "$PYTHON_BIN" -m pytest -q \
  tests/test_dashboard_trend_service.py \
  tests/test_dashboard_trend_api.py

echo "[Trend Gate] backend trend tests passed."
