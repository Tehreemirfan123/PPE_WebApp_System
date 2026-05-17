"""
Tests for /sites/ endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def admin_headers():
    r = client.post("/auth/login", json={"email": "admin@ppe.com", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_list_sites_returns_defaults():
    resp = client.get("/sites/", headers=admin_headers())
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    for expected in ["Construction Site", "Chemical Lab", "Factory", "Warehouse"]:
        assert expected in names


def test_cannot_delete_default_site():
    resp = client.get("/sites/", headers=admin_headers())
    default_site = next(s for s in resp.json() if s["is_default"])
    del_resp = client.delete(f"/sites/{default_site['name']}", headers=admin_headers())
    assert del_resp.status_code == 403


def test_cannot_update_default_site():
    resp = client.get("/sites/", headers=admin_headers())
    default_site = next(s for s in resp.json() if s["is_default"])
    put_resp = client.put(f"/sites/{default_site['name']}", json={"location": "Hacked"}, headers=admin_headers())
    assert put_resp.status_code == 403


def test_create_update_delete_site():
    headers = admin_headers()

    # Create
    resp = client.post("/sites/", json={
        "name": "Test Lab Z", "location": "Floor 9", "ppe_requirements": ["gloves", "helmet"]
    }, headers=headers)
    assert resp.status_code == 201
    site_name = resp.json()["name"]

    # Update
    resp = client.put(f"/sites/{site_name}", json={"location": "Floor 10"}, headers=headers)
    assert resp.status_code == 200

    # Delete
    resp = client.delete(f"/sites/{site_name}", headers=headers)
    assert resp.status_code == 204
