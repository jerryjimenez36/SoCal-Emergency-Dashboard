from __future__ import annotations

import logging
import threading
import time

from collectors.calfire import fetch as fetch_calfire
from collectors.chp import fetch as fetch_chp
from collectors.rvc_fire import fetch as fetch_rvc_fire
from config import SETTINGS
from database import upsert_source_incidents
from geofence import enrich_and_filter
from state import now_iso, set_source

LOG = logging.getLogger(__name__)
_STOP = threading.Event()
_THREAD: threading.Thread | None = None


def _collect(source: str, fetcher) -> None:
    attempted = now_iso()
    result = fetcher()
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
        upsert_source_incidents(source, filtered)
    set_source(
        source,
        online=result["online"],
        last_attempt=attempted,
        last_success=now_iso() if result["online"] else None,
        downloaded_count=len(result["incidents"]),
        within_radius=len(filtered),
        error=result["error"],
    )


def collect_rvc_fire() -> None:
    _collect("rvc_fire", fetch_rvc_fire)


def collect_chp() -> None:
    _collect("chp", fetch_chp)


def collect_calfire() -> None:
    _collect("calfire", fetch_calfire)


def _loop() -> None:
    next_rvc = 0.0
    next_chp = 0.0
    next_calfire = 0.0
    while not _STOP.is_set():
        now = time.monotonic()
        if now >= next_rvc:
            try:
                collect_rvc_fire()
            except Exception:
                LOG.exception("RVC Fire scheduled collection failed")
            next_rvc = time.monotonic() + SETTINGS.rvc_fire_refresh_seconds

        if now >= next_chp:
            try:
                collect_chp()
            except Exception:
                LOG.exception("CHP scheduled collection failed")
            next_chp = time.monotonic() + SETTINGS.chp_refresh_seconds

        if now >= next_calfire:
            try:
                collect_calfire()
            except Exception:
                LOG.exception("CAL FIRE scheduled collection failed")
            next_calfire = (
                time.monotonic()
                + SETTINGS.calfire_refresh_seconds
            )

        _STOP.wait(1)


def start_scheduler() -> None:
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _THREAD = threading.Thread(target=_loop, name="collector-scheduler", daemon=True)
    _THREAD.start()


def stop_scheduler() -> None:
    _STOP.set()
