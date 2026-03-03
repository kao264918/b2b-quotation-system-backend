#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
UVICORN_HOST="${UVICORN_HOST:-127.0.0.1}"
UVICORN_PORT="${UVICORN_PORT:-8000}"
UVICORN_LOG="${UVICORN_LOG:-/tmp/b2b_uvicorn.log}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] Python not found: $PYTHON_BIN"
  echo "請先建立 venv，或用 PYTHON_BIN 指定 Python 路徑。"
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[ERROR] DATABASE_URL 未設定，無法執行 migration 與測試。"
  exit 1
fi

UVICORN_PID=""
cleanup() {
  if [[ -n "$UVICORN_PID" ]] && kill -0 "$UVICORN_PID" 2>/dev/null; then
    kill "$UVICORN_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "[STEP] alembic upgrade head"
"$PYTHON_BIN" -m alembic upgrade head

echo "[STEP] pytest -q"
"$PYTHON_BIN" -m pytest -q

echo "[STEP] start uvicorn (${UVICORN_HOST}:${UVICORN_PORT})"
"$PYTHON_BIN" -m uvicorn app.main:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" >"$UVICORN_LOG" 2>&1 &
UVICORN_PID="$!"
sleep 3

if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
  echo "[ERROR] uvicorn 啟動失敗，請檢查：$UVICORN_LOG"
  exit 1
fi

echo "[STEP] verify_system_integrity.py"
"$PYTHON_BIN" scripts/verify_system_integrity.py

echo "[DONE] Backend gate passed."
