"""
api_client.py — All HTTP calls to the FastAPI backend.
Every call attaches the JWT from st.session_state["token"].
"""

import requests
import streamlit as st
from typing import Optional, Dict, Any
import os

# Handle environment variable with fallback
BASE_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
if not BASE_URL:
    # If empty string, use default
    BASE_URL = "http://127.0.0.1:8000"
BASE_URL = BASE_URL.rstrip("/")

# Debug: log the URL being used (visible in Streamlit logs)
if not os.getenv("BACKEND_API_URL"):
    import warnings
    warnings.warn(
        "BACKEND_API_URL environment variable not set. Using default: " + BASE_URL,
        RuntimeWarning
    )


# ─────────────────────────────────────────────────────────────
# Common Helpers
# ─────────────────────────────────────────────────────────────
def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = st.session_state.get("token", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(path: str, params: Optional[Dict] = None) -> Any:
    r = requests.get(
        f"{BASE_URL}{path}",
        headers=_headers(),
        params=params,
        timeout=10
    )
    r.raise_for_status()
    return r.json()


def _post(path: str, data: Dict) -> Any:
    r = requests.post(
        f"{BASE_URL}{path}",
        json=data,
        headers=_headers(),
        timeout=10
    )
    r.raise_for_status()
    return r.json()


def _put(path: str, data: Optional[Dict] = None) -> Any:
    r = requests.put(
        f"{BASE_URL}{path}",
        json=data or {},
        headers=_headers(),
        timeout=10
    )
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> bool:
    r = requests.delete(
        f"{BASE_URL}{path}",
        headers=_headers(),
        timeout=10
    )
    return r.status_code == 204


# ─────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────
def login(email: str, password: str) -> Dict:
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────
def get_dashboard_stats() -> Dict:
    return _get("/dashboard/stats/")


# ─────────────────────────────────────────────────────────────
# Violations
# ─────────────────────────────────────────────────────────────
def get_violations(
    site_name=None,
    camera_name=None,
    status=None,
    date_from=None,
    date_to=None,
) -> list:
    params = {}

    if site_name:
        params["site_name"] = site_name
    if camera_name:
        params["camera_name"] = camera_name
    if status:
        params["status"] = status
    if date_from:
        params["date_from"] = str(date_from)
    if date_to:
        params["date_to"] = str(date_to)

    return _get("/violations/", params=params)


def resolve_violation(violation_id: int) -> Dict:
    return _put(f"/violations/{violation_id}/resolve")


# Optimized + fallback 
def get_latest_violations(limit: int = 5) -> list:
    try:
        return _get("/violations/latest", params={"limit": limit})
    except Exception:
        # fallback if endpoint not implemented
        try:
            return get_violations(status="open")[:limit]
        except Exception:
            return []


# ─────────────────────────────────────────────────────────────
# Cameras (for grid view)
# ─────────────────────────────────────────────────────────────
def get_cameras() -> list:
    try:
        return _get("/cameras/")
    except Exception:
        return []


# Support token-based streaming if needed
def get_stream_url(camera_id: int) -> str:
    token = st.session_state.get("token", "")

    # OPTION A: If backend is PUBLIC → just return simple URL
    if not token:
        return f"{BASE_URL}/stream/{camera_id}"

    # OPTION B: If backend requires auth → attach token in URL
    return f"{BASE_URL}/stream/{camera_id}?token={token}"


# ─────────────────────────────────────────────────────────────
# Sites
# ─────────────────────────────────────────────────────────────
def get_sites() -> list:
    return _get("/sites/")


def create_site(name: str, location: str, description: str, ppe_requirements: list) -> Dict:
    return _post(
        "/sites/",
        {
            "name": name,
            "location": location,
            "description": description,
            "ppe_requirements": ppe_requirements,
        },
    )


def update_site(site_name: str, data: Dict) -> Dict:
    return _put(f"/sites/{site_name}", data)


def delete_site(site_name: str) -> bool:
    return _delete(f"/sites/{site_name}")


# ─────────────────────────────────────────────────────────────
# Workers
# ─────────────────────────────────────────────────────────────
def get_workers() -> list:
    return _get("/workers/")


def create_worker(
    employee_id: str,
    full_name: str,
    department: str,
    site_name: Optional[str],
) -> Dict:
    return _post(
        "/workers/",
        {
            "employee_id": employee_id,
            "full_name": full_name,
            "department": department,
            "site_name": site_name,
        },
    )


def update_worker(employee_id: str, data: Dict) -> Dict:
    return _put(f"/workers/{employee_id}", data)


def delete_worker(employee_id: str) -> bool:
    return _delete(f"/workers/{employee_id}")


def upload_face(employee_id: str, file_bytes: bytes, filename: str) -> Dict:
    r = requests.post(
        f"{BASE_URL}/workers/{employee_id}/upload-face",
        headers=_headers(),
        files={"file": (filename, file_bytes, "image/jpeg")},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()