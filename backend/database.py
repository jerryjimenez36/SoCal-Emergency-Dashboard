from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from config import SETTINGS

TZ = ZoneInfo("America/Los_Angeles")


def connect() -> sqlite3.Connection:
    SETTINGS.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SETTINGS.database_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                agency TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT,
                incident_type TEXT,
                location TEXT,
                street TEXT,
                community TEXT,
                latitude REAL,
                longitude REAL,
                distance_miles REAL,
                bearing_degrees INTEGER,
                direction TEXT,
                priority TEXT,
                priority_rank INTEGER,
                incident_time TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                location_approximate INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_incidents_active ON incidents(active);
            CREATE INDEX IF NOT EXISTS idx_incidents_source ON incidents(source);
            CREATE INDEX IF NOT EXISTS idx_incidents_last_seen ON incidents(last_seen);
            """
        )


def upsert_source_incidents(source: str, incidents: list[dict]) -> None:
    now = datetime.now(TZ).isoformat()
    ids = [item["id"] for item in incidents]
    with connect() as conn:
        for item in incidents:
            conn.execute(
                """
                INSERT INTO incidents (
                    id, agency, source, category, incident_type, location, street, community,
                    latitude, longitude, distance_miles, bearing_degrees, direction, priority,
                    priority_rank, incident_time, first_seen, last_seen, active,
                    location_approximate, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    agency=excluded.agency, category=excluded.category,
                    incident_type=excluded.incident_type, location=excluded.location,
                    street=excluded.street, community=excluded.community,
                    latitude=excluded.latitude, longitude=excluded.longitude,
                    distance_miles=excluded.distance_miles,
                    bearing_degrees=excluded.bearing_degrees, direction=excluded.direction,
                    priority=excluded.priority, priority_rank=excluded.priority_rank,
                    incident_time=excluded.incident_time, last_seen=excluded.last_seen,
                    active=1, location_approximate=excluded.location_approximate,
                    raw_json=excluded.raw_json
                """,
                (
                    item["id"], item.get("agency", ""), source, item.get("category"),
                    item.get("type"), item.get("location"), item.get("street"),
                    item.get("community"), item.get("latitude"), item.get("longitude"),
                    item.get("distance_miles"), item.get("bearing_degrees"),
                    item.get("direction"), item.get("priority"), item.get("priority_rank", 99),
                    item.get("incident_time"), now, now,
                    int(bool(item.get("location_approximate"))),
                    json.dumps(item, separators=(",", ":")),
                ),
            )
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"UPDATE incidents SET active=0 WHERE source=? AND id NOT IN ({placeholders})",
                (source, *ids),
            )
        else:
            conn.execute("UPDATE incidents SET active=0 WHERE source=?", (source,))


def _rows(query: str, params: tuple = ()) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) | {"active": bool(row["active"]), "location_approximate": bool(row["location_approximate"])} for row in rows]


def get_active_incidents() -> list[dict]:
    return _rows("SELECT * FROM incidents WHERE active=1 ORDER BY priority_rank, distance_miles")


def get_recent_incidents(limit: int = 50) -> list[dict]:
    return _rows("SELECT * FROM incidents ORDER BY last_seen DESC LIMIT ?", (limit,))
