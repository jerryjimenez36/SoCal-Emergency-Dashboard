# SoCal Emergency Dashboard

Raspberry Pi backend and ESP32 firmware for a 25-mile emergency incident dashboard centered near Calimesa, California.

## Version 0.2

- Flask REST API on port 5053
- SQLite incident history
- Riverside County Fire collector
- Geofence distance and bearing calculations
- Background collector scheduler
- Health, active incident, and history endpoints
- systemd service

## Endpoints

- `/health`
- `/emergency`
- `/history?limit=50`

## Install on Raspberry Pi

```bash
cd /opt
sudo git clone https://github.com/jerryjimenez36/SoCal-Emergency-Dashboard.git emergency-dashboard
cd /opt/emergency-dashboard
sudo bash scripts/install.sh
```
