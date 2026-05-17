"""
Tests for authentication endpoints.
Run with: pytest backend/tests/test_auth.py -v
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

ADMIN_EMAIL    = "admin@ppe.com"
ADMIN_PASSWORD = "admin123"
OFFICER_EMAIL  = "officer@ppe.com"
OFFICER_PASSWORD = "officer123"


def test_login_admin_success():
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "admin"


def test_login_officer_success():
    resp = client.post("/auth/login", json={"email": OFFICER_EMAIL, "password": OFFICER_PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["role"] == "security_officer"


def test_login_wrong_password():
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_nonexistent_user():
    resp = client.post("/auth/login", json={"email": "nouser@ppe.com", "password": "anything"})
    assert resp.status_code == 401


def test_protected_route_no_token():
    resp = client.get("/violations/")
    assert resp.status_code == 401


def test_protected_route_invalid_token():
    resp = client.get("/violations/", headers={"Authorization": "Bearer badtoken"})
    assert resp.status_code == 401


def get_admin_token() -> str:
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    return resp.json()["access_token"]


def get_officer_token() -> str:
    resp = client.post("/auth/login", json={"email": OFFICER_EMAIL, "password": OFFICER_PASSWORD})
    return resp.json()["access_token"]
