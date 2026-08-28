import sqlite3
import types

from fastapi.testclient import TestClient

import main
from scan_access import AccessTicket, ScanAccessManager


DEVICE = "device-token-123456789"
HEADERS = {"X-Trilloka-Device-ID": DEVICE, "Origin": "https://trilloka.com"}


def test_durable_job_is_owned_by_same_device_and_replays_result(tmp_path):
    manager = ScanAccessManager(str(tmp_path / "access.sqlite3"))
    ticket = AccessTicket(mode="free", usage_id=1, subject_hash=None, domain_key="example.com")
    job_id = manager.create_scan_job(ticket, device_id=DEVICE)

    assert manager.get_scan_job(job_id, device_id=DEVICE)["status"] == "processing"
    assert manager.get_scan_job(job_id, device_id="different-device-token-999") is None

    manager.complete_scan_job(job_id, {"overall_score": 40.8})
    job = manager.find_device_domain_job(device_id=DEVICE, domain_key="example.com")
    assert job["status"] == "complete"
    assert job["result"]["overall_score"] == 40.8


def test_scan_start_poll_and_same_url_review_does_not_consume_second_free_scan(tmp_path, monkeypatch):
    manager = ScanAccessManager(str(tmp_path / "access.sqlite3"))
    monkeypatch.setattr(main, "access_manager", manager)
    monkeypatch.setattr(main, "handle_trilloka_guardrail", lambda domain: None)
    monkeypatch.setattr(
        main,
        "validate_public_http_url",
        lambda domain: types.SimpleNamespace(url="https://example.com/"),
    )

    async def fake_execute_reserved_scan(**kwargs):
        manager.finish(kwargs["ticket"], success=True)
        return {
            "overall_score": 40.8,
            "score_rating": "MATERIAL COMMERCIAL WEAKNESSES",
            "target_domain": "https://example.com/",
            "scan_access": {"mode": "free", "cached": False},
        }

    monkeypatch.setattr(main, "_execute_reserved_scan", fake_execute_reserved_scan)
    client = TestClient(main.app)

    first = client.post("/api/scan/start", headers=HEADERS, json={"domain": "example.com", "business_type": "auto"})
    assert first.status_code == 202
    job_id = first.json()["job"]["job_id"]

    status = client.get(f"/api/scan/status/{job_id}", headers=HEADERS)
    assert status.status_code == 200
    assert status.json()["state"] == "complete"

    review = client.post("/api/scan/start", headers=HEADERS, json={"domain": "example.com", "business_type": "auto"})
    assert review.status_code == 200
    body = review.json()
    assert body["state"] == "complete"
    assert body["replayed"] is True
    assert body["fresh_scan_run"] is False
    assert body["result"]["scan_replay"]["fresh_scan_run"] is False

    with sqlite3.connect(manager.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM free_usage").fetchone()[0]
    assert count == 1


def test_reentering_url_while_processing_resumes_same_job_without_new_reservation(tmp_path, monkeypatch):
    manager = ScanAccessManager(str(tmp_path / "access.sqlite3"))
    monkeypatch.setattr(main, "access_manager", manager)
    monkeypatch.setattr(main, "handle_trilloka_guardrail", lambda domain: None)
    monkeypatch.setattr(
        main,
        "validate_public_http_url",
        lambda domain: types.SimpleNamespace(url="https://example.com/"),
    )

    ticket = manager.reserve(
        ip="1.2.3.4",
        device_id=DEVICE,
        email=None,
        domain_key="example.com",
        access_pass=None,
        admin_bypass=False,
    )
    job_id = manager.create_scan_job(ticket, device_id=DEVICE)

    client = TestClient(main.app)
    response = client.post("/api/scan/start", headers=HEADERS, json={"domain": "example.com", "business_type": "auto"})
    assert response.status_code == 202
    assert response.json()["resumed"] is True
    assert response.json()["job"]["job_id"] == job_id

    with sqlite3.connect(manager.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM free_usage").fetchone()[0]
    assert count == 1
