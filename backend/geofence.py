from __future__ import annotations

import math


def distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.7613
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def compass_direction(degrees: float) -> str:
    directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return directions[round(degrees / 45) % 8]


def enrich_and_filter(incident: dict, home_lat: float, home_lon: float, radius_miles: float) -> dict | None:
    lat = incident.get("latitude")
    lon = incident.get("longitude")
    if lat is None or lon is None:
        return None
    distance = distance_miles(home_lat, home_lon, float(lat), float(lon))
    if distance > radius_miles:
        return None
    bearing = bearing_degrees(home_lat, home_lon, float(lat), float(lon))
    result = dict(incident)
    result["distance_miles"] = round(distance, 1)
    result["bearing_degrees"] = round(bearing)
    result["direction"] = compass_direction(bearing)
    return result
