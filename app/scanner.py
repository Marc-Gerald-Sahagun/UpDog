import asyncio
import socket
import subprocess
import ipaddress
import sys
from typing import List, Dict


COMMON_PORTS = [22, 23, 25, 53, 80, 110, 143, 443, 445, 3306, 3389, 8080, 8443]

PORT_SERVICES = {
    22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 3306: "MySQL", 3389: "RDP", 8080: "HTTP-Alt", 8443: "HTTPS-Alt"
}

IS_WINDOWS = sys.platform == "win32"


def _ping_args(ip: str):
    if IS_WINDOWS:
        return ["ping", "-n", "1", "-w", "2000", ip]
    else:
        return ["ping", "-c", "1", "-W", "2000", ip]


def _parse_latency(output: str):
    try:
        if IS_WINDOWS:
            if "time<" in output:
                return 0.5  # less than 1ms, return 0.5 as approximation
            if "time=" in output:
                time_str = output.split("time=")[1].split("ms")[0].strip()
                return float(time_str)
        else:
            if "time=" in output:
                time_str = output.split("time=")[1].split(" ")[0]
                return float(time_str)
    except Exception:
        return None
    return None

def _ping_sync(ip: str) -> tuple:
    """Synchronous ping — runs in a thread."""
    try:
        result = subprocess.run(
            _ping_args(ip),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            latency = _parse_latency(result.stdout)
            return True, latency
        return False, None
    except Exception:
        return False, None


async def ping_host(ip: str) -> bool:
    is_up, _ = await asyncio.to_thread(_ping_sync, ip)
    return is_up


async def get_latency(ip: str) -> float | None:
    _, latency = await asyncio.to_thread(_ping_sync, ip)
    return latency


async def scan_port(ip: str, port: int) -> bool:
    """Check if a TCP port is open."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=1
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def scan_ports(ip: str) -> List[Dict]:
    """Scan common ports on a host and return open ones."""
    tasks = {port: scan_port(ip, port) for port in COMMON_PORTS}
    results = await asyncio.gather(*tasks.values())
    open_ports = []
    for port, is_open in zip(tasks.keys(), results):
        if is_open:
            open_ports.append({
                "port": port,
                "service": PORT_SERVICES.get(port, "Unknown")
            })
    return open_ports


def resolve_hostname(ip: str) -> str:
    """Try to resolve a hostname from an IP address."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip


async def scan_host(ip: str) -> Dict | None:
    """Scan a single host — ping, latency, ports, hostname."""
    is_up, latency = await asyncio.to_thread(_ping_sync, ip)
    if not is_up:
        return None

    open_ports, hostname = await asyncio.gather(
        scan_ports(ip),
        asyncio.to_thread(resolve_hostname, ip)
    )

    return {
        "ip": ip,
        "hostname": hostname,
        "status": "up",
        "latency_ms": latency,
        "open_ports": open_ports
    }


async def scan_subnet(subnet: str) -> List[Dict]:
    """Scan all hosts in a subnet concurrently."""
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return []

    hosts = list(network.hosts())[:254]
    results = []
    batch_size = 20

    for i in range(0, len(hosts), batch_size):
        batch = hosts[i:i + batch_size]
        batch_results = await asyncio.gather(*[scan_host(str(ip)) for ip in batch])
        results.extend(batch_results)

    return [r for r in results if r is not None]