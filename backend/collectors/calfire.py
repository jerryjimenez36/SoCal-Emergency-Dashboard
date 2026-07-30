from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import requests

LOG = logging.getLogger(__name__)

# Official interagency IRWIN/NIFC wildfire incident layer.
ARCGIS_QUERY_URL = (
    "https://services9.arcgis.com/RHVPKKiFTONKtxq3/"
    "ArcGIS/rest/services/USA_Wildfires_v1/"
    "FeatureServer/0/query"
)

HEADERS = {
    "User-Agent": (
        "SoCal-Emergency-Dashboard/0.4 "
        "(personal emergency display)"
    )
}


def _first(attributes: dict, *names, default=None):
    for name in names:
        value = attributes.get(name)

        if value not in (None, ""):
            return value

    return default


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value):
    number = _number(value)

    if number is None:
        return None

    return int(round(number))


def _timestamp(value):
    if value in (None, ""):
        return None

    try:
        milliseconds = float(value)
        moment = datetime.fromtimestamp(
            milliseconds / 1000,
            tz=timezone.utc,
        )
        return moment.isoformat()
    except (TypeError, ValueError, OSError):
        return str(value)


def _incident_id(attributes: dict, name: str) -> str:
    source_id = _first(
        attributes,
        "IrwinID",
        "IRWINID",
        "UniqueFireIdentifier",
        "OBJECTID",
        default=name,
    )

    digest = hashlib.sha1(
        str(source_id).encode("utf-8")
    ).hexdigest()[:12]

    return f"wildfire-{digest}"


def _parse_feature(feature: dict) -> dict | None:
    attributes = feature.get("attributes") or {}
    geometry = feature.get("geometry") or {}

    longitude = _number(geometry.get("x"))
    latitude = _number(geometry.get("y"))

    if latitude is None or longitude is None:
        latitude = _number(
            _first(
                attributes,
                "InitialLatitude",
                "POO_Latitude",
                "Latitude",
            )
        )
        longitude = _number(
            _first(
                attributes,
                "InitialLongitude",
                "POO_Longitude",
                "Longitude",
            )
        )

    if latitude is None or longitude is None:
        return None

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    name = str(
        _first(
            attributes,
            "IncidentName",
            "Incident_Name",
            default="Unnamed Wildfire",
        )
    ).strip()

    incident_category = str(
        _first(
            attributes,
            "IncidentTypeCategory",
            "IncidentTypeKind",
            default="WF",
        )
    ).upper()

    # Do not display prescribed burns as emergency wildfires.
    if incident_category == "RX":
        return None

    county = str(
        _first(
            attributes,
            "POOCounty",
            "County",
            "POOCountyName",
            default="Unknown County",
        )
    ).strip()

    acres = _integer(
        _first(
            attributes,
            "DailyAcres",
            "CalculatedAcres",
            "GISAcres",
            "DiscoveryAcres",
        )
    )

    containment = _integer(
        _first(
            attributes,
            "PercentContained",
            "PercentContainment",
        )
    )

    agency = str(
        _first(
            attributes,
            "POOResponsibleUnit",
            "POOProtectingAgency",
            "Source",
            default="NIFC / IRWIN",
        )
    ).strip()

    location = str(
        _first(
            attributes,
            "IncidentShortDescription",
            "POOPlaceName",
            "FireLocation",
            default=f"{name}, {county}",
        )
    ).strip()

    discovered = _timestamp(
        _first(
            attributes,
            "FireDiscoveryDateTime",
            "FireDiscoveryDateTime_dt",
            "CreatedOnDateTime",
        )
    )

    details = []

    if acres is not None:
        details.append(f"{acres:,} acres")

    if containment is not None:
        details.append(f"{containment}% contained")

    incident_type = f"{name} Wildfire"

    if details:
        incident_type += f" ({', '.join(details)})"

    return {
        "id": _incident_id(attributes, name),
        "agency": agency,
        "source": "calfire",
        "category": "fire",
        "type": incident_type,
        "street": location,
        "community": county,
        "location": location,
        "incident_time": discovered,
        "latitude": latitude,
        "longitude": longitude,
        "location_approximate": False,
        "priority": "critical",
        "priority_rank": 1,
        "wildfire_name": name,
        "county": county,
        "acres": acres,
        "containment_percent": containment,
    }


def fetch() -> dict:
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }

    try:
        response = requests.get(
            ARCGIS_QUERY_URL,
            params=params,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()

        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))

        incidents = []

        for feature in payload.get("features", []):
            incident = _parse_feature(feature)

            if incident is not None:
                incidents.append(incident)

        return {
            "online": True,
            "error": None,
            "incidents": incidents,
        }

    except Exception as exc:
        LOG.exception("Wildfire collector failed")

        return {
            "online": False,
            "error": str(exc),
            "incidents": [],
        }
