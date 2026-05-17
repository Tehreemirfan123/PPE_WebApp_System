"""
Tests for /violations/ and /dashboard/stats/ endpoints.
"""

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def admin_headers():
    r = client.post("/auth/login", json={"email": "admin@ppe.com", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def officer_headers():
    r = client.post("/auth/login", json={"email": "officer@ppe.com", "password": "officer123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_get_violations_as_officer():
    resp = client.get("/violations/", headers=officer_headers())
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_violations_as_admin():
    resp = client.get("/violations/", headers=admin_headers())
    assert resp.status_code == 200


def test_get_violations_no_auth():
    resp = client.get("/violations/")
    assert resp.status_code == 401


def test_dashboard_stats_as_officer():
    resp = client.get("/dashboard/stats/", headers=officer_headers())
    assert resp.status_code == 200
    data = resp.json()
    for key in ["total_violations", "violations_today", "open_violations",
                "resolved_violations", "by_site", "compliance_rate"]:
        assert key in data


def test_dashboard_stats_no_auth():
    resp = client.get("/dashboard/stats/")
    assert resp.status_code == 401


def test_post_detection_event_missing_ppe_check():
    """Events with no missing PPE should be rejected."""
    headers = admin_headers()
    resp = client.post("/detection-event/", json={
        "site_name": "Construction Site", "detected_ppe": ["helmet", "gloves"], "missing_ppe": []
    }, headers=headers)
    assert resp.status_code == 400
