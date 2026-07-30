from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    home_latitude: float = 33.97015801797804
    home_longitude: float = -117.04995849775626
    radius_miles: float = 25.0
    api_port: int = 5053
    rvc_fire_refresh_seconds: int = 60
    chp_refresh_seconds: int = 60
    database_path: Path = BASE_DIR / "data" / "incidents.db"
    geocode_cache_path: Path = BASE_DIR / "cache" / "geocode-cache.json"
    log_path: Path = BASE_DIR / "logs" / "backend.log"


SETTINGS = Settings()
