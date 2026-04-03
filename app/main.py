from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from contextlib import asynccontextmanager
import asyncio

from app.scanner import scan_subnet
from app.monitor import start_monitor, get_host_status
from app.database import init_db, get_recent_latency

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
    return {"hosts": hosts}


@app.get("/api/status")
async def status():
    return {"hosts": get_host_status()}


@app.get("/api/latency/{host}")
async def latency(host: str):
    data = get_recent_latency(host)
    return {"host": host, "latency": data}