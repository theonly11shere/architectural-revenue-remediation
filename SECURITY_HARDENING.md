# Trilloka V7.2.1 — Network / SSRF Hardening

This build treats every user-supplied, page-derived, redirect-derived and
competitor-derived destination as untrusted.

## Server-side HTTP protections

`network_security.py` validates and resolves every untrusted HTTP(S) target before
connection. It rejects:

- localhost and internal hostname suffixes
- IPv4/IPv6 loopback
- RFC1918/private addresses
- link-local and cloud metadata addresses
- carrier-grade NAT, multicast, reserved and unspecified addresses
- mixed public/private DNS answers
- non-HTTP(S) schemes
- embedded username/password credentials
- disallowed ports (80/443 by default)
- ambiguous whitespace/control/backslash URL forms

The safe HTTP client does not merely validate DNS and then let the networking
library resolve the hostname again. It connects to the exact public IP address
that passed validation while retaining the original Host header and TLS
SNI/certificate hostname. This prevents DNS rebinding between validation and the
actual server-side socket connection.

Redirects are followed manually and every redirect destination is independently
DNS-validated and re-pinned before a new connection is made.

Remote HTML responses are bounded to prevent untrusted pages from creating
unbounded scanner memory use.

## Browser / Playwright protections

- The main target is resolved before Chromium launch.
- A validated public IPv4 address is pinned with Chromium host-resolver rules.
- Private/non-public HTTP(S) requests are aborted.
- Cross-origin browser traffic fails closed except for provider-controlled
  trusted DNS suffixes used by common real-world websites and supported booking
  providers.
- WebSocket destinations are independently validated.
- Service workers are disabled for scanning.
- WebRTC and WebTransport are disabled because they are unnecessary for passive
  evidence collection and create alternate network paths.
- Chromium is launched with no proxy server.
- New cross-host top-level navigation is blocked after the safe HTTP preflight has
  already resolved normal server redirects.

If the browser security policy blocks third-party resources, negative dynamic
observations are downgraded to PARTIAL/UNKNOWN rather than becoming false revenue
leaks. Positive evidence remains usable. UNKNOWN still earns no readiness points.

## Configuration

`TRILLOKA_ALLOWED_TARGET_PORTS`
  Optional comma-separated override. Defaults to `80,443`. A malformed/empty
  override fails closed to the default.

`TRILLOKA_BROWSER_TRUSTED_HOSTS`
  Optional comma-separated additional browser DNS suffixes. Only add provider
  domains you explicitly trust. The default list covers common major web/CDN,
  analytics, commerce and booking infrastructure.

## Security scope

These controls address the scanner's outbound-target/SSRF attack surface. They do
not replace normal production controls such as dependency updates, secret
management, HTTPS, platform firewalls, access logging, rate limiting, backups and
a periodic external penetration test.
