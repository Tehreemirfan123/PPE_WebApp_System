"""
FastAPI Application Entry Point
PPE Detection System — Backend API
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import auth, workers, sites, detection, violations, dashboard

app = FastAPI(
    title="PPE Detection System API",
    description=(
        "Backend API for the PPE (Personal Protective Equipment) Detection System. "
        "Manages workers, sites, detection events, and violations."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS (allow Streamlit on same machine) ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static files — serve saved violation images ──────────────────────────────
os.makedirs(settings.saved_violations_dir, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.saved_violations_dir), name="images")

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(workers.router)
app.include_router(sites.router)
app.include_router(detection.router)
app.include_router(violations.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "PPE Detection System API is running"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
