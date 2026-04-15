from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import asyncio
import csv
import io
import ipaddress
import time
import sys

from app.scanner import scan_subnet
from app.monitor import (
    start_monitor, get_host_status, set_monitored_hosts,
    add_host as monitor_add_host, remove_host as monitor_remove_host,
    load_hosts_from_db,
)
from app.database import (
    init_db, get_recent_latency, get_uptime_percent,
    upsert_host, remove_host_from_db, get_all_hosts,
    update_host_field, get_host_history,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_hosts_from_db()
    asyncio.create_task(start_monitor())
    yield


app = FastAPI(title="UpDog", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Scan ──────────────────────────────────────────────────────────────────────

@app.get("/api/scan")
async def scan(subnet: str = "192.168.1.0/24"):
    hosts = await scan_subnet(subnet)
    for host in hosts:
        monitor_add_host(host["ip"])
        upsert_host(
            host["ip"],
            hostname=host.get("hostname"),
            open_ports=host.get("open_ports", []),
            manually_added=False,
        )
        host["uptime_pct"] = get_uptime_percent(host["ip"], hours=24)
    return {"hosts": hosts}


# ── Live status ───────────────────────────────────────────────────────────────

@app.get("/api/status")
async def status():
    return {"hosts": get_host_status()}


# ── Latency history ───────────────────────────────────────────────────────────

@app.get("/api/latency/{host}")
async def latency(host: str):
    data = get_recent_latency(host)
    return {"host": host, "latency": data}


@app.get("/api/hosts/{ip}/history")
async def host_history(ip: str, hours: int = 24):
    data = get_host_history(ip, hours=hours)
    return {"host": ip, "latency": data}


# ── Hosts CRUD ────────────────────────────────────────────────────────────────

@app.get("/api/hosts")
async def list_hosts():
    db_hosts = get_all_hosts()
    status_map = {h["ip"]: h for h in get_host_status()}
    for host in db_hosts:
        live = status_map.get(host["ip"], {})
        host["status"] = live.get("status", "unknown")
        host["latency_ms"] = live.get("latency_ms")
        host["uptime_pct"] = live.get("uptime_pct", get_uptime_percent(host["ip"]))
        host["last_checked"] = live.get("last_checked")
    return {"hosts": db_hosts}


@app.post("/api/hosts")
async def add_host(ip: str, label: str = "", group_name: str = ""):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IP address")
    upsert_host(ip, manually_added=True)
    if label:
        update_host_field(ip, "label", label)
    if group_name:
        update_host_field(ip, "group_name", group_name)
    monitor_add_host(ip)
    return {"ok": True}


@app.delete("/api/hosts/{ip}")
async def delete_host(ip: str):
    remove_host_from_db(ip)
    monitor_remove_host(ip)
    return {"ok": True}


@app.patch("/api/hosts/{ip}")
async def update_host(ip: str, field: str, value: str):
    ok = update_host_field(ip, field, value)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Field '{field}' is not editable")
    return {"ok": True}


# ── CSV export ────────────────────────────────────────────────────────────────

@app.get("/api/export/csv")
async def export_csv():
    """Export current host status + uptime as a CSV download."""
    hosts = get_host_status()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["IP Address", "Status", "Latency (ms)", "Uptime % (24h)", "Last Checked"])

    for host in hosts:
        last_checked = (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(host["last_checked"]))
            if host.get("last_checked")
            else ""
        )
        writer.writerow([
            host.get("ip", ""),
            host.get("status", ""),
            host.get("latency_ms", ""),
            host.get("uptime_pct", ""),
            last_checked,
        ])

    output.seek(0)
    filename = f"updog-export-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
