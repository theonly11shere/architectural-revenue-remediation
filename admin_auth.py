"""Owner-only OTP authentication for the Trilloka administration endpoints.

This module is deliberately small and self-contained:
- the owner address is fixed by environment configuration; clients never submit an email;
- OTP challenge and admin-session tokens are HMAC signed;
- raw OTPs are never stored or logged;
- OTP delivery uses the same Resend account already used by the report engine;
- request cooldown/rate limits and bounded verification attempts reduce brute-force abuse;
- browser cookies remain HttpOnly/Secure/Strict through ``main.py``.

Required production configuration:
    ADMIN_EMAIL or TRILLOKA_ADMIN_EMAIL
    RESEND_API_KEY
Optional:
    TRILLOKA_ADMIN_SESSION_SECRET  (recommended; otherwise a stable key is derived
                                    from the Resend key and owner email)
    FROM_EMAIL / TRILLOKA_ADMIN_FROM_EMAIL
    TRILLOKA_ADMIN_OTP_TTL_SECONDS       default 600
    TRILLOKA_ADMIN_SESSION_TTL_SECONDS   default 1800
    TRILLOKA_ADMIN_OTP_COOLDOWN_SECONDS  default 60
    TRILLOKA_ADMIN_OTP_MAX_PER_HOUR      default 5
    TRILLOKA_ADMIN_OTP_MAX_ATTEMPTS      default 5
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(os.environ.get(name, str(default)))))
    except Exception:
        return default


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    value = str(value or "")
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


class AdminAuthError(RuntimeError):
    def __init__(self, message: str, reason: str = "ADMIN_AUTH_FAILED", retry_after: Optional[int] = None):
        super().__init__(message)
        self.reason = reason
        self.retry_after = retry_after


@dataclass(frozen=True)
class AdminChallenge:
    token: str
    destination: str
    expires_at: int


@dataclass(frozen=True)
class AdminSession:
    token: str
    expires_at: int


class AdminAuthManager:
    cookie_name = "trilloka_admin_session"
    challenge_cookie_name = "trilloka_admin_challenge"

    def __init__(self) -> None:
        self.owner_email = (os.environ.get("TRILLOKA_ADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL") or "").strip().lower()
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
        self.from_email = (os.environ.get("TRILLOKA_ADMIN_FROM_EMAIL") or os.environ.get("FROM_EMAIL") or "alerts@trilloka.com").strip()
        explicit_secret = os.environ.get("TRILLOKA_ADMIN_SESSION_SECRET", "").strip()
        if explicit_secret:
            secret_material = explicit_secret.encode("utf-8")
        elif self.resend_api_key and self.owner_email:
            # Stable fallback so existing deployments do not require a new variable immediately.
            # A dedicated TRILLOKA_ADMIN_SESSION_SECRET remains the preferred production setup.
            secret_material = hashlib.sha256(
                ("trilloka-admin-v1|" + self.owner_email + "|" + self.resend_api_key).encode("utf-8")
            ).digest()
        else:
            secret_material = b""
        self._secret = hashlib.sha256(secret_material).digest() if secret_material else b""

        self.otp_ttl_seconds = _env_int("TRILLOKA_ADMIN_OTP_TTL_SECONDS", 600, 120, 1800)
        self.session_ttl_seconds = _env_int("TRILLOKA_ADMIN_SESSION_TTL_SECONDS", 1800, 300, 43200)
        self.otp_cooldown_seconds = _env_int("TRILLOKA_ADMIN_OTP_COOLDOWN_SECONDS", 60, 15, 600)
        self.otp_max_per_hour = _env_int("TRILLOKA_ADMIN_OTP_MAX_PER_HOUR", 5, 2, 20)
        self.otp_max_attempts = _env_int("TRILLOKA_ADMIN_OTP_MAX_ATTEMPTS", 5, 3, 10)
        self.cookie_secure = os.environ.get("TRILLOKA_ADMIN_COOKIE_SECURE", "true").strip().lower() in {"1", "true", "yes", "on"}

        self._lock = threading.RLock()
        self._request_times: Dict[str, list[float]] = {}
        self._attempts: Dict[str, int] = {}
        self._used_challenges: Dict[str, int] = {}
        self._revoked_sessions: Dict[str, int] = {}

    @property
    def configured(self) -> bool:
        return bool(self.owner_email and self.resend_api_key and self._secret)

    def _sign(self, payload: bytes) -> str:
        return _b64e(hmac.new(self._secret, payload, hashlib.sha256).digest())

    def _encode_token(self, data: Dict[str, Any]) -> str:
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return _b64e(payload) + "." + self._sign(payload)

    def _decode_token(self, token: Optional[str], expected_type: str) -> Dict[str, Any]:
        if not token or not self._secret:
            raise AdminAuthError("Authentication token is missing or invalid", "ADMIN_AUTH_INVALID")
        try:
            payload_part, sig = str(token).split(".", 1)
            payload = _b64d(payload_part)
            if not hmac.compare_digest(sig, self._sign(payload)):
                raise ValueError("signature")
            data = json.loads(payload.decode("utf-8"))
            if not isinstance(data, dict) or data.get("typ") != expected_type:
                raise ValueError("type")
            if int(data.get("exp") or 0) <= int(time.time()):
                raise AdminAuthError("Authentication token has expired", "ADMIN_AUTH_EXPIRED")
            return data
        except AdminAuthError:
            raise
        except Exception as exc:
            raise AdminAuthError("Authentication token is invalid", "ADMIN_AUTH_INVALID") from exc

    @staticmethod
    def _client_fingerprint(client_ip: str) -> str:
        return hashlib.sha256(str(client_ip or "unknown").strip().encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _masked_email(email: str) -> str:
        local, _, domain = str(email or "").partition("@")
        if not domain:
            return "configured owner email"
        if len(local) <= 2:
            visible = local[:1] + "*"
        else:
            visible = local[:2] + ("*" * min(6, len(local) - 2))
        return f"{visible}@{domain}"

    def _cleanup(self, now: int) -> None:
        self._used_challenges = {k: exp for k, exp in self._used_challenges.items() if exp > now}
        self._revoked_sessions = {k: exp for k, exp in self._revoked_sessions.items() if exp > now}
        cutoff = now - 3600
        for key in list(self._request_times):
            vals = [t for t in self._request_times[key] if t > cutoff]
            if vals:
                self._request_times[key] = vals
            else:
                self._request_times.pop(key, None)

    def request_code(self, client_ip: str) -> AdminChallenge:
        if not self.owner_email:
            raise AdminAuthError("Owner email is not configured", "ADMIN_EMAIL_NOT_CONFIGURED")
        if not self.resend_api_key or not self._secret:
            raise AdminAuthError("Owner OTP email authentication is not configured", "OTP_EMAIL_NOT_CONFIGURED")

        now = int(time.time())
        fingerprint = self._client_fingerprint(client_ip)
        with self._lock:
            self._cleanup(now)
            history = self._request_times.setdefault(fingerprint, [])
            if history and (now - history[-1]) < self.otp_cooldown_seconds:
                retry = self.otp_cooldown_seconds - (now - int(history[-1]))
                raise AdminAuthError("Please wait before requesting another owner code", "OTP_COOLDOWN", max(1, retry))
            if len(history) >= self.otp_max_per_hour:
                retry = max(60, 3600 - (now - int(history[0])))
                raise AdminAuthError("Owner code request limit reached", "OTP_RATE_LIMIT", retry)

        code = f"{secrets.randbelow(1_000_000):06d}"
        nonce = secrets.token_urlsafe(18)
        exp = now + self.otp_ttl_seconds
        code_hash = hmac.new(self._secret, f"otp|{nonce}|{code}".encode("utf-8"), hashlib.sha256).hexdigest()
        token = self._encode_token({"typ": "otp", "iat": now, "exp": exp, "nonce": nonce, "ip": fingerprint, "code": code_hash})

        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.resend_api_key}", "Content-Type": "application/json"},
                json={
                    "from": self.from_email,
                    "to": self.owner_email,
                    "subject": "Your Trilloka owner sign-in code",
                    "html": (
                        "<div style='font-family:Arial,sans-serif;max-width:560px'>"
                        "<h2>Trilloka owner sign-in</h2>"
                        f"<p>Your one-time code is <strong style='font-size:26px;letter-spacing:4px'>{code}</strong></p>"
                        f"<p>This code expires in {max(1, round(self.otp_ttl_seconds/60))} minutes. If you did not request it, ignore this email.</p>"
                        "</div>"
                    ),
                },
                timeout=12,
            )
            if response.status_code not in {200, 201, 202}:
                raise RuntimeError(f"Resend HTTP {response.status_code}")
        except Exception as exc:
            raise AdminAuthError("Owner sign-in code could not be delivered", "OTP_EMAIL_DELIVERY_FAILED") from exc

        with self._lock:
            self._request_times.setdefault(fingerprint, []).append(float(now))
            self._attempts[nonce] = 0
        return AdminChallenge(token=token, destination=self._masked_email(self.owner_email), expires_at=exp)

    def verify_code(self, code: str, challenge_token: Optional[str], client_ip: str) -> AdminSession:
        data = self._decode_token(challenge_token, "otp")
        now = int(time.time())
        nonce = str(data.get("nonce") or "")
        fingerprint = self._client_fingerprint(client_ip)
        if not hmac.compare_digest(str(data.get("ip") or ""), fingerprint):
            raise AdminAuthError("Owner code must be verified from the requesting client", "ADMIN_AUTH_INVALID")
        clean_code = "".join(ch for ch in str(code or "") if ch.isdigit())
        if len(clean_code) != 6:
            raise AdminAuthError("Enter the 6-digit owner code", "OTP_INVALID")

        with self._lock:
            self._cleanup(now)
            if nonce in self._used_challenges:
                raise AdminAuthError("This owner code has already been used", "OTP_INVALID")
            attempts = int(self._attempts.get(nonce, 0))
            if attempts >= self.otp_max_attempts:
                raise AdminAuthError("Too many invalid code attempts; request a new code", "OTP_RATE_LIMIT", self.otp_cooldown_seconds)

        expected = str(data.get("code") or "")
        supplied = hmac.new(self._secret, f"otp|{nonce}|{clean_code}".encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            with self._lock:
                self._attempts[nonce] = int(self._attempts.get(nonce, 0)) + 1
            raise AdminAuthError("Owner code is incorrect", "OTP_INVALID")

        session_nonce = secrets.token_urlsafe(24)
        exp = now + self.session_ttl_seconds
        token = self._encode_token({"typ": "session", "iat": now, "exp": exp, "nonce": session_nonce})
        with self._lock:
            self._used_challenges[nonce] = int(data.get("exp") or now)
            self._attempts.pop(nonce, None)
        return AdminSession(token=token, expires_at=exp)

    def validate_session(self, token: Optional[str]) -> bool:
        try:
            data = self._decode_token(token, "session")
            token_id = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
            with self._lock:
                self._cleanup(int(time.time()))
                return token_id not in self._revoked_sessions
        except AdminAuthError:
            return False

    def session_status(self, token: Optional[str]) -> Dict[str, Any]:
        try:
            data = self._decode_token(token, "session")
            token_id = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
            now = int(time.time())
            with self._lock:
                self._cleanup(now)
                if token_id in self._revoked_sessions:
                    return {"success": True, "authenticated": False, "configured": self.configured, "expires_in_seconds": 0}
            exp = int(data.get("exp") or 0)
            return {"success": True, "authenticated": True, "configured": self.configured, "expires_at": exp, "expires_in_seconds": max(0, exp - now)}
        except AdminAuthError:
            return {"success": True, "authenticated": False, "configured": self.configured, "expires_in_seconds": 0}

    def revoke_session(self, token: Optional[str]) -> None:
        if not token:
            return
        try:
            data = self._decode_token(token, "session")
            exp = int(data.get("exp") or int(time.time()))
        except AdminAuthError:
            return
        token_id = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
        with self._lock:
            self._revoked_sessions[token_id] = exp
