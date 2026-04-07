import asyncio
import time
from typing import Dict, List
from app.scanner import ping_host, get_latency
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
    global _monitored_hosts
    _monitored_hosts = hosts


async def check_host(ip: str):
    previous_status = _host_status.get(ip, {}).get("status")
    latency = await get_latency(ip)
    is_up = latency is not None
    timestamp = int(time.time())
    uptime_pct = get_uptime_percent(ip, hours=24)

    _host_status[ip] = {
        "ip": ip,
        "status": "up" if is_up else "down",
        "latency_ms": latency,
        "last_checked": timestamp,
        "uptime_pct": uptime_pct,
        "just_went_down": previous_status == "up" and not is_up,
    }

    log_ping(ip, is_up, latency, timestamp)


async def start_monitor():
    while True:
        if _monitored_hosts:
            tasks = [check_host(ip) for ip in _monitored_hosts]
            await asyncio.gather(*tasks)
        await asyncio.sleep(MONITOR_INTERVAL)