from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")
_LOCK = threading.Lock()
_STATE = {
    "rvc_fire": {"online": False, "last_attempt": None, "last_success": None, "downloaded_count": 0, "within_radius": 0, "error": "not started"}
}


def set_source(name: str, **values) -> None:
    with _LOCK:
        _STATE.setdefault(name, {}).update(values)


def get_sources() -> dict:
    with _LOCK:
        return {name: dict(value) for name, value in _STATE.items()}


def now_iso() -> str:
    return datetime.now(TZ).isoformat()
