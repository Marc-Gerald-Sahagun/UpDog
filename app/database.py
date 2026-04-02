import sqlite3
import time
from typing import List, Dict

DB_PATH = "netwatch.db"


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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip ON ping_log (ip)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ping_log (timestamp)")
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