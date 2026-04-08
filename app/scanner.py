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


async def ping_host(ip: str) -> bool:
    """Ping a single host and return True if alive."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2000", ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await asyncio.wait_for(proc.wait(), timeout=2)
        return proc.returncode == 0
    except Exception:
        return False


async def get_latency(ip: str) -> float | None:
    """Return ping latency in ms, or None if unreachable."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2000", ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
        output = stdout.decode()
        if "time=" in output:
            time_str = output.split("time=")[1].split(" ")[0]
            return float(time_str)
    except Exception:
        pass
    return None


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
    alive = await ping_host(ip)
    if not alive:
        return None

    latency, open_ports, hostname = await asyncio.gather(
        get_latency(ip),
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

    # Limit to /24 max to avoid runaway scans
    hosts = list(network.hosts())[:254]
    tasks = [scan_host(str(ip)) for ip in hosts]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]