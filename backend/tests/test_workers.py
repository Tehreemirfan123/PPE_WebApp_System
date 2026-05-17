"""
Tests for /workers/ endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def get_admin_token():
    r = client.post("/auth/login", json={"email": "admin@ppe.com", "password": "admin123"})
    return r.json()["access_token"]


def get_officer_token():
    r = client.post("/auth/login", json={"email": "officer@ppe.com", "password": "officer123"})
    return r.json()["access_token"]


def admin_headers():
    return {"Authorization": f"Bearer {get_admin_token()}"}


def officer_headers():
    return {"Authorization": f"Bearer {get_officer_token()}"}


def test_officer_cannot_create_worker():
    resp = client.post("/workers/", json={
        "employee_id": "TEST-999", "full_name": "Test Worker"
    }, headers=officer_headers())
    assert resp.status_code == 403


def test_admin_can_list_workers():
    resp = client.get("/workers/", headers=admin_headers())
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_update_delete_worker():
    headers = admin_headers()

    # Create
    resp = client.post("/workers/", json={
        "employee_id": "EMP-TEST-001",
        "full_name":   "Test Worker",
        "department":  "QA",
    }, headers=headers)
    assert resp.status_code == 201
    employee_id = resp.json()["employee_id"]

    # Update
    resp = client.put(f"/workers/{employee_id}", json={"full_name": "Updated Name"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"

    # Delete
    resp = client.delete(f"/workers/{employee_id}", headers=headers)
    assert resp.status_code == 204


def test_duplicate_employee_id():
    headers = admin_headers()
    payload = {"employee_id": "EMP-DUP-001", "full_name": "Worker A"}
    client.post("/workers/", json=payload, headers=headers)
    resp2 = client.post("/workers/", json=payload, headers=headers)
    assert resp2.status_code == 400
