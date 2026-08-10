from __future__ import annotations

import time

import pytest

from scan_access import AccessDenied, PLAN_CATALOG, ScanAccessManager


def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAN_ACCESS_CONTROL_ENABLED", "true")
    monkeypatch.setenv("FREE_SCAN_LIMIT", "1")
    monkeypatch.setenv("FREE_SCAN_WINDOW_HOURS", "24")
    monkeypatch.setenv("FREE_SCAN_CACHE_HOURS", "24")
    monkeypatch.setenv("PAID_DUPLICATE_GRACE_SECONDS", "180")
    monkeypatch.setenv("SCAN_ACCESS_SECRET", "unit-test-secret")
    monkeypatch.setenv("PLAN_TIMEZONE", "America/Vancouver")
    return ScanAccessManager(str(tmp_path / "access.sqlite3"))


def activate(m: ScanAccessManager, email="buyer@example.com", domain="example.com", plan="essential_350"):
    return m.activate_plan(email=email, domain=domain, plan_id=plan, purchase_ref="test-order")


def test_free_preview_is_one_successful_scan_per_ip_or_device(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    t = m.reserve(ip="203.0.113.4", device_id="device-one-123", email=None, domain_key="a.example")
    assert t.mode == "free"
    m.finish(t, success=True)
    with pytest.raises(AccessDenied) as e:
        m.reserve(ip="203.0.113.4", device_id="another-device-123", email=None, domain_key="b.example")
    assert e.value.reason == "FREE_DAILY_LIMIT"
    with pytest.raises(AccessDenied):
        m.reserve(ip="198.51.100.20", device_id="device-one-123", email=None, domain_key="c.example")


def test_failed_free_scan_does_not_burn_allowance(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    t1 = m.reserve(ip="203.0.113.5", device_id="device-fail-123", email=None, domain_key="a.example")
    m.finish(t1, success=False)
    t2 = m.reserve(ip="203.0.113.5", device_id="device-fail-123", email=None, domain_key="b.example")
    assert t2.mode == "free"


def test_paid_plan_requires_email_domain_and_purchase_pass(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m)
    assert grant["plan"]["plan_id"] == "essential_350"
    assert len(grant["access_pass"]) >= 20

    with pytest.raises(AccessDenied) as e:
        m.reserve(
            ip="203.0.113.8",
            device_id="paid-device-123",
            email="buyer@example.com",
            domain_key="example.com",
            access_pass=None,
        )
    assert e.value.reason == "PAID_PASS_REQUIRED"

    # The pass is domain-bound. Another domain is only eligible for the normal free-preview path.
    t = m.reserve(
        ip="203.0.113.8",
        device_id="paid-device-123",
        email="buyer@example.com",
        domain_key="other.example",
        access_pass=grant["access_pass"],
    )
    assert t.mode == "free"


def test_essential_has_two_successful_fresh_scans_per_day(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m)
    for i in range(2):
        t = m.reserve(
            ip=f"203.0.113.{20+i}",
            device_id=f"essential-device-{i}-123",
            email="buyer@example.com",
            domain_key="example.com",
            access_pass=grant["access_pass"],
        )
        assert t.mode == "paid"
        assert t.remediation_limit == 3
        m.finish(t, success=True)
    status = m.entitlement_status("buyer@example.com", "example.com")
    assert status["scans_used_today"] == 2
    assert status["scans_remaining_today"] == 0
    with pytest.raises(AccessDenied) as e:
        m.reserve(
            ip="203.0.113.99",
            device_id="essential-last-123",
            email="buyer@example.com",
            domain_key="example.com",
            access_pass=grant["access_pass"],
        )
    assert e.value.reason == "PAID_DAILY_LIMIT"


def test_failed_paid_scan_does_not_consume_daily_allowance(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m, email="refund@example.com")
    t = m.reserve(
        ip="203.0.113.44",
        device_id="refund-device-123",
        email="refund@example.com",
        domain_key="example.com",
        access_pass=grant["access_pass"],
    )
    m.finish(t, success=False)
    status = m.entitlement_status("refund@example.com", "example.com")
    assert status["scans_used_today"] == 0
    assert status["scans_remaining_today"] == 2


def test_all_commercial_tiers_have_expected_limits(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    expected = {
        "essential_350": (2, 3, 0, None),
        "advanced_550": (3, 6, 1, None),
        "architect_850": (4, 10, 2, 15),
    }
    for i, (plan_id, values) in enumerate(expected.items()):
        email = f"tier{i}@example.com"
        domain = f"tier{i}.example"
        grant = activate(m, email=email, domain=domain, plan=plan_id)
        status = m.entitlement_status(email, domain, grant["access_pass"], require_pass=True)
        plan = status["plan"]
        assert (plan["scans_per_day"], plan["remediation_limit"], plan["guidance_calls"], plan["email_support_response_hours"]) == values


def test_admin_can_upgrade_or_downgrade_without_rotating_pass(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m)
    old_pass = grant["access_pass"]
    updated = m.update_entitlement(email="buyer@example.com", domain="example.com", plan_id="architect_850")
    assert updated["plan"]["plan_id"] == "architect_850"
    assert updated["plan"]["scans_per_day"] == 4
    assert updated["plan"]["remediation_limit"] == 10
    assert m.entitlement_status("buyer@example.com", "example.com", old_pass, require_pass=True)["pass_valid"] is True


def test_admin_can_extend_or_shorten_expiry(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    activate(m)
    original = m.entitlement_status("buyer@example.com", "example.com")["expires_at"]
    extended = m.update_entitlement(email="buyer@example.com", domain="example.com", extend_days=7)
    assert extended["expires_at"] == original + 7 * 86400
    shortened = m.update_entitlement(email="buyer@example.com", domain="example.com", extend_days=-2)
    assert shortened["expires_at"] == original + 5 * 86400
    exact = int(time.time()) + 86400
    exact_status = m.update_entitlement(email="buyer@example.com", domain="example.com", expires_at=exact)
    assert exact_status["expires_at"] == exact


def test_admin_revoke_and_restore_control_customer_access(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m)
    revoked = m.revoke_entitlement(email="buyer@example.com", domain="example.com")
    assert revoked["revoked"] is True
    with pytest.raises(AccessDenied) as e:
        m.reserve(
            ip="203.0.113.10",
            device_id="revoke-device-123",
            email="buyer@example.com",
            domain_key="example.com",
            access_pass=grant["access_pass"],
        )
    assert e.value.reason == "PAID_PLAN_REVOKED"
    restored = m.restore_entitlement(email="buyer@example.com", domain="example.com")
    assert restored["active"] is True
    t = m.reserve(
        ip="203.0.113.10",
        device_id="revoke-device-123",
        email="buyer@example.com",
        domain_key="example.com",
        access_pass=grant["access_pass"],
    )
    assert t.mode == "paid"


def test_admin_can_rotate_lost_or_compromised_pass(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m)
    old_pass = grant["access_pass"]
    rotated = m.rotate_access_pass(email="buyer@example.com", domain="example.com")
    new_pass = rotated["access_pass"]
    assert new_pass != old_pass
    assert m.entitlement_status("buyer@example.com", "example.com", old_pass, require_pass=True)["pass_valid"] is False
    assert m.entitlement_status("buyer@example.com", "example.com", new_pass, require_pass=True)["pass_valid"] is True


def test_admin_can_change_purchased_domain_and_keep_usage_history(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m)
    t = m.reserve(
        ip="203.0.113.11",
        device_id="domain-device-123",
        email="buyer@example.com",
        domain_key="example.com",
        access_pass=grant["access_pass"],
    )
    m.finish(t, success=True)
    changed = m.change_entitlement_domain(email="buyer@example.com", domain="example.com", new_domain="new.example")
    assert changed["domain"] == "new.example"
    assert changed["scans_used_today"] == 1
    assert m.entitlement_status("buyer@example.com", "example.com")["exists"] is False
    assert m.entitlement_status("buyer@example.com", "new.example", grant["access_pass"], require_pass=True)["pass_valid"] is True


def test_admin_can_reset_daily_scan_count(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    grant = activate(m)
    for i in range(2):
        t = m.reserve(
            ip=f"203.0.113.{70+i}",
            device_id=f"reset-device-{i}-123",
            email="buyer@example.com",
            domain_key="example.com",
            access_pass=grant["access_pass"],
        )
        m.finish(t, success=True)
    reset = m.reset_daily_usage(email="buyer@example.com", domain="example.com")
    assert reset["usage_rows_reset"] == 2
    assert reset["scans_used_today"] == 0
    assert reset["scans_remaining_today"] == 2


def test_guidance_calls_are_tracked_for_550_and_850(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    activate(m, email="advanced@example.com", plan="advanced_550")
    status = m.record_guidance_call(email="advanced@example.com", domain="example.com", delta=1)
    assert status["guidance_calls_used"] == 1
    assert status["guidance_calls_remaining"] == 0
    with pytest.raises(ValueError):
        m.record_guidance_call(email="advanced@example.com", domain="example.com", delta=1)

    activate(m, email="architect@example.com", domain="architect.example", plan="architect_850")
    one = m.record_guidance_call(email="architect@example.com", domain="architect.example", delta=1)
    assert one["guidance_calls_remaining"] == 1
    undone = m.record_guidance_call(email="architect@example.com", domain="architect.example", delta=-1)
    assert undone["guidance_calls_remaining"] == 2


def test_admin_can_grant_complimentary_custom_duration_plan(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    now = int(time.time())
    grant = m.activate_plan(
        email="comp@example.com",
        domain="comp.example",
        plan_id="architect_850",
        complimentary=True,
        duration_days_override=45,
    )
    assert grant["complimentary"] is True
    assert grant["purchase_ref"] == "COMPLIMENTARY"
    assert 44 * 86400 <= grant["expires_at"] - now <= 46 * 86400


def test_cache_normalizes_domain_and_contains_no_access_state(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    assert m.normalize_domain("https://www.Example.com/path") == "example.com"
    m.cache_put("example.com", {"success": True, "overall_score": 70.2})
    cached = m.cache_get("example.com", 86400)
    assert cached is not None
    payload, age = cached
    assert payload["overall_score"] == 70.2
    assert "scan_access" not in payload
    assert age >= 0


def test_admin_list_and_database_do_not_expose_raw_email_or_ip(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    email = "private-user@example.com"
    ip = "203.0.113.77"
    grant = activate(m, email=email, domain="privacy.example")
    t = m.reserve(
        ip=ip,
        device_id="privacy-device-123",
        email=email,
        domain_key="privacy.example",
        access_pass=grant["access_pass"],
    )
    m.finish(t, success=True)
    listing = m.list_entitlements()
    assert listing["count"] == 1
    assert "subject_ref" in listing["entitlements"][0]
    assert "email" not in listing["entitlements"][0]
    raw = (tmp_path / "access.sqlite3").read_bytes()
    assert email.encode() not in raw
    assert ip.encode() not in raw


def test_main_exposes_owner_admin_control_routes(monkeypatch, tmp_path):
    # Import after manager tests so the module can use an isolated access DB if needed.
    monkeypatch.setenv("SCAN_ACCESS_DB_PATH", str(tmp_path / "main.sqlite3"))
    monkeypatch.setenv("SCAN_ACCESS_SECRET", "unit-test-secret")
    import importlib
    import main as main_module

    main_module = importlib.reload(main_module)
    paths = {route.path for route in main_module.app.routes}
    expected = {
        "/api/admin/activate-plan",
        "/api/admin/scan-usage",
        "/api/admin/entitlements",
        "/api/admin/entitlement/status",
        "/api/admin/entitlement/update",
        "/api/admin/entitlement/revoke",
        "/api/admin/entitlement/restore",
        "/api/admin/entitlement/rotate-pass",
        "/api/admin/entitlement/change-domain",
        "/api/admin/entitlement/reset-daily-usage",
        "/api/admin/entitlement/guidance-call",
        "/api/plan/status",
        "/api/audit",
        "/api/scan",
    }
    assert expected.issubset(paths)
    assert PLAN_CATALOG["essential_350"]["remediation_limit"] == 3
    assert PLAN_CATALOG["advanced_550"]["remediation_limit"] == 6
    assert PLAN_CATALOG["architect_850"]["remediation_limit"] == 10


def test_report_visibility_is_exactly_free_preview_or_paid_top_3_6_10(monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_ACCESS_DB_PATH", str(tmp_path / "visibility.sqlite3"))
    monkeypatch.setenv("SCAN_ACCESS_SECRET", "unit-test-secret")
    import importlib
    import main as main_module
    from scan_access import AccessTicket

    main_module = importlib.reload(main_module)
    leaks = [
        {
            "rule_key": f"r{i}",
            "leak_name": f"Leak {i}",
            "impact_summary": "impact",
            "solutions_3_angles": {"technical": "secret patch"},
            "final_score_loss": float(10 - i),
        }
        for i in range(10)
    ]
    base = {
        "top_10_financial_leaks": leaks,
        "top_5_seo_leaks": leaks[:5],
        "full_50_checkpoint_basis": [{"id": i} for i in range(50)],
        "scoring_ledger": [{"id": 1}],
        "overlap_adjustments": [{"id": 1}],
        "score_formula": {"x": 1},
    }

    free = main_module._apply_report_access(
        base,
        AccessTicket(mode="free", usage_id=1, subject_hash=None, domain_key="example.com"),
    )
    assert len(free["top_10_financial_leaks"]) == 3
    assert "solutions_3_angles" not in free["top_10_financial_leaks"][0]
    assert "full_50_checkpoint_basis" not in free

    for plan_id, expected in (("essential_350", 3), ("advanced_550", 6), ("architect_850", 10)):
        paid = main_module._apply_report_access(
            base,
            AccessTicket(
                mode="paid",
                usage_id=1,
                subject_hash="hash",
                domain_key="example.com",
                plan_id=plan_id,
                remediation_limit=expected,
            ),
        )
        assert len(paid["top_10_financial_leaks"]) == expected
        assert len(paid["full_50_checkpoint_basis"]) == 50
        assert paid["top_10_financial_leaks"][0]["solutions_3_angles"]["technical"] == "secret patch"
        assert paid["report_access"]["remediation_findings_unlocked"] == expected


def test_admin_api_key_protects_and_controls_entitlement(monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_ACCESS_DB_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.setenv("SCAN_ACCESS_SECRET", "unit-test-secret")
    monkeypatch.setenv("TRILLOKA_ADMIN_API_KEY", "owner-secret-key")
    import importlib
    import main as main_module
    from fastapi.testclient import TestClient

    main_module = importlib.reload(main_module)
    client = TestClient(main_module.app)
    body = {
        "email": "api-buyer@example.com",
        "domain": "api.example",
        "plan_id": "essential_350",
        "purchase_ref": "ORDER-API",
    }
    denied = client.post("/api/admin/activate-plan", json=body)
    assert denied.status_code == 403

    headers = {"X-Trilloka-Admin-Key": "owner-secret-key"}
    created = client.post("/api/admin/activate-plan", json=body, headers=headers)
    assert created.status_code == 200
    payload = created.json()
    assert payload["plan"]["plan_id"] == "essential_350"
    assert len(payload["access_pass"]) >= 20

    upgraded = client.post(
        "/api/admin/entitlement/update",
        json={"email": body["email"], "domain": body["domain"], "plan_id": "architect_850"},
        headers=headers,
    )
    assert upgraded.status_code == 200
    assert upgraded.json()["plan"]["plan_id"] == "architect_850"

    revoked = client.post(
        "/api/admin/entitlement/revoke",
        json={"email": body["email"], "domain": body["domain"]},
        headers=headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True
