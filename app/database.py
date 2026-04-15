import sqlite3
import time
import json
from typing import List, Dict

DB_PATH = "netwatch.db"

_ALLOWED_HOST_FIELDS = {"label", "group_name"}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ping_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                is_up INTEGER NOT NULL,
                latency_ms REAL,
                timestamp INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hosts (
                ip TEXT PRIMARY KEY,
                label TEXT DEFAULT '',
                group_name TEXT DEFAULT '',
                hostname TEXT DEFAULT '',
                open_ports TEXT DEFAULT '[]',
                manually_added INTEGER DEFAULT 0,
                added_at INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip ON ping_log (ip)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ping_log (timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_ts ON ping_log (ip, timestamp)")
        conn.commit()


def log_ping(ip: str, is_up: bool, latency_ms: float | None, timestamp: int = None):
    """Log a single ping result."""
    if timestamp is None:
        timestamp = int(time.time())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO ping_log (ip, is_up, latency_ms, timestamp) VALUES (?, ?, ?, ?)",
            (ip, int(is_up), latency_ms, timestamp)
        )
        conn.commit()


def get_recent_latency(ip: str, limit: int = 60) -> List[Dict]:
    """Return the last N latency readings for a host."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT latency_ms, timestamp FROM ping_log
            WHERE ip = ? AND is_up = 1
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (ip, limit)
        ).fetchall()
    return [{"latency_ms": r["latency_ms"], "timestamp": r["timestamp"]} for r in reversed(rows)]


def get_uptime_percent(ip: str, hours: int = 24) -> float:
    """Calculate uptime % for a host over the last N hours."""
    since = int(time.time()) - (hours * 3600)
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM ping_log WHERE ip = ? AND timestamp >= ?",
            (ip, since)
        ).fetchone()[0]
        up = conn.execute(
            "SELECT COUNT(*) FROM ping_log WHERE ip = ? AND timestamp >= ? AND is_up = 1",
            (ip, since)
        ).fetchone()[0]
    if total == 0:
        return 0.0
    return round((up / total) * 100, 2)


# ── Hosts table ──────────────────────────────────────────────────────────────

def upsert_host(ip: str, hostname: str = None, open_ports: list = None, manually_added: bool = False):
    """Insert a host record, or update hostname/open_ports if it already exists.

    Existing label and group_name are never overwritten by this function so
    that user-set values survive re-scans.
    """
    ports_json = json.dumps(open_ports) if open_ports is not None else None
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO hosts (ip, hostname, open_ports, manually_added, added_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                hostname   = COALESCE(excluded.hostname,    hostname),
                open_ports = COALESCE(excluded.open_ports,  open_ports)
        """, (ip, hostname, ports_json, int(manually_added), int(time.time())))
        conn.commit()


def remove_host_from_db(ip: str):
    """Remove a host record (ping history is kept)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM hosts WHERE ip = ?", (ip,))
        conn.commit()


def get_all_hosts() -> List[Dict]:
    """Return all host records."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM hosts ORDER BY added_at").fetchall()
    result = []
    for r in rows:
        host = dict(r)
        try:
            host["open_ports"] = json.loads(host.get("open_ports") or "[]")
        except (json.JSONDecodeError, TypeError):
            host["open_ports"] = []
        result.append(host)
    return result


def update_host_field(ip: str, field: str, value: str) -> bool:
    """Update a single metadata field (label or group_name) for a host."""
    if field not in _ALLOWED_HOST_FIELDS:
        return False
    with get_connection() as conn:
        conn.execute(f"UPDATE hosts SET {field} = ? WHERE ip = ?", (value, ip))
        conn.commit()
    return True


def get_host_history(ip: str, hours: int = 24) -> List[Dict]:
    """Return time-bucketed average latency for a host over the past N hours."""
    since = int(time.time()) - (hours * 3600)

    if hours <= 1:
        bucket = 60        # 1-minute buckets
    elif hours <= 24:
        bucket = 1800      # 30-minute buckets
    else:
        bucket = 7200      # 2-hour buckets

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ROUND(AVG(latency_ms), 2) AS latency_ms,
                (timestamp / ?) * ? AS bucket_ts
            FROM ping_log
            WHERE ip = ? AND timestamp >= ? AND is_up = 1 AND latency_ms IS NOT NULL
            GROUP BY (timestamp / ?)
            ORDER BY bucket_ts ASC
            """,
            (bucket, bucket, ip, since, bucket)
        ).fetchall()
    return [{"latency_ms": r["latency_ms"], "timestamp": r["bucket_ts"]} for r in rows]
