#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${PYTHONPATH:-${PROJECT_ROOT}}"

if [ -n "${PYTHON_BIN:-}" ]; then
	PYTHON_CMD="${PYTHON_BIN}"
elif [ -x "${PROJECT_ROOT}/venv/bin/python" ]; then
	PYTHON_CMD="${PROJECT_ROOT}/venv/bin/python"
else
	PYTHON_CMD="python3"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

exec "${PYTHON_CMD}" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}"
