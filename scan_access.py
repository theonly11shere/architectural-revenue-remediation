"""Trilloka V6 server-side free-scan and paid-plan access controls.

The scanner itself is unchanged. This module controls who may run a fresh scan and how much
customer-facing remediation is unlocked after a verified purchase.

Commercial rules
----------------
FREE PREVIEW
* 1 successful free scan per IP/device per rolling 24 hours.
* Recent domain results may be served from a protected cache to avoid needless API/Chromium cost.

ESSENTIAL_350
* CAD $350
* 30 days for the purchased domain
* 2 fresh successful scans per calendar day
* full 50-checkpoint evidence + detailed remediation for Top 3 findings

ADVANCED_550
* CAD $550
* 30 days for the purchased domain
* 3 fresh successful scans per calendar day
* full 50-checkpoint evidence + detailed remediation for Top 6 findings
* one 15-minute implementation guidance call

ARCHITECT_850
* CAD $850
* 30 days for the purchased domain
* 4 fresh successful scans per calendar day
* full 50-checkpoint evidence + detailed remediation for Top 10 findings
* two 15-minute implementation guidance calls
* email support with a 15-hour response target

Security
--------
* Paid access is bound to email + purchased domain + a random purchase access pass.
* Only an HMAC hash of the pass is stored in SQLite.
* Raw email addresses and raw client IPs are not stored in the access database.
* Failed paid scans do not consume that day's allowance.
* Parallel reservations count while running so daily quotas cannot be bypassed by double-clicks.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


PLAN_CATALOG: Dict[str, Dict[str, Any]] = {
    "essential_350": {
        "plan_id": "essential_350",
        "name": "Essential Revenue Audit",
        "price": 350,
        "currency": "CAD",
        "duration_days": 30,
        "scans_per_day": 2,
        "remediation_limit": 3,
        "checkpoint_access": "full_50",
        "guidance_calls": 0,
        "guidance_call_minutes": 15,
        "email_support_response_hours": None,
    },
    "advanced_550": {
        "plan_id": "advanced_550",
        "name": "Advanced Revenue Audit",
        "price": 550,
        "currency": "CAD",
        "duration_days": 30,
        "scans_per_day": 3,
        "remediation_limit": 6,
        "checkpoint_access": "full_50",
        "guidance_calls": 1,
        "guidance_call_minutes": 15,
        "email_support_response_hours": None,
    },
    "architect_850": {
        "plan_id": "architect_850",
        "name": "Architect Revenue Audit",
        "price": 850,
        "currency": "CAD",
        "duration_days": 30,
        "scans_per_day": 4,
        "remediation_limit": 10,
        "checkpoint_access": "full_50",
        "guidance_calls": 2,
        "guidance_call_minutes": 15,
        "email_support_response_hours": 15,
    },
}


class AccessDenied(RuntimeError):
    def __init__(self, message: str, *, reason: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.reason = reason
        self.retry_after = retry_after


@dataclass
class AccessTicket:
    mode: str
    usage_id: Optional[int]
    subject_hash: Optional[str]
    domain_key: str
    plan_id: Optional[str] = None
    scans_per_day: Optional[int] = None
    scans_remaining_today: Optional[int] = None
    remediation_limit: Optional[int] = None
    expires_at: Optional[int] = None
    reservation_consumes_quota: bool = True


class ScanAccessManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("SCAN_ACCESS_DB_PATH", "./trilloka_scan_access.sqlite3")
        self.enabled = self._env_bool("SCAN_ACCESS_CONTROL_ENABLED", True)
        self.free_limit = max(1, int(os.environ.get("FREE_SCAN_LIMIT", "1")))
        self.free_window_seconds = max(3600, int(float(os.environ.get("FREE_SCAN_WINDOW_HOURS", "24")) * 3600))
        self.free_cache_seconds = max(60, int(float(os.environ.get("FREE_SCAN_CACHE_HOURS", "24")) * 3600))
        self.paid_duplicate_grace_seconds = max(0, int(os.environ.get("PAID_DUPLICATE_GRACE_SECONDS", "180")))
        self.reservation_ttl_seconds = max(60, int(os.environ.get("SCAN_RESERVATION_TTL_SECONDS", "1200")))
        self.trust_proxy_headers = self._env_bool("TRUST_PROXY_HEADERS", False)
        tz_name = os.environ.get("PLAN_TIMEZONE", "America/Vancouver").strip() or "America/Vancouver"
        try:
            self.plan_timezone = ZoneInfo(tz_name)
        except Exception:
            self.plan_timezone = ZoneInfo("UTC")
            tz_name = "UTC"
        self.plan_timezone_name = tz_name
        self._lock = threading.RLock()
        self._init_db()
        self._secret = self._load_or_create_secret()

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS access_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                -- V6.3 paid entitlements are domain + plan specific. The older credit table, if
                -- present from V6.1, is intentionally left untouched for safe in-place deployment.
                CREATE TABLE IF NOT EXISTS plan_entitlements (
                    subject_hash TEXT NOT NULL,
                    domain_key TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    pass_hash TEXT NOT NULL,
                    purchase_ref TEXT,
                    activated_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    guidance_calls_used INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(subject_hash, domain_key)
                );
                CREATE INDEX IF NOT EXISTS idx_plan_entitlement_expiry ON plan_entitlements(expires_at);

                CREATE TABLE IF NOT EXISTS free_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_hash TEXT NOT NULL,
                    device_hash TEXT NOT NULL,
                    domain_key TEXT NOT NULL,
                    reserved_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_free_usage_ip_time ON free_usage(ip_hash, reserved_at);
                CREATE INDEX IF NOT EXISTS idx_free_usage_device_time ON free_usage(device_hash, reserved_at);

                CREATE TABLE IF NOT EXISTS paid_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_hash TEXT NOT NULL,
                    domain_key TEXT NOT NULL,
                    plan_id TEXT,
                    reserved_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_paid_usage_subject_time ON paid_usage(subject_hash, reserved_at);
                CREATE INDEX IF NOT EXISTS idx_paid_usage_subject_domain ON paid_usage(subject_hash, domain_key, reserved_at);

                CREATE TABLE IF NOT EXISTS scan_cache (
                    domain_key TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    response_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS access_metrics (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            # Safe in-place migrations from V6.1/V6.3 databases.
            cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(paid_usage)").fetchall()}
            if "plan_id" not in cols:
                conn.execute("ALTER TABLE paid_usage ADD COLUMN plan_id TEXT")

            entitlement_cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(plan_entitlements)").fetchall()}
            if "status" not in entitlement_cols:
                conn.execute("ALTER TABLE plan_entitlements ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
            if "guidance_calls_used" not in entitlement_cols:
                conn.execute("ALTER TABLE plan_entitlements ADD COLUMN guidance_calls_used INTEGER NOT NULL DEFAULT 0")

    def _load_or_create_secret(self) -> bytes:
        configured = os.environ.get("SCAN_ACCESS_SECRET", "").strip()
        if configured:
            return configured.encode("utf-8")
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT value FROM access_meta WHERE key='generated_secret'").fetchone()
            if row:
                return str(row["value"]).encode("utf-8")
            secret = secrets.token_urlsafe(48)
            conn.execute("INSERT OR REPLACE INTO access_meta(key,value) VALUES('generated_secret',?)", (secret,))
            return secret.encode("utf-8")

    def _hash(self, namespace: str, value: str) -> str:
        normalized = (value or "").strip().lower()
        return hmac.new(self._secret, f"{namespace}:{normalized}".encode("utf-8"), hashlib.sha256).hexdigest()

    def _pass_hash(self, access_pass: str) -> str:
        # Passes are case-sensitive; do not use _hash()'s lower-casing behavior.
        return hmac.new(self._secret, f"pass:{access_pass}".encode("utf-8"), hashlib.sha256).hexdigest()

    def email_subject(self, email: Optional[str]) -> Optional[str]:
        return self._hash("email", str(email)) if email else None

    def ip_subject(self, ip: str) -> str:
        return self._hash("ip", ip or "unknown")

    def device_subject(self, device_id: str) -> str:
        return self._hash("device", device_id or "unknown")

    @staticmethod
    def normalize_domain(target: str) -> str:
        raw = (target or "").strip()
        if not raw:
            return ""
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or raw).lower().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        return host

    def client_ip(self, request: Any) -> str:
        if self.trust_proxy_headers:
            for name in ("cf-connecting-ip", "x-real-ip"):
                value = str(request.headers.get(name) or "").strip()
                if value:
                    return value
            forwarded = str(request.headers.get("x-forwarded-for") or "").strip()
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
        client = getattr(request, "client", None)
        return str(getattr(client, "host", "") or "unknown")

    @staticmethod
    def ensure_device_id(existing: Optional[str]) -> Tuple[str, bool]:
        clean = (existing or "").strip()
        if clean and 12 <= len(clean) <= 128 and all(c.isalnum() or c in "-_" for c in clean):
            return clean, False
        return secrets.token_urlsafe(24), True

    def public_plans(self) -> Dict[str, Dict[str, Any]]:
        return {key: dict(value) for key, value in PLAN_CATALOG.items()}

    def _metric(self, conn: sqlite3.Connection, key: str, amount: int = 1) -> None:
        conn.execute(
            """INSERT INTO access_metrics(key,value) VALUES(?,?)
               ON CONFLICT(key) DO UPDATE SET value=value+excluded.value""",
            (key, int(amount)),
        )

    def _day_bounds(self, now: Optional[int] = None) -> Tuple[int, int]:
        ts = int(now or time.time())
        local = _dt.datetime.fromtimestamp(ts, tz=self.plan_timezone)
        start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + _dt.timedelta(days=1)
        return int(start_local.timestamp()), int(end_local.timestamp())

    def _recover_stale(self, conn: sqlite3.Connection, now: int) -> None:
        cutoff = now - self.reservation_ttl_seconds
        stale = conn.execute(
            "SELECT id FROM paid_usage WHERE status='reserved' AND reserved_at<?", (cutoff,)
        ).fetchall()
        for row in stale:
            changed = conn.execute(
                "UPDATE paid_usage SET status='failed', completed_at=? WHERE id=? AND status='reserved'",
                (now, int(row["id"])),
            ).rowcount
            if changed:
                self._metric(conn, "paid_stale_released")
        conn.execute(
            "UPDATE free_usage SET status='failed', completed_at=? WHERE status='reserved' AND reserved_at<?",
            (now, cutoff),
        )

    def activate_plan(
        self,
        *,
        email: str,
        domain: str,
        plan_id: str,
        purchase_ref: str = "",
        access_pass: Optional[str] = None,
        duration_days_override: Optional[int] = None,
        complimentary: bool = False,
    ) -> Dict[str, Any]:
        """Activate or replace a customer/domain entitlement after verified payment or owner grant.

        The plaintext access pass is returned once. Only its HMAC hash is stored.
        ``duration_days_override`` is an owner-only convenience for complimentary/custom grants.
        """
        subject = self.email_subject(email)
        domain_key = self.normalize_domain(domain)
        plan = PLAN_CATALOG.get(str(plan_id or "").strip().lower())
        if not subject:
            raise ValueError("A valid customer email is required")
        if not domain_key:
            raise ValueError("A valid purchased domain is required")
        if not plan:
            raise ValueError(f"Unknown plan_id. Expected one of: {', '.join(PLAN_CATALOG)}")

        issued_pass = (access_pass or secrets.token_urlsafe(32)).strip()
        if len(issued_pass) < 20:
            raise ValueError("access_pass must be at least 20 characters when supplied")
        duration_days = int(duration_days_override or plan["duration_days"])
        if duration_days < 1 or duration_days > 3650:
            raise ValueError("duration_days_override must be between 1 and 3650")
        pass_hash = self._pass_hash(issued_pass)
        now = int(time.time())
        expires_at = now + duration_days * 86400
        purchase_label = purchase_ref or ("COMPLIMENTARY" if complimentary else "")
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """INSERT INTO plan_entitlements(
                           subject_hash,domain_key,plan_id,pass_hash,purchase_ref,activated_at,expires_at,updated_at,status,guidance_calls_used
                       ) VALUES(?,?,?,?,?,?,?,?, 'active', 0)
                       ON CONFLICT(subject_hash,domain_key) DO UPDATE SET
                           plan_id=excluded.plan_id,
                           pass_hash=excluded.pass_hash,
                           purchase_ref=excluded.purchase_ref,
                           activated_at=excluded.activated_at,
                           expires_at=excluded.expires_at,
                           updated_at=excluded.updated_at,
                           status='active',
                           guidance_calls_used=0""",
                    (subject, domain_key, plan["plan_id"], pass_hash, purchase_label or None, now, expires_at, now),
                )
                self._metric(conn, f"plan_activated_{plan['plan_id']}")
                if complimentary:
                    self._metric(conn, "plan_activated_complimentary")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return {
            "plan": dict(plan),
            "domain": domain_key,
            "activated_at": now,
            "expires_at": expires_at,
            "duration_days": duration_days,
            "access_pass": issued_pass,
            "purchase_ref": purchase_label,
            "complimentary": bool(complimentary),
            "status": "active",
        }

    # Backward-compatible name for the V6.1/V6.3 admin endpoint.
    def grant_package(
        self,
        email: str,
        domain: str,
        plan_id: str = "essential_350",
        purchase_ref: str = "",
    ) -> Dict[str, Any]:
        return self.activate_plan(email=email, domain=domain, plan_id=plan_id, purchase_ref=purchase_ref)

    def _entitlement_row(self, subject: str, domain_key: str) -> Optional[sqlite3.Row]:
        with self._lock, self._connect() as conn:
            return conn.execute(
                """SELECT subject_hash,domain_key,plan_id,pass_hash,purchase_ref,activated_at,expires_at,updated_at,
                          status,guidance_calls_used
                   FROM plan_entitlements WHERE subject_hash=? AND domain_key=?""",
                (subject, domain_key),
            ).fetchone()

    def entitlement_status(
        self,
        email: Optional[str],
        domain_key: Optional[str] = None,
        access_pass: Optional[str] = None,
        *,
        require_pass: bool = False,
    ) -> Dict[str, Any]:
        subject = self.email_subject(email)
        domain = self.normalize_domain(domain_key or "")
        if not subject or not domain:
            return {"exists": False, "active": False}
        row = self._entitlement_row(subject, domain)
        if not row:
            return {"exists": False, "active": False}
        plan = PLAN_CATALOG.get(str(row["plan_id"]))
        now = int(time.time())
        expired = int(row["expires_at"]) <= now
        revoked = str(row["status"] or "active").lower() == "revoked"
        pass_valid = False
        if access_pass:
            pass_valid = hmac.compare_digest(self._pass_hash(str(access_pass)), str(row["pass_hash"]))
        if require_pass and not pass_valid:
            return {
                "exists": True,
                "active": False if revoked or expired else bool(plan),
                "pass_valid": False,
                "expired": expired,
                "revoked": revoked,
                "status": "revoked" if revoked else ("expired" if expired else "active"),
                "plan": dict(plan or {}),
                "domain": domain,
                "expires_at": int(row["expires_at"]),
            }
        day_start, day_end = self._day_bounds(now)
        with self._lock, self._connect() as conn:
            used_row = conn.execute(
                """SELECT COUNT(*) AS n FROM paid_usage
                   WHERE subject_hash=? AND domain_key=? AND status IN ('reserved','success')
                     AND reserved_at>=? AND reserved_at<?""",
                (subject, domain, day_start, day_end),
            ).fetchone()
        used_today = int(used_row["n"] if used_row else 0)
        limit = int((plan or {}).get("scans_per_day") or 0)
        calls_total = int((plan or {}).get("guidance_calls") or 0)
        calls_used = max(0, int(row["guidance_calls_used"] or 0))
        return {
            "exists": True,
            "active": bool(plan and not expired and not revoked),
            "expired": expired,
            "revoked": revoked,
            "status": "revoked" if revoked else ("expired" if expired else "active"),
            "pass_valid": pass_valid,
            "domain": domain,
            "plan": dict(plan or {}),
            "purchase_ref": str(row["purchase_ref"] or ""),
            "activated_at": int(row["activated_at"]),
            "updated_at": int(row["updated_at"]),
            "expires_at": int(row["expires_at"]),
            "scans_used_today": used_today,
            "scans_remaining_today": max(0, limit - used_today),
            "day_resets_at": day_end,
            "timezone": self.plan_timezone_name,
            "guidance_calls_total": calls_total,
            "guidance_calls_used": calls_used,
            "guidance_calls_remaining": max(0, calls_total - calls_used),
        }

    def _require_paid_status(self, email: Optional[str], domain_key: str, access_pass: Optional[str]) -> Optional[Dict[str, Any]]:
        subject = self.email_subject(email)
        if not subject:
            return None
        row = self._entitlement_row(subject, domain_key)
        if not row:
            return None
        status = self.entitlement_status(email, domain_key, access_pass, require_pass=True)
        if not status.get("pass_valid"):
            raise AccessDenied(
                "A valid purchase access pass is required for this paid domain. Use the pass issued after payment.",
                reason="PAID_PASS_REQUIRED",
            )
        if status.get("revoked"):
            raise AccessDenied(
                "This audit plan has been paused or revoked by Trilloka administration.",
                reason="PAID_PLAN_REVOKED",
            )
        if status.get("expired"):
            raise AccessDenied(
                "This audit plan has expired. Purchase a new plan or contact Trilloka to continue paid rescans and remediation access.",
                reason="PAID_PLAN_EXPIRED",
            )
        return status

    # -------------------------
    # Owner/admin plan controls
    # -------------------------
    def update_entitlement(
        self,
        *,
        email: str,
        domain: str,
        plan_id: Optional[str] = None,
        extend_days: Optional[int] = None,
        expires_at: Optional[int] = None,
        purchase_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upgrade/downgrade a plan and/or change its expiry without rotating the customer pass."""
        subject = self.email_subject(email)
        domain_key = self.normalize_domain(domain)
        if not subject or not domain_key:
            raise ValueError("Valid email and domain are required")
        row = self._entitlement_row(subject, domain_key)
        if not row:
            raise ValueError("No entitlement exists for this customer/domain")
        new_plan = str(plan_id or row["plan_id"]).strip().lower()
        if new_plan not in PLAN_CATALOG:
            raise ValueError(f"Unknown plan_id. Expected one of: {', '.join(PLAN_CATALOG)}")
        if extend_days is not None and expires_at is not None:
            raise ValueError("Use either extend_days or expires_at, not both")
        new_expiry = int(row["expires_at"])
        if extend_days is not None:
            new_expiry += int(extend_days) * 86400
        elif expires_at is not None:
            new_expiry = int(expires_at)
        if new_expiry < 1:
            raise ValueError("expires_at must be a positive Unix timestamp")
        new_purchase_ref = str(row["purchase_ref"] or "") if purchase_ref is None else str(purchase_ref or "")
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE plan_entitlements SET plan_id=?,expires_at=?,purchase_ref=?,updated_at=?
                   WHERE subject_hash=? AND domain_key=?""",
                (new_plan, new_expiry, new_purchase_ref or None, now, subject, domain_key),
            )
            self._metric(conn, "admin_entitlement_updated")
            if new_plan != str(row["plan_id"]):
                self._metric(conn, f"admin_plan_changed_to_{new_plan}")
        return self.entitlement_status(email, domain_key)

    def revoke_entitlement(self, *, email: str, domain: str) -> Dict[str, Any]:
        return self._set_entitlement_status(email=email, domain=domain, status="revoked")

    def restore_entitlement(self, *, email: str, domain: str) -> Dict[str, Any]:
        return self._set_entitlement_status(email=email, domain=domain, status="active")

    def _set_entitlement_status(self, *, email: str, domain: str, status: str) -> Dict[str, Any]:
        subject = self.email_subject(email)
        domain_key = self.normalize_domain(domain)
        if status not in {"active", "revoked"}:
            raise ValueError("status must be active or revoked")
        if not subject or not domain_key:
            raise ValueError("Valid email and domain are required")
        now = int(time.time())
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE plan_entitlements SET status=?,updated_at=? WHERE subject_hash=? AND domain_key=?",
                (status, now, subject, domain_key),
            ).rowcount
            if not changed:
                raise ValueError("No entitlement exists for this customer/domain")
            self._metric(conn, f"admin_entitlement_{status}")
        return self.entitlement_status(email, domain_key)

    def rotate_access_pass(self, *, email: str, domain: str) -> Dict[str, Any]:
        subject = self.email_subject(email)
        domain_key = self.normalize_domain(domain)
        if not subject or not domain_key or not self._entitlement_row(subject, domain_key):
            raise ValueError("No entitlement exists for this customer/domain")
        new_pass = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE plan_entitlements SET pass_hash=?,updated_at=? WHERE subject_hash=? AND domain_key=?",
                (self._pass_hash(new_pass), now, subject, domain_key),
            )
            self._metric(conn, "admin_pass_rotated")
        return {"domain": domain_key, "access_pass": new_pass, "rotated_at": now}

    def change_entitlement_domain(self, *, email: str, domain: str, new_domain: str) -> Dict[str, Any]:
        subject = self.email_subject(email)
        old_domain = self.normalize_domain(domain)
        new_key = self.normalize_domain(new_domain)
        if not subject or not old_domain or not new_key:
            raise ValueError("Valid email, current domain and new domain are required")
        if old_domain == new_key:
            return self.entitlement_status(email, old_domain)
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                src = conn.execute(
                    "SELECT 1 FROM plan_entitlements WHERE subject_hash=? AND domain_key=?", (subject, old_domain)
                ).fetchone()
                if not src:
                    raise ValueError("No entitlement exists for the current customer/domain")
                dst = conn.execute(
                    "SELECT 1 FROM plan_entitlements WHERE subject_hash=? AND domain_key=?", (subject, new_key)
                ).fetchone()
                if dst:
                    raise ValueError("An entitlement already exists for the new domain")
                conn.execute(
                    "UPDATE plan_entitlements SET domain_key=?,updated_at=? WHERE subject_hash=? AND domain_key=?",
                    (new_key, now, subject, old_domain),
                )
                # Preserve daily usage/history when correcting or moving the purchased domain.
                conn.execute(
                    "UPDATE paid_usage SET domain_key=? WHERE subject_hash=? AND domain_key=?",
                    (new_key, subject, old_domain),
                )
                self._metric(conn, "admin_domain_changed")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return self.entitlement_status(email, new_key)

    def reset_daily_usage(self, *, email: str, domain: str) -> Dict[str, Any]:
        subject = self.email_subject(email)
        domain_key = self.normalize_domain(domain)
        if not subject or not domain_key or not self._entitlement_row(subject, domain_key):
            raise ValueError("No entitlement exists for this customer/domain")
        now = int(time.time())
        day_start, day_end = self._day_bounds(now)
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                """UPDATE paid_usage SET status='admin_reset',completed_at=?
                   WHERE subject_hash=? AND domain_key=? AND reserved_at>=? AND reserved_at<?
                     AND status IN ('reserved','success')""",
                (now, subject, domain_key, day_start, day_end),
            ).rowcount
            self._metric(conn, "admin_daily_usage_reset")
        result = self.entitlement_status(email, domain_key)
        result["usage_rows_reset"] = int(changed)
        return result

    def record_guidance_call(self, *, email: str, domain: str, delta: int = 1) -> Dict[str, Any]:
        subject = self.email_subject(email)
        domain_key = self.normalize_domain(domain)
        row = self._entitlement_row(subject or "", domain_key) if subject and domain_key else None
        if not row:
            raise ValueError("No entitlement exists for this customer/domain")
        plan = PLAN_CATALOG.get(str(row["plan_id"])) or {}
        total = int(plan.get("guidance_calls") or 0)
        current = max(0, int(row["guidance_calls_used"] or 0))
        new_value = max(0, current + int(delta))
        if new_value > total:
            raise ValueError(f"This plan includes {total} guidance call(s); cannot record {new_value}")
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE plan_entitlements SET guidance_calls_used=?,updated_at=? WHERE subject_hash=? AND domain_key=?",
                (new_value, now, subject, domain_key),
            )
            self._metric(conn, "admin_guidance_call_adjusted")
        return self.entitlement_status(email, domain_key)

    def list_entitlements(self, *, active_only: bool = False, limit: int = 100) -> Dict[str, Any]:
        """Admin-safe listing. Raw customer emails are intentionally not stored or returned."""
        now = int(time.time())
        limit = max(1, min(500, int(limit)))
        where = "WHERE status='active' AND expires_at>?" if active_only else ""
        params = (now, limit) if active_only else (limit,)
        sql = f"""SELECT subject_hash,domain_key,plan_id,purchase_ref,activated_at,expires_at,updated_at,status,guidance_calls_used
                  FROM plan_entitlements {where} ORDER BY updated_at DESC LIMIT ?"""
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        items = []
        for row in rows:
            plan = PLAN_CATALOG.get(str(row["plan_id"])) or {}
            items.append({
                "subject_ref": str(row["subject_hash"])[:12],
                "domain": str(row["domain_key"]),
                "plan": dict(plan),
                "purchase_ref": str(row["purchase_ref"] or ""),
                "activated_at": int(row["activated_at"]),
                "expires_at": int(row["expires_at"]),
                "updated_at": int(row["updated_at"]),
                "status": str(row["status"] or "active"),
                "expired": int(row["expires_at"]) <= now,
                "guidance_calls_used": int(row["guidance_calls_used"] or 0),
            })
        return {"count": len(items), "entitlements": items}

    def recent_paid_duplicate(
        self,
        email: Optional[str],
        domain_key: str,
        access_pass: Optional[str] = None,
        *,
        force_refresh: bool = False,
    ) -> bool:
        if force_refresh or self.paid_duplicate_grace_seconds <= 0:
            return False
        status = self._require_paid_status(email, domain_key, access_pass)
        if not status:
            return False
        subject = self.email_subject(email)
        cutoff = int(time.time()) - self.paid_duplicate_grace_seconds
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT 1 FROM paid_usage
                   WHERE subject_hash=? AND domain_key=? AND status='success' AND completed_at>=?
                   ORDER BY completed_at DESC LIMIT 1""",
                (subject, domain_key, cutoff),
            ).fetchone()
        return bool(row)

    def reserve(
        self,
        *,
        ip: str,
        device_id: str,
        email: Optional[str],
        domain_key: str,
        access_pass: Optional[str] = None,
        admin_bypass: bool = False,
    ) -> AccessTicket:
        if not self.enabled or admin_bypass:
            return AccessTicket(
                mode="admin" if admin_bypass else "unmetered",
                usage_id=None,
                subject_hash=None,
                domain_key=domain_key,
                remediation_limit=10,
                reservation_consumes_quota=False,
            )

        now = int(time.time())
        subject = self.email_subject(email)
        ip_hash = self.ip_subject(ip)
        device_hash = self.device_subject(device_id)

        # If a plan exists for this exact customer/domain, require the purchase pass before doing
        # anything else. This prevents email-only impersonation from consuming a paid allowance.
        paid_status = self._require_paid_status(email, domain_key, access_pass) if subject else None

        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._recover_stale(conn, now)
                if paid_status:
                    plan = paid_status["plan"]
                    day_start, day_end = self._day_bounds(now)
                    used = conn.execute(
                        """SELECT COUNT(*) AS n FROM paid_usage
                           WHERE subject_hash=? AND domain_key=? AND status IN ('reserved','success')
                             AND reserved_at>=? AND reserved_at<?""",
                        (subject, domain_key, day_start, day_end),
                    ).fetchone()
                    used_count = int(used["n"] if used else 0)
                    daily_limit = int(plan["scans_per_day"])
                    if used_count >= daily_limit:
                        retry = max(60, day_end - now)
                        conn.execute("ROLLBACK")
                        raise AccessDenied(
                            f"Daily paid scan allowance reached for {plan['name']}. This plan allows {daily_limit} fresh scans per day for the purchased domain.",
                            reason="PAID_DAILY_LIMIT",
                            retry_after=retry,
                        )
                    cur = conn.execute(
                        """INSERT INTO paid_usage(subject_hash,domain_key,plan_id,reserved_at,status)
                           VALUES(?,?,?,?, 'reserved')""",
                        (subject, domain_key, plan["plan_id"], now),
                    )
                    self._metric(conn, f"paid_reserved_{plan['plan_id']}")
                    conn.execute("COMMIT")
                    return AccessTicket(
                        mode="paid",
                        usage_id=int(cur.lastrowid),
                        subject_hash=subject,
                        domain_key=domain_key,
                        plan_id=str(plan["plan_id"]),
                        scans_per_day=daily_limit,
                        scans_remaining_today=max(0, daily_limit - used_count - 1),
                        remediation_limit=int(plan["remediation_limit"]),
                        expires_at=int(paid_status["expires_at"]),
                    )

                cutoff = now - self.free_window_seconds
                used = conn.execute(
                    """SELECT COUNT(*) AS n FROM free_usage
                       WHERE reserved_at>=? AND status IN ('reserved','success')
                         AND (ip_hash=? OR device_hash=?)""",
                    (cutoff, ip_hash, device_hash),
                ).fetchone()
                used_count = int(used["n"] if used else 0)
                if used_count >= self.free_limit:
                    first = conn.execute(
                        """SELECT MIN(reserved_at) AS first_at FROM free_usage
                           WHERE reserved_at>=? AND status IN ('reserved','success')
                             AND (ip_hash=? OR device_hash=?)""",
                        (cutoff, ip_hash, device_hash),
                    ).fetchone()
                    first_at = int(first["first_at"] or now) if first else now
                    retry = max(60, self.free_window_seconds - (now - first_at))
                    conn.execute("ROLLBACK")
                    raise AccessDenied(
                        "Free scan limit reached. One free preview scan is available per 24 hours per IP/device. Paid audit plans unlock domain-specific daily rescans for 30 days.",
                        reason="FREE_DAILY_LIMIT",
                        retry_after=retry,
                    )
                cur = conn.execute(
                    """INSERT INTO free_usage(ip_hash,device_hash,domain_key,reserved_at,status)
                       VALUES(?,?,?,?, 'reserved')""",
                    (ip_hash, device_hash, domain_key, now),
                )
                self._metric(conn, "free_reserved")
                conn.execute("COMMIT")
                return AccessTicket(
                    mode="free",
                    usage_id=int(cur.lastrowid),
                    subject_hash=subject,
                    domain_key=domain_key,
                    remediation_limit=0,
                )
            except AccessDenied:
                raise
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    def finish(self, ticket: AccessTicket, *, success: bool) -> None:
        if ticket.usage_id is None or not ticket.reservation_consumes_quota:
            return
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if ticket.mode == "paid":
                    changed = conn.execute(
                        "UPDATE paid_usage SET status=?,completed_at=? WHERE id=? AND status='reserved'",
                        ("success" if success else "failed", now, ticket.usage_id),
                    ).rowcount
                    if changed:
                        self._metric(conn, "paid_success" if success else "paid_failed_released")
                elif ticket.mode == "free":
                    changed = conn.execute(
                        "UPDATE free_usage SET status=?,completed_at=? WHERE id=? AND status='reserved'",
                        ("success" if success else "failed", now, ticket.usage_id),
                    ).rowcount
                    if changed:
                        self._metric(conn, "free_success" if success else "free_failed")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def cache_get(self, domain_key: str, max_age_seconds: int) -> Optional[Tuple[Dict[str, Any], int]]:
        if not domain_key or max_age_seconds <= 0:
            return None
        now = int(time.time())
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT created_at,response_json FROM scan_cache WHERE domain_key=?", (domain_key,)).fetchone()
        if not row:
            return None
        age = max(0, now - int(row["created_at"]))
        if age > max_age_seconds:
            return None
        try:
            payload = json.loads(str(row["response_json"]))
        except Exception:
            return None
        return (payload, age) if isinstance(payload, dict) else None

    def cache_put(self, domain_key: str, response_payload: Dict[str, Any]) -> None:
        if not domain_key:
            return
        serializable = json.dumps(response_payload, separators=(",", ":"), ensure_ascii=False, default=str)
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO scan_cache(domain_key,created_at,response_json) VALUES(?,?,?)
                   ON CONFLICT(domain_key) DO UPDATE SET created_at=excluded.created_at,response_json=excluded.response_json""",
                (domain_key, now, serializable),
            )
            self._metric(conn, "cache_writes")

    def note_cache_hit(self, mode: str) -> None:
        with self._lock, self._connect() as conn:
            self._metric(conn, f"cache_hit_{mode}")

    def access_summary(
        self,
        ticket: AccessTicket,
        *,
        cached: bool,
        cache_age_seconds: Optional[int] = None,
        email: Optional[str] = None,
        access_pass: Optional[str] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "mode": ticket.mode,
            "cached": bool(cached),
            "cache_age_seconds": int(cache_age_seconds or 0) if cached else None,
            "free_limit": self.free_limit,
            "free_window_hours": round(self.free_window_seconds / 3600, 2),
            "timezone": self.plan_timezone_name,
        }
        if ticket.mode == "paid" and ticket.plan_id:
            status = self.entitlement_status(email, ticket.domain_key, access_pass)
            plan = status.get("plan") or PLAN_CATALOG.get(ticket.plan_id, {})
            result.update(
                {
                    "plan": dict(plan),
                    "entitlement_status": status.get("status"),
                    "expires_at": ticket.expires_at,
                    "scans_per_day": int(plan.get("scans_per_day") or ticket.scans_per_day or 0),
                    "scans_used_today": status.get("scans_used_today"),
                    "scans_remaining_today": status.get("scans_remaining_today", ticket.scans_remaining_today),
                    "day_resets_at": status.get("day_resets_at"),
                    "remediation_limit": int(plan.get("remediation_limit") or ticket.remediation_limit or 0),
                    "guidance_calls_total": status.get("guidance_calls_total"),
                    "guidance_calls_used": status.get("guidance_calls_used"),
                    "guidance_calls_remaining": status.get("guidance_calls_remaining"),
                }
            )
        else:
            result["plan"] = {
                "plan_id": "free_preview",
                "name": "Free Preview",
                "price": 0,
                "currency": "CAD",
                "remediation_limit": 0,
                "checkpoint_access": "summary_only",
            }
        return result

    def admin_metrics(self) -> Dict[str, Any]:
        now = int(time.time())
        day_start, day_end = self._day_bounds(now)
        with self._lock, self._connect() as conn:
            metrics = {str(r["key"]): int(r["value"]) for r in conn.execute("SELECT key,value FROM access_metrics").fetchall()}
            active = conn.execute(
                "SELECT plan_id,COUNT(*) AS n FROM plan_entitlements WHERE expires_at>? AND status='active' GROUP BY plan_id", (now,)
            ).fetchall()
            paid_today = conn.execute(
                "SELECT plan_id,COUNT(*) AS n FROM paid_usage WHERE status='success' AND reserved_at>=? AND reserved_at<? GROUP BY plan_id",
                (day_start, day_end),
            ).fetchall()
            cached = conn.execute("SELECT COUNT(*) AS n FROM scan_cache WHERE created_at>=?", (now - self.free_cache_seconds,)).fetchone()
        return {
            "enabled": self.enabled,
            "metrics": metrics,
            "active_plans": {str(r["plan_id"]): int(r["n"]) for r in active},
            "successful_paid_scans_today": {str(r["plan_id"]): int(r["n"]) for r in paid_today},
            "fresh_cache_entries": int(cached["n"] if cached else 0),
            "free_limit": self.free_limit,
            "free_window_hours": round(self.free_window_seconds / 3600, 2),
            "free_cache_hours": round(self.free_cache_seconds / 3600, 2),
            "plan_timezone": self.plan_timezone_name,
            "plans": self.public_plans(),
        }
