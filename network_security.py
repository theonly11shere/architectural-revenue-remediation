"""Outbound network target validation for the Trilloka scanner.

The scanner accepts public website targets, so every user- or page-derived network
request must be treated as untrusted.  This module provides two related controls:

1. Strict URL/DNS validation: only public HTTP(S) destinations on normal web ports.
2. A pinned HTTP client: requests connect to the exact public IP address that was
   validated, while preserving the original Host header and TLS SNI/certificate
   verification.  Redirects are validated and re-pinned hop by hop.

This prevents classic SSRF, redirects to internal services, DNS rebinding between
validation and the socket connection for server-side HTTP probes, cloud metadata
access, localhost/private/link-local access, embedded-credential URLs, and non-web
schemes.
"""
from __future__ import annotations

import ipaddress
import json as _json
import os
import re
import socket
import ssl
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import urllib3


_REDIRECT_CODES = {301, 302, 303, 307, 308}
_DEFAULT_ALLOWED_PORTS = {80, 443}
_FORBIDDEN_HOST_SUFFIXES = (
    "localhost",
    "local",
    "localdomain",
    "internal",
    "intranet",
    "lan",
    "home",
    "corp",
    "private",
    "onion",
)
_CONTROL_OR_SPACE_RE = re.compile(r"[\x00-\x20\x7f]")


# Browser rendering is stricter than the server-side HTTP client because Chromium cannot
# dynamically pin every attacker-chosen third-party hostname.  Cross-origin requests are
# therefore limited to provider-controlled DNS suffixes commonly required by real websites.
# Tenant content on these platforms can still redirect, but every redirect is independently
# routed through the private-address guard.
_DEFAULT_BROWSER_TRUSTED_SUFFIXES = (
    "google.com", "gstatic.com", "googleapis.com", "googletagmanager.com",
    "google-analytics.com", "doubleclick.net", "recaptcha.net",
    "cloudflare.com", "cdnjs.cloudflare.com", "pages.dev", "workers.dev",
    "jsdelivr.net", "unpkg.com", "bootstrapcdn.com", "jquery.com",
    "cloudfront.net", "amazonaws.com", "azureedge.net", "akamaized.net", "akamaihd.net", "fastly.net",
    "wp.com", "wordpress.com", "wordpress.org",
    "shopify.com", "shopifycdn.com", "wix.com", "wixstatic.com", "squarespace.com", "squarespace-cdn.com",
    "stripe.com", "stripe.network", "paypal.com", "paypalobjects.com",
    "fontawesome.com", "typekit.net", "adobe.com",
    "cookielaw.org", "onetrust.com", "trustpilot.com", "trustpilot.net", "yotpo.com", "reviews.io",
    "hubspot.com", "hs-scripts.com", "hsforms.net", "intercom.io", "intercomcdn.com",
    "zendesk.com", "zopim.com", "hotjar.com", "clarity.ms",
    "facebook.com", "facebook.net", "instagram.com", "tiktok.com", "linkedin.com",
    "youtube.com", "ytimg.com", "vimeo.com", "vimeocdn.com",
)


class NetworkTargetError(ValueError):
    """Raised when an outbound scanner destination is not a safe public web target."""

    def __init__(self, message: str, reason: str = "UNSAFE_NETWORK_TARGET") -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class ResolvedPublicTarget:
    url: str
    scheme: str
    host: str
    port: int
    ips: Tuple[str, ...]

    @property
    def preferred_ipv4(self) -> Optional[str]:
        for value in self.ips:
            try:
                if ipaddress.ip_address(value).version == 4:
                    return value
            except ValueError:
                continue
        return None


