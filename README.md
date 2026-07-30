# SoCal Emergency Dashboard

Raspberry Pi backend and ESP32 display project for nearby public-safety incidents around Calimesa, California.

## Version 0.3.0

Current live sources:

- Riverside County Fire
- California Highway Patrol Inland Communications Center
- California Highway Patrol Indio Communications Center

The backend filters geocoded incidents to a configurable 25-mile radius and exposes JSON endpoints for the ESP32 display.

## API

- `GET /health`
- `GET /emergency`
- `GET /history?limit=10`

Default local URL: `http://<PI-IP>:5053`

## Install on Raspberry Pi

```bash
cd /opt/emergency-dashboard
sudo bash scripts/install.sh
```

## Update after pushing to GitHub

```bash
cd /opt/emergency-dashboard
git pull
sudo systemctl restart emergency-dashboard
```

## Notes

Public incident locations can be approximate. This project is for situational awareness and is not a replacement for 911, Wireless Emergency Alerts, or official evacuation information.
