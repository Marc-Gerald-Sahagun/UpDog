import asyncio
import time
from typing import Dict, List
from app.scanner import _ping_sync
from app.database import log_ping, get_uptime_percent

_host_status: Dict[str, dict] = {}
_monitored_hosts: List[str] = []

MONITOR_INTERVAL = 30


def add_host(ip: str):
    if ip not in _monitored_hosts:
        _monitored_hosts.append(ip)


def remove_host(ip: str):
    if ip in _monitored_hosts:
        _monitored_hosts.remove(ip)
    _host_status.pop(ip, None)


def get_host_status() -> List[dict]:
    return list(_host_status.values())


def set_monitored_hosts(hosts: List[str]):
    """Merge hosts into the monitored list (does not replace)."""
    for ip in hosts:
        add_host(ip)


def load_hosts_from_db():
    """Restore monitored hosts from the database on startup."""
    from app.database import get_all_hosts
    for h in get_all_hosts():
        add_host(h["ip"])


async def check_host(ip: str):
    is_up, latency = await asyncio.to_thread(_ping_sync, ip)
    timestamp = int(time.time())

    log_ping(ip, is_up, latency, timestamp)

    uptime_pct = get_uptime_percent(ip, hours=24)

    _host_status[ip] = {
        "ip": ip,
        "status": "up" if is_up else "down",
        "latency_ms": latency,
        "last_checked": timestamp,
        "uptime_pct": uptime_pct,
    }


async def start_monitor():
    while True:
        if _monitored_hosts:
            tasks = [check_host(ip) for ip in _monitored_hosts]
            await asyncio.gather(*tasks)
        await asyncio.sleep(MONITOR_INTERVAL)
