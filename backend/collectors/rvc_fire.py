from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

from config import SETTINGS

LOG = logging.getLogger(__name__)
FEED_URL = "https://rvcfire.org/Feed/Feed"
HEADERS = {"User-Agent": "SoCal-Emergency-Dashboard/0.2 (personal public-safety display)"}
GEOCODER = Nominatim(user_agent="socal-emergency-dashboard-calimesa")


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _classify(call_type: str) -> tuple[str, str, int]:
    value = call_type.lower()
    if any(word in value for word in ("structure fire", "vegetation fire", "hazmat", "rescue")):
        return "fire", "critical", 1
    if "fire" in value:
        return "fire", "high", 2
    if "medical" in value:
        return "medical", "moderate", 3
    return "other", "information", 4


def _geocode(street: str, community: str, cache: dict) -> tuple[float | None, float | None, bool]:
    query = f"{street}, {community}, Riverside County, California, USA"
    key = query.lower()
    if key in cache:
        value = cache[key]
        return value.get("latitude"), value.get("longitude"), True
    location = GEOCODER.geocode(query, timeout=10, country_codes="us")
    time.sleep(1.1)
    cache[key] = {
        "latitude": float(location.latitude) if location else None,
        "longitude": float(location.longitude) if location else None,
    }
    _save_cache(SETTINGS.geocode_cache_path, cache)
    return cache[key]["latitude"], cache[key]["longitude"], False


def fetch() -> dict:
    cache = _load_cache(SETTINGS.geocode_cache_path)
    try:
        response = requests.get(FEED_URL, headers=HEADERS, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        if table is None:
            raise RuntimeError("RVC Fire incident table was not found")
        incidents: list[dict] = []
        for row in table.find_all("tr"):
            cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all(["td", "th"])]
            if len(cells) < 4 or cells[0].lower() == "street":
                continue
            street, community, call_type, incident_time = cells[:4]
            lat, lon, cached = _geocode(street, community, cache)
            category, priority, rank = _classify(call_type)
            incidents.append({
                "id": f"rvcfire-{_slug(street)}-{_slug(community)}-{_slug(incident_time)}",
                "agency": "Riverside County Fire",
                "source": "rvc_fire",
                "category": category,
                "type": call_type,
                "street": street,
                "community": community,
                "location": f"{street}, {community}",
                "incident_time": incident_time,
                "latitude": lat,
                "longitude": lon,
                "location_approximate": True,
                "geocode_cached": cached,
                "priority": priority,
                "priority_rank": rank,
            })
        return {"online": True, "error": None, "incidents": incidents}
    except Exception as exc:  # collector failure should not stop API
        LOG.exception("RVC Fire collector failed")
        return {"online": False, "error": str(exc), "incidents": []}
