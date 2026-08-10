from __future__ import annotations

import sqlite3

import pytest

from admin_auth import AdminAuthError, AdminAuthManager, LOCKED_OWNER_EMAIL


def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAN_ACCESS_DB_PATH", str(tmp_path / "otp.sqlite3"))
    monkeypatch.setenv("SCAN_ACCESS_SECRET", "test-scan-secret")
    monkeypatch.setenv("ADMIN_AUTH_SECRET", "test-admin-secret")
    monkeypatch.setenv("RESEND_API_KEY", "test-resend")
    monkeypatch.setenv("ADMIN_COOKIE_SECURE", "false")
    monkeypatch.setenv("ADMIN_OTP_REQUEST_COOLDOWN_SECONDS", "15")
    monkeypatch.setenv("ADMIN_OTP_BIND_REQUEST_IP", "true")
    return AdminAuthManager(str(tmp_path / "otp.sqlite3"))


def test_owner_email_is_locked_and_not_chosen_by_browser(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    assert m.admin_email == LOCKED_OWNER_EMAIL == "onlyonearpit@gmail.com"
    assert "@gmail.com" in m.masked_admin_email()


def test_build_refuses_redirecting_owner_code_to_other_email(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAN_ACCESS_DB_PATH", str(tmp_path / "wrong.sqlite3"))
    monkeypatch.setenv("SCAN_ACCESS_SECRET", "test-scan-secret")
    monkeypatch.setenv("ADMIN_AUTH_SECRET", "test-admin-secret")
    monkeypatch.setenv("TRILLOKA_ADMIN_LOGIN_EMAIL", "attacker@example.com")
    with pytest.raises(RuntimeError):
        AdminAuthManager(str(tmp_path / "wrong.sqlite3"))


def test_otp_is_single_use_and_browser_challenge_bound(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    sent = {}
    m._send_code_email = lambda code: sent.setdefault("code", code)
    challenge = m.request_code("203.0.113.9")

    with pytest.raises(AdminAuthError) as wrong_browser:
        m.verify_code(sent["code"], "different-browser-token", "203.0.113.9")
    assert wrong_browser.value.reason == "OTP_CHALLENGE_INVALID"

    session = m.verify_code(sent["code"], challenge.token, "203.0.113.9")
    assert m.validate_session(session.token) is True

    with pytest.raises(AdminAuthError) as reused:
        m.verify_code(sent["code"], challenge.token, "203.0.113.9")
    assert reused.value.reason == "OTP_NOT_FOUND"


def test_otp_request_is_bound_to_requesting_network_by_default(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    sent = {}
    m._send_code_email = lambda code: sent.setdefault("code", code)
    challenge = m.request_code("203.0.113.10")
    with pytest.raises(AdminAuthError) as changed:
        m.verify_code(sent["code"], challenge.token, "198.51.100.20")
    assert changed.value.reason == "OTP_REQUESTER_CHANGED"


def test_database_never_stores_plain_otp_or_owner_email(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    sent = {}
    m._send_code_email = lambda code: sent.setdefault("code", code)
    m.request_code("203.0.113.11")
    raw = (tmp_path / "otp.sqlite3").read_bytes()
    assert sent["code"].encode() not in raw
    assert LOCKED_OWNER_EMAIL.encode() not in raw


def test_admin_session_can_be_revoked(tmp_path, monkeypatch):
    m = manager(tmp_path, monkeypatch)
    sent = {}
    m._send_code_email = lambda code: sent.setdefault("code", code)
    challenge = m.request_code("203.0.113.12")
    session = m.verify_code(sent["code"], challenge.token, "203.0.113.12")
    assert m.validate_session(session.token)
    m.revoke_session(session.token)
    assert not m.validate_session(session.token)
