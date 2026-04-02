import asyncio
import time
from typing import Dict, List
from app.scanner import ping_host, get_latency
from app.database import log_ping

# In-memory host state — updated by the monitor loop
_host_status: Dict[str, dict] = {}

# Hosts being actively monitored
_monitored_hosts: List[str] = []

MONITOR_INTERVAL = 30  # seconds between ping sweeps


def add_host(ip: str):
    """Add a host to the monitoring list."""
    if ip not in _monitored_hosts:
        _monitored_hosts.append(ip)


def remove_host(ip: str):
    """Remove a host from monitoring."""
    if ip in _monitored_hosts:
        _monitored_hosts.remove(ip)
    _host_status.pop(ip, None)


def get_host_status() -> List[dict]:
    """Return current status of all monitored hosts."""
    return list(_host_status.values())


def set_monitored_hosts(hosts: List[str]):
    """Replace the monitored host list (called after a scan)."""
    global _monitored_hosts
    _monitored_hosts = hosts


async def check_host(ip: str):
    """Ping a host, update its status, and log the result."""
    latency = await get_latency(ip)
    is_up = latency is not None
    timestamp = int(time.time())

    _host_status[ip] = {
        "ip": ip,
        "status": "up" if is_up else "down",
        "latency_ms": latency,
        "last_checked": timestamp
    }

    log_ping(ip, is_up, latency, timestamp)


async def start_monitor():
    """Background task — continuously monitors all tracked hosts."""
    while True:
        if _monitored_hosts:
            tasks = [check_host(ip) for ip in _monitored_hosts]
            await asyncio.gather(*tasks)
        await asyncio.sleep(MONITOR_INTERVAL)