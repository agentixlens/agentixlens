"""
AgentixLens Backend — main.py
FastAPI server: ingests traces from the SDK and serves the dashboard API.

Run dev server:
    uvicorn main:app --reload --port 4317

Docker:
    docker build -t agentixlens-server .
    docker run -p 4317:4317 agentixlens-server
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from db.database import init_db
from routers import ingest, traces, stats, alerts


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    print("✓ AgentixLens backend started")
    print("✓ Dashboard: http://localhost:4317")
    print("✓ API docs:  http://localhost:4317/docs")
    yield
    # Shutdown
    print("AgentixLens backend stopped.")


app = FastAPI(
    title="AgentixLens API",
    description="AI Agent Observability Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow SDK and dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(ingest.router,  prefix="/v1", tags=["Ingest"])
app.include_router(traces.router,  prefix="/v1", tags=["Traces"])
app.include_router(stats.router,   prefix="/v1", tags=["Stats"])
app.include_router(alerts.router,  prefix="/v1", tags=["Alerts"])

# Serve dashboard static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "dashboard_dist")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/dashboard/{full_path:path}")
    async def serve_dashboard(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/dashboard")
    async def dashboard_root():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/")
async def root():
    return {
        "service": "AgentixLens",
        "version": "0.1.0",
        "status": "ok",
        "docs": "/docs",
        "dashboard": "/dashboard",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
