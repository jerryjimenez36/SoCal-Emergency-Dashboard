#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"

sudo mkdir -p /opt/emergency-dashboard
if [[ "$ROOT" != "/opt/emergency-dashboard" ]]; then
  sudo rsync -a --delete --exclude '.git' "$ROOT/" /opt/emergency-dashboard/
  ROOT=/opt/emergency-dashboard
  BACKEND="$ROOT/backend"
fi

sudo chown -R pi5:pi5 "$ROOT"
python3 -m venv "$BACKEND/venv"
"$BACKEND/venv/bin/pip" install --upgrade pip
"$BACKEND/venv/bin/pip" install -r "$BACKEND/requirements.txt"
sudo cp "$ROOT/systemd/emergency-dashboard.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now emergency-dashboard
sudo systemctl restart emergency-dashboard

echo "Installed. Test: curl -s http://127.0.0.1:5053/health | python3 -m json.tool"
