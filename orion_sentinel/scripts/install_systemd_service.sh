#!/bin/bash
set -euo pipefail

SERVICE_NAME="orion-sentinel"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_DIR="${PROJECT_ROOT}/orion_sentinel"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
SERVICE_USER="${SUDO_USER:-$USER}"

if [[ ! -f "${WORK_DIR}/run.sh" ]]; then
  echo "Could not find ${WORK_DIR}/run.sh"
  exit 1
fi

if [[ -x "${PROJECT_ROOT}/venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 was not found in PATH"
  exit 1
fi

TMP_SERVICE_FILE="$(mktemp)"
cat > "${TMP_SERVICE_FILE}" <<EOF
[Unit]
Description=Orion Sentinel FastAPI Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${WORK_DIR}
EnvironmentFile=-${WORK_DIR}/.env
Environment=PYTHONPATH=${PROJECT_ROOT}
Environment=PYTHON_BIN=${PYTHON_BIN}
ExecStart=${WORK_DIR}/run.sh
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "Installing service file to ${SERVICE_PATH}"
sudo cp "${TMP_SERVICE_FILE}" "${SERVICE_PATH}"
rm -f "${TMP_SERVICE_FILE}"

sudo chmod 644 "${SERVICE_PATH}"
sudo chmod +x "${WORK_DIR}/run.sh"

sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}.service"

echo
echo "Service installed and started: ${SERVICE_NAME}.service"
echo "Check status: sudo systemctl status ${SERVICE_NAME}.service"
echo "View logs: sudo journalctl -u ${SERVICE_NAME}.service -f"
