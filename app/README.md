# UpDog - Network Monitor

A network monitoring tool I built to track devices on a local network.
It scans for live hosts, checks open ports, and displays latency and
uptime data on a web dashboard that updates in real time.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal?style=flat&logo=fastapi)

---

## What it does

- Scans a subnet and identifies live hosts
- Checks which TCP ports are open on each device
- Pings hosts on an interval and logs whether they're up or down
- Shows everything on a live dashboard with latency graphs

---

## Tech

- **Backend:** Python, FastAPI, asyncio
- **Frontend:** HTML, CSS, Chart.js
- **Database:** SQLite
- **Networking:** socket, scapy

---

## Running it locally
```bash
git clone https://github.com/YOUR_USERNAME/netwatch.git
cd netwatch
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000` in your browser.

---

## Project structure
```
netwatch/
├── app/
│   ├── main.py        # entry point
│   ├── scanner.py     # host discovery and port scanning
│   ├── monitor.py     # uptime tracking loop
│   └── database.py    # SQLite logging
├── static/
│   ├── css/styles.css
│   └── js/dashboard.js
├── templates/
│   └── index.html
└── requirements.txt
```

---

## Planned features

- Alerts when a host goes down
- Docker support
- CSV export for uptime reports

---

## Screenshot

> coming once the dashboard is built