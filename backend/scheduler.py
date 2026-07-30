from __future__ import annotations

import logging
import threading
import time

from collectors.rvc_fire import fetch as fetch_rvc_fire
from config import SETTINGS
from database import upsert_source_incidents
from geofence import enrich_and_filter
from state import now_iso, set_source

LOG = logging.getLogger(__name__)
_STOP = threading.Event()
_THREAD: threading.Thread | None = None


def collect_rvc_fire() -> None:
    attempted = now_iso()
    result = fetch_rvc_fire()
    filtered = []
    for incident in result["incidents"]:
        item = enrich_and_filter(
            incident,
            SETTINGS.home_latitude,
            SETTINGS.home_longitude,
            SETTINGS.radius_miles,
        )
        if item is not None:
            filtered.append(item)
    if result["online"]:
        upsert_source_incidents("rvc_fire", filtered)
    set_source(
        "rvc_fire",
        online=result["online"],
        last_attempt=attempted,
        last_success=now_iso() if result["online"] else None,
        downloaded_count=len(result["incidents"]),
        within_radius=len(filtered),
        error=result["error"],
    )


def _loop() -> None:
    while not _STOP.is_set():
        try:
            collect_rvc_fire()
        except Exception:
            LOG.exception("Scheduled collection failed")
        _STOP.wait(SETTINGS.rvc_fire_refresh_seconds)


def start_scheduler() -> None:
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _THREAD = threading.Thread(target=_loop, name="collector-scheduler", daemon=True)
    _THREAD.start()


def stop_scheduler() -> None:
    _STOP.set()