@dataclass
class SafeHTTPResponse:
    status_code: int
    url: str
    headers: Dict[str, str]
    body: bytes = b""
    history: List["SafeHTTPResponse"] = field(default_factory=list)

    @property
    def text(self) -> str:
        content_type = str(self.headers.get("Content-Type") or self.headers.get("content-type") or "")
        charset = "utf-8"
        match = re.search(r"charset\s*=\s*['\"]?([^;\s'\"]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip()
        try:
            return self.body.decode(charset, errors="replace")
        except (LookupError, UnicodeError):
            return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return _json.loads(self.text)



def _allowed_ports() -> set[int]:
    raw = os.environ.get("TRILLOKA_ALLOWED_TARGET_PORTS", "").strip()
    if not raw:
        return set(_DEFAULT_ALLOWED_PORTS)
    ports: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError:
            continue
        if 1 <= value <= 65535:
            ports.add(value)
    # Security fail-closed: a malformed/empty override never means "all ports".
    return ports or set(_DEFAULT_ALLOWED_PORTS)


def _normalize_host(raw_host: str) -> str:
    host = str(raw_host or "").strip().rstrip(".").lower()
    if not host:
        raise NetworkTargetError("A hostname is required", "MISSING_HOST")
    if "%" in host:
        # Blocks IPv6 zone identifiers and percent-encoded host ambiguity.
        raise NetworkTargetError("Percent-encoded or zone-qualified hosts are not allowed", "AMBIGUOUS_HOST")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise NetworkTargetError("The hostname is not valid IDNA", "INVALID_HOST") from exc
    if len(host) > 253:
        raise NetworkTargetError("The hostname is too long", "INVALID_HOST")
    return host


def _host_is_explicitly_internal(host: str) -> bool:
    value = str(host or "").lower().rstrip(".")
    return any(value == suffix or value.endswith("." + suffix) for suffix in _FORBIDDEN_HOST_SUFFIXES)


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # Python's is_global can still be True for multicast space, so explicitly reject
    # every non-unicast/non-public category before accepting global reachability.
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        return False
    return bool(ip.is_global)


def _resolve_host(host: str, port: int) -> Tuple[str, ...]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            infos = socket.getaddrinfo(
                host,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        except socket.gaierror as exc:
            raise NetworkTargetError("The target hostname could not be resolved", "DNS_RESOLUTION_FAILED") from exc
        addresses = []
        for info in infos:
            try:
                address = str(info[4][0]).split("%", 1)[0]
            except Exception:
                continue
            if address and address not in addresses:
                addresses.append(address)
    if not addresses:
        raise NetworkTargetError("The target hostname did not resolve to an address", "DNS_RESOLUTION_FAILED")
    unsafe = [address for address in addresses if not _is_public_ip(address)]
    if unsafe:
        raise NetworkTargetError(
            "The target resolves to a private, loopback, link-local, reserved, or otherwise non-public address",
            "NON_PUBLIC_ADDRESS",
        )
    return tuple(addresses)


def validate_public_http_url(
    target: str,
    *,
    add_default_scheme: bool = True,
    resolve_dns: bool = True,
) -> ResolvedPublicTarget:
    """Normalize and validate a public HTTP(S) scanner target.

    The returned IP list is the exact set approved for a subsequent pinned connection.
    """
    raw = str(target or "").strip()
    if not raw:
        raise NetworkTargetError("Target domain is required", "MISSING_TARGET")
    if len(raw) > 4096:
        raise NetworkTargetError("The target URL is too long", "INVALID_URL")
    if _CONTROL_OR_SPACE_RE.search(raw) or "\\" in raw:
        raise NetworkTargetError("Whitespace, control characters, and backslashes are not allowed in target URLs", "AMBIGUOUS_URL")
    if raw.startswith("//"):
        raise NetworkTargetError("Scheme-relative URLs are not accepted as scanner targets", "INVALID_SCHEME")
    if "://" not in raw:
        if not add_default_scheme:
            raise NetworkTargetError("An explicit http:// or https:// scheme is required", "INVALID_SCHEME")
        raw = "https://" + raw

    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception as exc:
        raise NetworkTargetError("The target URL could not be parsed", "INVALID_URL") from exc

    scheme = str(parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise NetworkTargetError("Only http:// and https:// targets are allowed", "INVALID_SCHEME")
    if parsed.username is not None or parsed.password is not None:
        raise NetworkTargetError("URLs containing embedded credentials are not allowed", "EMBEDDED_CREDENTIALS")

    host = _normalize_host(parsed.hostname or "")
    if _host_is_explicitly_internal(host):
        raise NetworkTargetError("Local or internal hostnames are not allowed", "INTERNAL_HOSTNAME")

    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise NetworkTargetError("The target contains an invalid port", "INVALID_PORT") from exc
    port = int(explicit_port or (443 if scheme == "https" else 80))
    if port not in _allowed_ports():
        raise NetworkTargetError("Only approved public web ports are allowed", "DISALLOWED_PORT")

    ips: Tuple[str, ...] = _resolve_host(host, port) if resolve_dns else tuple()

    # Rebuild the authority without credentials and with an ASCII/IDNA hostname.
    display_host = f"[{host}]" if ":" in host else host
    default_port = 443 if scheme == "https" else 80
    netloc = display_host if port == default_port else f"{display_host}:{port}"
    path = parsed.path or "/"
    normalized = urllib.parse.urlunsplit((scheme, netloc, path, parsed.query, ""))
    return ResolvedPublicTarget(normalized, scheme, host, port, ips)


def validate_public_websocket_url(target: str, *, resolve_dns: bool = True) -> ResolvedPublicTarget:
    raw = str(target or "").strip()
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception as exc:
        raise NetworkTargetError("Invalid WebSocket URL", "INVALID_URL") from exc
    scheme = str(parsed.scheme or "").lower()
    if scheme not in {"ws", "wss"}:
        raise NetworkTargetError("Only ws:// and wss:// WebSocket targets are allowed", "INVALID_SCHEME")
    mapped_scheme = "https" if scheme == "wss" else "http"
    mapped = urllib.parse.urlunsplit((mapped_scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))
    return validate_public_http_url(mapped, add_default_scheme=False, resolve_dns=resolve_dns)



def _hostname_matches_suffix(host: str, suffix: str) -> bool:
    host = str(host or "").lower().rstrip(".")
    suffix = str(suffix or "").lower().strip().rstrip(".")
    return bool(host and suffix and (host == suffix or host.endswith("." + suffix)))


def browser_cross_origin_host_allowed(
    host: str,
    primary_host: str,
    *,
    extra_trusted_hosts: Optional[Iterable[str]] = None,
) -> bool:
    """Return True only for the pinned primary host or provider-controlled DNS suffixes."""
    normalized = _normalize_host(host)
    primary = _normalize_host(primary_host)
    if normalized == primary:
        return True
    trusted: List[str] = list(_DEFAULT_BROWSER_TRUSTED_SUFFIXES)
    env_extra = os.environ.get("TRILLOKA_BROWSER_TRUSTED_HOSTS", "")
    trusted.extend(item.strip() for item in env_extra.split(",") if item.strip())
    trusted.extend(str(item).strip() for item in (extra_trusted_hosts or ()) if str(item).strip())
    return any(_hostname_matches_suffix(normalized, suffix) for suffix in trusted)

def browser_non_network_scheme_allowed(url: str) -> bool:
    try:
        scheme = urllib.parse.urlsplit(str(url or "")).scheme.lower()
    except Exception:
        return False
    return scheme in {"about", "data", "blob"}


class SafeHTTPClient:
    """Pinned, redirect-aware GET client for untrusted scanner destinations."""

    def __init__(self, *, default_headers: Optional[Mapping[str, str]] = None, max_redirects: int = 6) -> None:
        self.default_headers = {
            "User-Agent": "TrillokaBot/3.2 Secure Revenue Architecture Auditor",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close",
        }
        if default_headers:
            self.default_headers.update({str(k): str(v) for k, v in default_headers.items()})
        self.max_redirects = max(0, min(10, int(max_redirects)))
        self._ssl_context = ssl.create_default_context()

    @staticmethod
    def normalize_target(target: str) -> str:
        return validate_public_http_url(target).url

    def get(
        self,
        url: str,
        *,
        timeout: Any = (5, 12),
        headers: Optional[Mapping[str, str]] = None,
        allow_redirects: bool = True,
        max_bytes: int = 2_000_000,
    ) -> SafeHTTPResponse:
        current = str(url or "")
        history: List[SafeHTTPResponse] = []
        redirect_limit = self.max_redirects if allow_redirects else 0

        for hop in range(redirect_limit + 1):
            resolved = validate_public_http_url(current, add_default_scheme=True, resolve_dns=True)
            response = self._request_once(resolved, timeout=timeout, headers=headers, max_bytes=max_bytes)
            if not allow_redirects or response.status_code not in _REDIRECT_CODES:
                response.history = history
                return response
            location = str(response.headers.get("Location") or response.headers.get("location") or "").strip()
            if not location:
                response.history = history
                return response
            if hop >= redirect_limit:
                raise NetworkTargetError("The target exceeded the safe redirect limit", "TOO_MANY_REDIRECTS")
            next_url = urllib.parse.urljoin(resolved.url, location)
            # Critical: validate the redirect before any connection is made to it.
            validate_public_http_url(next_url, add_default_scheme=False, resolve_dns=True)
            history.append(response)
            current = next_url

        raise NetworkTargetError("The target exceeded the safe redirect limit", "TOO_MANY_REDIRECTS")

    @staticmethod
    def _timeout(timeout: Any) -> urllib3.Timeout:
        if isinstance(timeout, (tuple, list)) and len(timeout) >= 2:
            connect, read = timeout[0], timeout[1]
        else:
            connect = read = timeout
        try:
            connect_f = float(connect)
        except Exception:
            connect_f = 5.0
        try:
            read_f = float(read)
        except Exception:
            read_f = 12.0
        return urllib3.Timeout(connect=max(0.5, connect_f), read=max(0.5, read_f))

    @staticmethod
    def _host_header(target: ResolvedPublicTarget) -> str:
        host = f"[{target.host}]" if ":" in target.host else target.host
        default_port = 443 if target.scheme == "https" else 80
        return host if target.port == default_port else f"{host}:{target.port}"

    @staticmethod
    def _request_target(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        query = urllib.parse.quote(parsed.query or "", safe="=&?/:;+,%@!$'()*-._~")
        return path + (("?" + query) if query else "")

    def _request_once(
        self,
        target: ResolvedPublicTarget,
        *,
        timeout: Any,
        headers: Optional[Mapping[str, str]],
        max_bytes: int,
    ) -> SafeHTTPResponse:
        request_headers = dict(self.default_headers)
        if headers:
            request_headers.update({str(k): str(v) for k, v in headers.items()})
        # Never let a caller override authority with a second Host value.
        request_headers["Host"] = self._host_header(target)
        request_target = self._request_target(target.url)
        maximum = max(1024, min(int(max_bytes or 0), 5_000_000))
        last_error: Optional[BaseException] = None

        for ip in target.ips:
            pool: Any = None
            response: Any = None
            try:
                if target.scheme == "https":
                    pool = urllib3.HTTPSConnectionPool(
                        host=ip,
                        port=target.port,
                        timeout=self._timeout(timeout),
                        retries=False,
                        maxsize=1,
                        block=True,
                        assert_hostname=target.host,
                        server_hostname=target.host,
                        ssl_context=self._ssl_context,
                    )
                else:
                    pool = urllib3.HTTPConnectionPool(
                        host=ip,
                        port=target.port,
                        timeout=self._timeout(timeout),
                        retries=False,
                        maxsize=1,
                        block=True,
                    )
                response = pool.request(
                    "GET",
                    request_target,
                    headers=request_headers,
                    redirect=False,
                    preload_content=False,
                    decode_content=False,
                )
                body = response.read(maximum + 1, decode_content=True)
                if len(body) > maximum:
                    raise NetworkTargetError("The remote response exceeded the scanner safety limit", "RESPONSE_TOO_LARGE")
                response_headers = {str(k): str(v) for k, v in response.headers.items()}
                return SafeHTTPResponse(
                    status_code=int(response.status),
                    url=target.url,
                    headers=response_headers,
                    body=bytes(body),
                )
            except NetworkTargetError:
                raise
            except Exception as exc:
                last_error = exc
                continue
            finally:
                try:
                    if response is not None:
                        response.release_conn()
                except Exception:
                    pass
                try:
                    if pool is not None:
                        pool.close()
                except Exception:
                    pass

        if last_error is not None:
            raise last_error
        raise NetworkTargetError("No approved public address was available for the target", "DNS_RESOLUTION_FAILED")
