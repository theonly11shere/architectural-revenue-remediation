"""Private owner one-time-password authentication for Trilloka V6.

Human admin access is locked to exactly one owner email address. The browser never
supplies or chooses that address. A six-digit code is emailed with Resend, expires
quickly, is single-use, and is tied to the browser challenge that requested it.
Successful verification creates a short-lived HttpOnly admin session.

No scanner/checkpoint/scorer/report logic lives here.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


LOCKED_OWNER_EMAIL = "onlyonearpit@gmail.com"


class AdminAuthError(RuntimeError):
    def __init__(self, message: str, *, reason: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.reason = reason
        self.retry_after = retry_after


@dataclass(frozen=True)
class AdminChallenge:
    token: str
    expires_at: int
    destination: str


@dataclass(frozen=True)
class AdminSession:
    token: str
    expires_at: int


class AdminAuthManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("SCAN_ACCESS_DB_PATH", "./trilloka_scan_access.sqlite3")

        # Intentionally locked. There is no request field or browser setting that can
        # redirect owner codes to another address.
        configured = os.environ.get("TRILLOKA_ADMIN_LOGIN_EMAIL", LOCKED_OWNER_EMAIL).strip().lower()
        if configured and configured != LOCKED_OWNER_EMAIL:
            raise RuntimeError(
                "TRILLOKA_ADMIN_LOGIN_EMAIL does not match the owner email locked into this build"
            )
        self.admin_email = LOCKED_OWNER_EMAIL

        self.resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
        self.from_email = os.environ.get(
            "ADMIN_OTP_FROM_EMAIL", os.environ.get("FROM_EMAIL", "alerts@trilloka.com")
        ).strip()
        self.otp_ttl_seconds = max(120, int(os.environ.get("ADMIN_OTP_TTL_SECONDS", "600")))
        self.session_ttl_seconds = max(120, int(os.environ.get("ADMIN_SESSION_TTL_SECONDS", "900")))
        self.request_cooldown_seconds = max(15, int(os.environ.get("ADMIN_OTP_REQUEST_COOLDOWN_SECONDS", "60")))
        self.max_requests_per_hour = max(1, int(os.environ.get("ADMIN_OTP_MAX_REQUESTS_PER_HOUR", "5")))
        self.max_global_requests_per_hour = max(
            self.max_requests_per_hour,
            int(os.environ.get("ADMIN_OTP_MAX_GLOBAL_REQUESTS_PER_HOUR", "10")),
        )
        self.max_attempts = max(3, int(os.environ.get("ADMIN_OTP_MAX_ATTEMPTS", "5")))
        self.bind_request_ip = self._env_bool("ADMIN_OTP_BIND_REQUEST_IP", True)

        self.cookie_name = os.environ.get("ADMIN_SESSION_COOKIE_NAME", "trilloka_admin_session").strip() or "trilloka_admin_session"
        self.challenge_cookie_name = os.environ.get(
            "ADMIN_CHALLENGE_COOKIE_NAME", "trilloka_admin_challenge"
        ).strip() or "trilloka_admin_challenge"
        self.cookie_secure = self._env_bool("ADMIN_COOKIE_SECURE", self._env_bool("SCAN_COOKIE_SECURE", True))

        self._lock = threading.RLock()
        self._secret = self._load_secret()
        self._init_db()

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _load_secret(self) -> bytes:
        configured = os.environ.get("ADMIN_AUTH_SECRET", "").strip() or os.environ.get("SCAN_ACCESS_SECRET", "").strip()
        if configured:
            return configured.encode("utf-8")
        # Development-only fallback. Production docs require a persistent random secret.
        return secrets.token_bytes(48)

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS admin_otp_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code_hash TEXT NOT NULL,
                    challenge_hash TEXT,
                    requested_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    consumed_at INTEGER,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    requester_hash TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_admin_otp_requested ON admin_otp_codes(requested_at);

                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    revoked_at INTEGER,
                    requester_hash TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_admin_sessions_expiry ON admin_sessions(expires_at);
                """
            )
            # Safe migration from the immediately previous OTP draft, if it was ever deployed.
            if "challenge_hash" not in self._columns(conn, "admin_otp_codes"):
                conn.execute("ALTER TABLE admin_otp_codes ADD COLUMN challenge_hash TEXT")

    def _hash(self, namespace: str, value: str, *, normalize: bool = False) -> str:
        data = (value or "").strip()
        if normalize:
            data = data.lower()
        return hmac.new(
            self._secret,
            f"{namespace}:{data}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def requester_hash(self, requester_ip: str) -> str:
        return self._hash("admin-ip", requester_ip or "unknown", normalize=True)

    @property
    def configured(self) -> bool:
        return bool(self.admin_email and self.resend_api_key and self.from_email)

    def masked_admin_email(self) -> str:
        local, domain = self.admin_email.split("@", 1)
        if len(local) <= 2:
            masked = local[:1] + "*"
        else:
            masked = local[:2] + "*" * max(2, len(local) - 3) + local[-1:]
        return f"{masked}@{domain}"

    def _prune(self, conn: sqlite3.Connection, now: int) -> None:
        conn.execute("DELETE FROM admin_otp_codes WHERE requested_at < ?", (now - 86400,))
        conn.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (now - 86400,))

    def _send_code_email(self, code: str) -> None:
        if not self.resend_api_key:
            raise AdminAuthError("Resend API key is not configured", reason="OTP_EMAIL_NOT_CONFIGURED")
        if not self.from_email:
            raise AdminAuthError("OTP sender email is not configured", reason="OTP_EMAIL_NOT_CONFIGURED")

        ttl_minutes = max(1, round(self.otp_ttl_seconds / 60))
        safe_email = html.escape(self.admin_email)
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:28px">
          <h2 style="margin:0 0 16px">Trilloka Owner Sign-in</h2>
          <p>A sign-in code was requested for the private Trilloka owner console.</p>
          <div style="font-size:34px;font-weight:700;letter-spacing:8px;margin:26px 0">{code}</div>
          <p>This code expires in {ttl_minutes} minutes and can be used once.</p>
          <p style="font-size:13px;color:#666">Sent only to {safe_email}. If you did not request it, ignore this email.</p>
        </div>
        """
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": self.from_email,
                "to": [self.admin_email],
                "subject": "Your Trilloka admin sign-in code",
                "html": body,
            },
            timeout=15,
        )
        if response.status_code not in (200, 201, 202):
            raise AdminAuthError("Unable to deliver admin sign-in code", reason="OTP_EMAIL_DELIVERY_FAILED")

    def request_code(self, requester_ip: str) -> AdminChallenge:
        now = int(time.time())
        requester = self.requester_hash(requester_ip)

        with self._lock, self._connect() as conn:
            self._prune(conn, now)
            latest = conn.execute(
                "SELECT requested_at FROM admin_otp_codes ORDER BY requested_at DESC LIMIT 1"
            ).fetchone()
            if latest:
                wait = self.request_cooldown_seconds - (now - int(latest["requested_at"]))
                if wait > 0:
                    raise AdminAuthError(
                        "Please wait before requesting another code",
                        reason="OTP_COOLDOWN",
                        retry_after=wait,
                    )

            hourly_for_requester = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM admin_otp_codes WHERE requester_hash=? AND requested_at>=?",
                    (requester, now - 3600),
                ).fetchone()["c"]
            )
            hourly_global = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM admin_otp_codes WHERE requested_at>=?",
                    (now - 3600,),
                ).fetchone()["c"]
            )
            if hourly_for_requester >= self.max_requests_per_hour or hourly_global >= self.max_global_requests_per_hour:
                raise AdminAuthError(
                    "Too many sign-in code requests. Try again later.",
                    reason="OTP_RATE_LIMIT",
                    retry_after=3600,
                )

        code = f"{secrets.randbelow(1_000_000):06d}"
        challenge_token = secrets.token_urlsafe(32)
        code_hash = self._hash("admin-otp", code)
        challenge_hash = self._hash("admin-challenge", challenge_token)

        # Delivery must succeed before the code becomes valid.
        self._send_code_email(code)

        with self._lock, self._connect() as conn:
            # Only the newest code can work.
            conn.execute("UPDATE admin_otp_codes SET consumed_at=? WHERE consumed_at IS NULL", (now,))
            conn.execute(
                """
                INSERT INTO admin_otp_codes(
                    code_hash,challenge_hash,requested_at,expires_at,requester_hash
                ) VALUES(?,?,?,?,?)
                """,
                (code_hash, challenge_hash, now, now + self.otp_ttl_seconds, requester),
            )

        return AdminChallenge(
            token=challenge_token,
            expires_at=now + self.otp_ttl_seconds,
            destination=self.masked_admin_email(),
        )

    def verify_code(
        self,
        code: str,
        challenge_token: Optional[str],
        requester_ip: str,
    ) -> AdminSession:
        candidate = (code or "").strip()
        challenge = (challenge_token or "").strip()
        if len(candidate) != 6 or not candidate.isdigit():
            raise AdminAuthError("Invalid sign-in code", reason="OTP_INVALID")
        if not challenge:
            raise AdminAuthError("Sign-in challenge missing. Request a new code.", reason="OTP_CHALLENGE_MISSING")

        now = int(time.time())
        requester = self.requester_hash(requester_ip)
        candidate_hash = self._hash("admin-otp", candidate)
        challenge_hash = self._hash("admin-challenge", challenge)

        with self._lock, self._connect() as conn:
            self._prune(conn, now)
            row = conn.execute(
                "SELECT * FROM admin_otp_codes WHERE consumed_at IS NULL ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                raise AdminAuthError("No active sign-in code. Request a new code.", reason="OTP_NOT_FOUND")
            if int(row["expires_at"]) <= now:
                conn.execute("UPDATE admin_otp_codes SET consumed_at=? WHERE id=?", (now, int(row["id"])))
                raise AdminAuthError("Sign-in code expired. Request a new code.", reason="OTP_EXPIRED")
            if not row["challenge_hash"] or not hmac.compare_digest(str(row["challenge_hash"]), challenge_hash):
                raise AdminAuthError("This code belongs to a different browser sign-in request.", reason="OTP_CHALLENGE_INVALID")
            if self.bind_request_ip and row["requester_hash"] and not hmac.compare_digest(str(row["requester_hash"]), requester):
                raise AdminAuthError("Sign-in request changed network. Request a new code.", reason="OTP_REQUESTER_CHANGED")

            attempts = int(row["attempts"] or 0)
            if attempts >= self.max_attempts:
                conn.execute("UPDATE admin_otp_codes SET consumed_at=? WHERE id=?", (now, int(row["id"])))
                raise AdminAuthError("Too many incorrect attempts. Request a new code.", reason="OTP_ATTEMPTS_EXCEEDED")
            if not hmac.compare_digest(str(row["code_hash"]), candidate_hash):
                attempts += 1
                conn.execute(
                    "UPDATE admin_otp_codes SET attempts=?, consumed_at=? WHERE id=?",
                    (attempts, now if attempts >= self.max_attempts else None, int(row["id"])),
                )
                raise AdminAuthError("Invalid sign-in code", reason="OTP_INVALID")

            conn.execute("UPDATE admin_otp_codes SET consumed_at=? WHERE id=?", (now, int(row["id"])))
            token = secrets.token_urlsafe(40)
            token_hash = self._hash("admin-session", token)
            expires_at = now + self.session_ttl_seconds
            conn.execute(
                "INSERT INTO admin_sessions(token_hash,created_at,expires_at,requester_hash) VALUES(?,?,?,?)",
                (token_hash, now, expires_at, requester),
            )
            return AdminSession(token=token, expires_at=expires_at)

    def validate_session(self, token: Optional[str]) -> bool:
        raw = (token or "").strip()
        if not raw:
            return False
        now = int(time.time())
        token_hash = self._hash("admin-session", raw)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT expires_at,revoked_at FROM admin_sessions WHERE token_hash=? LIMIT 1",
                (token_hash,),
            ).fetchone()
            return bool(row and row["revoked_at"] is None and int(row["expires_at"]) > now)

    def session_status(self, token: Optional[str]) -> Dict[str, Any]:
        raw = (token or "").strip()
        if not raw:
            return {"authenticated": False}
        now = int(time.time())
        token_hash = self._hash("admin-session", raw)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT created_at,expires_at,revoked_at FROM admin_sessions WHERE token_hash=? LIMIT 1",
                (token_hash,),
            ).fetchone()
            if not row or row["revoked_at"] is not None or int(row["expires_at"]) <= now:
                return {"authenticated": False}
            return {
                "authenticated": True,
                "expires_at": int(row["expires_at"]),
                "expires_in_seconds": max(0, int(row["expires_at"]) - now),
                "destination": self.masked_admin_email(),
            }

    def revoke_session(self, token: Optional[str]) -> None:
        raw = (token or "").strip()
        if not raw:
            return
        now = int(time.time())
        token_hash = self._hash("admin-session", raw)
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE admin_sessions SET revoked_at=? WHERE token_hash=?", (now, token_hash))

    def revoke_all_sessions(self) -> int:
        now = int(time.time())
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE admin_sessions SET revoked_at=? WHERE revoked_at IS NULL AND expires_at>?",
                (now, now),
            )
            return int(cur.rowcount or 0)
