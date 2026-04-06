from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import asyncio
import csv
import io
import time

from app.scanner import scan_subnet
from app.monitor import start_monitor, get_host_status, set_monitored_hosts
from app.database import init_db, get_recent_latency, get_uptime_percent

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(start_monitor())
    yield

app = FastAPI(title="UpDog", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/scan")
async def scan(subnet: str = "192.168.1.0/24"):
    hosts = await scan_subnet(subnet)
    # Kick off monitoring for discovered hosts
    set_monitored_hosts([h["ip"] for h in hosts])
    # Attach uptime % (will be 0 on first scan, that's fine)
    for host in hosts:
        host["uptime_pct"] = get_uptime_percent(host["ip"], hours=24)
    return {"hosts": hosts}


@app.get("/api/status")
async def status():
    return {"hosts": get_host_status()}


@app.get("/api/latency/{host}")
async def latency(host: str):
    data = get_recent_latency(host)
    return {"host": host, "latency": data}


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