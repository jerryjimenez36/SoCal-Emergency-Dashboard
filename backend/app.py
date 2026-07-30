from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

from config import SETTINGS
from database import get_active_incidents, get_recent_incidents, initialize_database
from scheduler import start_scheduler
from state import get_sources

TZ = ZoneInfo("America/Los_Angeles")


def configure_logging() -> None:
    SETTINGS.log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(SETTINGS.log_path), logging.StreamHandler()],
    )


def create_app() -> Flask:
    configure_logging()
    initialize_database()
    start_scheduler()
    app = Flask(__name__)

    @app.get("/")
    def index():
        return jsonify({"service": "SoCal Emergency Dashboard", "version": "0.2.0", "status": "online"})

    @app.get("/health")
    def health():
        return jsonify({
            "backend": "online",
            "database": "online",
            "version": "0.2.0",
            "time": datetime.now(TZ).isoformat(),
            "collectors": get_sources(),
        })

    @app.get("/emergency")
    def emergency():
        incidents = get_active_incidents()
        counts: dict[str, int] = {}
        for item in incidents:
            category = item.get("category") or "other"
            counts[category] = counts.get(category, 0) + 1
        return jsonify({
            "online": True,
            "updated": datetime.now(TZ).isoformat(),
            "center": {"label": "Calimesa", "latitude": SETTINGS.home_latitude, "longitude": SETTINGS.home_longitude},
            "radius_miles": SETTINGS.radius_miles,
            "incident_count": len(incidents),
            "counts": counts,
            "incidents": incidents,
            "sources": get_sources(),
        })

    @app.get("/history")
    def history():
        try:
            limit = max(1, min(int(request.args.get("limit", 50)), 250))
        except ValueError:
            limit = 50
        incidents = get_recent_incidents(limit)
        return jsonify({"online": True, "count": len(incidents), "incidents": incidents})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=SETTINGS.api_port, debug=False)
