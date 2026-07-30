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
URL = "https://cad.chp.ca.gov/Traffic.aspx"
CENTERS = {"inland": "INCC", "indio": "ICCC"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 SoCal-Emergency-Dashboard/0.3"
    )
}
GEOCODER = Nominatim(user_agent="socal-emergency-dashboard-chp-calimesa")

# Approximate fallback coordinates used only when CHP freeway shorthand
# cannot be resolved by the geocoder.
AREA_FALLBACKS = {
    "san gorgonio pass": (33.9256, -116.8753),
    "beaumont": (33.9295, -116.9773),
    "banning": (33.9256, -116.8764),
    "riverside": (33.9533, -117.3962),
    "riverside fsp": (33.9533, -117.3962),
    "san bernardino": (34.1083, -117.2898),
    "rancho cucamonga": (34.1064, -117.5931),
    "indio chp": (33.7206, -116.2156),
    "ic": (33.7206, -116.2156),
}


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


def _hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for element in soup.select("input[type='hidden'][name]"):
        fields[element["name"]] = element.get("value", "")
    return fields


def _normalize_road_text(value: str) -> str:
    text = f" {value.upper()} "
    replacements = {
        " I10 ": " Interstate 10 ",
        " I-10 ": " Interstate 10 ",
        " SR60 ": " State Route 60 ",
        " SR79 ": " State Route 79 ",
        " SR86 ": " State Route 86 ",
        " SR91 ": " State Route 91 ",
        " SR111 ": " State Route 111 ",
        " SR243 ": " State Route 243 ",
        " SR330 ": " State Route 330 ",
        " SR38 ": " State Route 38 ",
        " WB ": " westbound ",
        " EB ": " eastbound ",
        " NB ": " northbound ",
        " SB ": " southbound ",
        " W/O ": " west of ",
        " E/O ": " east of ",
        " N/O ": " north of ",
        " S/O ": " south of ",
        " / ": " and ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split()).title()


def _classify(call_type: str) -> tuple[str, str, str, int]:
    value = call_type.lower()
    if "sig alert" in value:
        return "SIG Alert", "traffic", "critical", 1
    if "1141" in value or "major inj" in value or "fatal" in value:
        return "Injury Collision", "traffic", "critical", 1
    if "collision" in value and "minor inj" in value:
        return "Minor-Injury Collision", "traffic", "high", 2
    if "collision" in value and "no inj" in value:
        return "Non-Injury Collision", "traffic", "moderate", 3
    if "collision" in value:
        return "Traffic Collision", "traffic", "high", 2
    if "vehicle fire" in value or "car fire" in value:
        return "Vehicle Fire", "fire", "high", 2
    if "hazard" in value:
        return "Traffic Hazard", "traffic", "moderate", 3
    if "closure" in value:
        return "Road Closure", "traffic", "high", 2
    if "disabled" in value:
        return "Disabled Vehicle", "traffic", "information", 4
    if "assist" in value:
        return "Motorist Assist", "traffic", "information", 4
    return call_type, "traffic", "information", 4


def _geocode(
    location: str,
    location_desc: str,
    area: str,
    cache: dict,
) -> tuple[float | None, float | None, bool]:
    best_location = location_desc or location
    query = f"{_normalize_road_text(best_location)}, {area}, California, USA"
    key = f"chp::{query.lower()}"

    cached = cache.get(key)

    # Return a successful cached location immediately. Failed cached entries
    # are retried through the fallback logic below.
    if cached and cached.get("latitude") is not None:
        return cached["latitude"], cached["longitude"], True

    location_result = None

    try:
        location_result = GEOCODER.geocode(
            query,
            timeout=10,
            country_codes="us",
        )
        time.sleep(1.1)
    except Exception:
        LOG.exception("CHP geocoding failed for %s", query)

    if location_result:
        latitude = float(location_result.latitude)
        longitude = float(location_result.longitude)
        method = "exact"
    else:
        fallback = AREA_FALLBACKS.get(area.strip().lower())

        if fallback:
            latitude, longitude = fallback
            method = "area_fallback"
        else:
            latitude = None
            longitude = None
            method = "failed"

    cache[key] = {
        "latitude": latitude,
        "longitude": longitude,
        "method": method,
    }

    _save_cache(SETTINGS.geocode_cache_path, cache)

    return latitude, longitude, False


def _fetch_center(center_name: str, center_code: str, cache: dict) -> list[dict]:
    session = requests.Session()
    first = session.get(URL, headers=HEADERS, timeout=30)
    first.raise_for_status()
    payload = _hidden_fields(BeautifulSoup(first.text, "html.parser"))
    payload.update({
        "__EVENTTARGET": "ddlComCenter",
        "__EVENTARGUMENT": "",
        "ddlComCenter": center_code,
    })
    response = session.post(URL, headers=HEADERS, data=payload, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError(f"CHP {center_name} incident table was not found")

    incidents: list[dict] = []
    for row in table.find_all("tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all(["td", "th"])]
        if len(cells) < 7:
            continue

        # Every CHP incident row begins with "Details".
        # Identify the header using the No. and Time columns instead.
        if cells[1].lower() in {"no.", "no"} or cells[2].lower() == "time":
            continue
        _, number, incident_time, raw_type, location, location_desc, area = cells[:7]
        display_type, category, priority, rank = _classify(raw_type)
        lat, lon, cached = _geocode(location, location_desc, area, cache)
        incidents.append({
            "id": f"chp-{center_code.lower()}-{_slug(number)}-{_slug(incident_time)}-{_slug(location)}",
            "agency": "California Highway Patrol",
            "source": "chp",
            "center": center_name,
            "center_code": center_code,
            "incident_number": number,
            "category": category,
            "type": display_type,
            "raw_type": raw_type,
            "street": location_desc or location,
            "community": area,
            "location": f"{location_desc or location}, {area}",
            "incident_time": incident_time,
            "latitude": lat,
            "longitude": lon,
            "location_approximate": True,
            "geocode_cached": cached,
            "priority": priority,
            "priority_rank": rank,
        })
    return incidents


def fetch() -> dict:
    cache = _load_cache(SETTINGS.geocode_cache_path)
    incidents: list[dict] = []
    errors: list[str] = []
    successful_centers = 0

    for center_name, center_code in CENTERS.items():
        try:
            incidents.extend(_fetch_center(center_name, center_code, cache))
            successful_centers += 1
        except Exception as exc:
            LOG.exception("CHP %s collector failed", center_name)
            errors.append(f"{center_name}: {exc}")

    # Deduplicate any incident returned by both centers.
    unique = {item["id"]: item for item in incidents}
    online = successful_centers > 0
    return {
        "online": online,
        "error": "; ".join(errors) if errors else None,
        "incidents": list(unique.values()),
    }
