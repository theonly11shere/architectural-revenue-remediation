"""Trilloka production scanning engine.

V7.1 Journey + Context architecture:
- Infers the observable customer journey instead of expanding an industry/subtype taxonomy.
- Adds independent context tags for regulated/high-trust, local, commerce, sensitive-data,
  enterprise/considered-purchase and hospitality/event requirements.
- Keeps universal low-weight foundation evidence separate from adaptive revenue architecture.
- Browser-renders one priority journey page in addition to the homepage and keeps the bounded
  same-origin evidence pass.
- Uses strict Google Place target identity and relevance-gated local competitor benchmarking.
- Preserves evidence receipts, safe external-provider checks, rescan comparison hooks and
  proof-backed severe-finding confirmation with CONFIRMED/CORROBORATED/unscored states.

Evidence guardrails:
- Positive evidence from a reliable source cannot be erased by a weaker negative pass.
- Customer-visible conversion errors are visible-text-first; dormant source strings do not count.
- Unknown telemetry remains UNKNOWN and causes no score deduction.
- Forms, bookings, purchases and customer data are never submitted or mutated.

Backward compatibility:
- Keeps legacy request/response keys used by the existing gateway/frontend.
- Legacy business-type values are weak journey hints only and cannot override stronger evidence.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import hashlib
import json
import math
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from playwright.async_api import async_playwright

from network_security import (
    NetworkTargetError, SafeHTTPClient, browser_cross_origin_host_allowed, browser_non_network_scheme_allowed,
    validate_public_http_url, validate_public_websocket_url,
)

from architecture_model import (
    JOURNEY_PAGE_TERMS, JOURNEY_PAGE_GUESSES,
    competitor_search_text as architecture_competitor_search_text,
    expected_actions as architecture_expected_actions,
    infer_architecture_profile, context_has,
)


PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4}(?!\d)")
H1_SOURCE_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1\s*>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

BOT_CHALLENGE_PATTERNS = (
    "checking your browser",
    "verify you are human",
    "attention required",
    "access denied",
    "cf-chl-",
    "cloudflare ray id",
    "unusual traffic",
    "too many requests",
)

SOCIAL_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
)


# High-confidence error strings that can be passively observed on public conversion pages.
# These are deliberately narrow: generic words like "error" do not create a failure.
CONVERSION_ERROR_PATTERNS = (
    ("recaptcha_invalid_site_key", r"google\s+recaptcha\s*:\s*invalid\s+site\s+key|recaptcha[^\n]{0,60}invalid\s+site\s+key|invalid\s+site\s+key[^\n]{0,40}recaptcha", "Google reCAPTCHA is exposing an invalid site-key error."),
    ("recaptcha_site_owner_error", r"error\s+for\s+site\s+owner[^\n]{0,120}(?:site\s+key|recaptcha|domain|key\s+type)", "The page exposes a reCAPTCHA site-owner configuration error."),
    ("recaptcha_load_failure", r"recaptcha[^\n]{0,80}(?:failed\s+to\s+load|verification\s+failed|could\s+not\s+load|unavailable)", "The page exposes a reCAPTCHA loading or verification failure."),
    ("booking_widget_failure", r"(?:booking|appointment|reservation)[^\n]{0,80}(?:widget\s+)?(?:failed\s+to\s+load|temporarily\s+unavailable|currently\s+unavailable|could\s+not\s+load)", "A customer-facing booking or reservation interface exposes an availability/loading error."),
    ("form_unavailable", r"(?:contact|enquiry|inquiry|quote|lead|request)[^\n]{0,80}form[^\n]{0,80}(?:currently\s+unavailable|temporarily\s+unavailable|failed\s+to\s+load|could\s+not\s+load)", "A customer-facing form exposes an availability/loading error."),
    ("broken_form_shortcode", r"\[(?:contact-form-7|gravityform|wpforms|formidable|ninja_form)[^\]]*\]", "A raw form shortcode is visible instead of the intended customer form."),
)

# Shared role terms used by bounded journey sampling. Journey-specific priorities live in architecture_model.py.
POLICY_TERMS = ("privacy", "terms", "terms-of-service", "terms_of_service", "cookie-policy", "cookie_policy", "policy")
PROOF_TERMS = ("about", "team", "staff", "reviews", "testimonials", "case-studies", "case_studies", "portfolio", "credentials")

# External booking/scheduling providers are allow-listed to avoid turning the scanner into
# an arbitrary external URL fetcher. Health checks are passive GETs only; no booking is made.
BOOKING_PROVIDER_HOSTS = {
    "Jane": ("janeapp.com",),
    "Cliniko": ("cliniko.com",),
    "Mindbody": ("mindbodyonline.com", "healcode.com"),
    "Calendly": ("calendly.com",),
    "Acuity Scheduling": ("acuityscheduling.com",),
    "OpenTable": ("opentable.com",),
    "Fresha": ("fresha.com",),
    "Square Appointments": ("square.site", "squareup.com", "squareappointments.com"),
    "Vagaro": ("vagaro.com",),
    "Boulevard": ("joinblvd.com",),
    "Phorest": ("phorest.com",),
    "Practice Better": ("practicebetter.io",),
    "SimplePractice": ("simplepractice.com",),
    "Zocdoc": ("zocdoc.com",),
    "Booksy": ("booksy.com",),
}


class _StaticHTMLProbe(HTMLParser):
    """Small dependency-free HTML evidence extractor used when browser evidence is weak."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: List[str] = []
        self._in_title = False
        self.h1_parts: List[List[str]] = []
        self._current_h1: Optional[List[str]] = None
        self.visible_parts: List[str] = []
        self._skip_depth = 0
        self.metas: List[Dict[str, str]] = []
        self.links: List[Dict[str, str]] = []
        self.images: List[Dict[str, str]] = []
        self.forms: List[Dict[str, Any]] = []
        self._form_stack: List[Dict[str, Any]] = []
        self.actions: List[Dict[str, str]] = []
        self._anchor_stack: List[Dict[str, Any]] = []
        self._button_stack: List[Dict[str, Any]] = []
        self.schema_scripts: List[str] = []
        self._schema_buffer: Optional[List[str]] = None
        self.html_lang = ""
        self.generator = ""
        self.has_author_markup = False
        self.has_publication_date_markup = False
        self.cookie_markup = False

    @staticmethod
    def _attrs(attrs: List[Tuple[str, Optional[str]]]) -> Dict[str, str]:
        return {str(k).lower(): str(v or "") for k, v in attrs}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        a = self._attrs(attrs)
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag == "html":
            self.html_lang = a.get("lang", "")
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            self.metas.append(a)
            if a.get("name", "").lower() == "generator":
                self.generator = a.get("content", "")
            if a.get("property", "").lower() == "article:published_time" or a.get("itemprop", "").lower() == "datepublished":
                self.has_publication_date_markup = True
        if tag == "link":
            self.links.append(a)
        if tag == "img":
            self.images.append(a)
        if tag == "h1":
            self._current_h1 = []
            self.h1_parts.append(self._current_h1)
        if tag == "a":
            item = {"href": a.get("href", ""), "text_parts": []}
            self._anchor_stack.append(item)
            if a.get("rel", "").lower() == "author":
                self.has_author_markup = True
        if tag == "button":
            self._button_stack.append({"href": "", "text_parts": [], "type": a.get("type", "")})
        if tag == "iframe" and a.get("src"):
            self.actions.append({"href": a.get("src", ""), "text": a.get("title", "") or a.get("aria-label", "")})
        if tag == "form":
            form = {
                "action": a.get("action", ""),
                "has_inputs": False,
                "has_submit": False,
                "field_count": 0,
                "required_field_count": 0,
            }
            self._form_stack.append(form)
            self.forms.append(form)
        if self._form_stack and tag in {"input", "textarea", "select"}:
            input_type = a.get("type", "").lower() if tag == "input" else ""
            if input_type not in {"submit", "button", "hidden", "image", "reset"}:
                self._form_stack[-1]["has_inputs"] = True
                self._form_stack[-1]["field_count"] += 1
                if "required" in a or a.get("aria-required", "").lower() == "true":
                    self._form_stack[-1]["required_field_count"] += 1
            if tag == "input" and input_type == "submit":
                self._form_stack[-1]["has_submit"] = True
        if self._form_stack and tag == "button" and a.get("type", "submit").lower() in {"", "submit"}:
            self._form_stack[-1]["has_submit"] = True
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._schema_buffer = []
        attrs_blob = " ".join(f"{k}={v}" for k, v in a.items()).lower()
        if "cookie" in attrs_blob or "consent" in attrs_blob:
            self.cookie_markup = True
        if "author" in a.get("class", "").lower() or a.get("itemprop", "").lower() == "author":
            self.has_author_markup = True
        if tag == "time" and a.get("datetime"):
            self.has_publication_date_markup = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._current_h1 = None
        if tag == "a" and self._anchor_stack:
            item = self._anchor_stack.pop()
            self.actions.append({"href": str(item.get("href") or ""), "text": " ".join(item.get("text_parts") or []).strip()})
        if tag == "button" and self._button_stack:
            item = self._button_stack.pop()
            self.actions.append({"href": "", "text": " ".join(item.get("text_parts") or []).strip()})
        if tag == "form" and self._form_stack:
            self._form_stack.pop()
        if tag == "script" and self._schema_buffer is not None:
            self.schema_scripts.append("".join(self._schema_buffer))
            self._schema_buffer = None
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._schema_buffer is not None:
            self._schema_buffer.append(data)
        clean = " ".join((data or "").split())
        if not clean:
            return
        if self._in_title:
            self.title_parts.append(clean)
        if self._current_h1 is not None:
            self._current_h1.append(clean)
        if self._anchor_stack:
            self._anchor_stack[-1]["text_parts"].append(clean)
        if self._button_stack:
            self._button_stack[-1]["text_parts"].append(clean)
        if self._skip_depth == 0:
            self.visible_parts.append(clean)
            # Title text is harmless if duplicated into visible text; the title field is separately recovered below.



class HybridScanner:
    ENGINE_VERSION = "v7.1.1"
    """Three-phase scanner with evidence confidence and business context."""

    def __init__(self, google_api_key: Optional[str] = None):
        self.google_api_key = str(
            google_api_key
            or os.environ.get("PAGESPEED_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
            or ""
        ).strip()
        # Places may use a separately restricted Google key. If none is provided, fall back
        # to GOOGLE_API_KEY and finally the existing PageSpeed/general key for compatibility.
        self.places_api_key = str(
            os.environ.get("GOOGLE_PLACES_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
            or self.google_api_key
            or ""
        ).strip()
        self.session = requests.Session()
        # Fixed Google API calls use this session. Disable environment proxy inheritance so
        # deployment-level proxy variables cannot silently reroute security-sensitive traffic.
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": "TrillokaBot/3.2 Secure Revenue Architecture Auditor"})
        # Every user/page-derived destination goes through a DNS-validated, IP-pinned client.
        self.safe_http = SafeHTTPClient(default_headers={"User-Agent": "TrillokaBot/3.2 Secure Revenue Architecture Auditor"})

    async def execute_hybrid_scan(self, target_domain: str, business_name: str = "", business_type: str = "auto") -> Dict[str, Any]:
        """Run HTTP, Google and mobile-browser evidence collection."""
        # Resolve and reject unsafe destinations before any outbound scan work.
        url = self.safe_http.normalize_target(target_domain)
        scan_started_at = self._utc_now()

        # Keep Playwright on this event loop while moving blocking requests work
        # to worker threads. This avoids executor -> asyncio.run(...) nesting.
        http_meta = await asyncio.to_thread(self._fast_http_preflight, url)
        raw_html = str(http_meta.pop("_http_html", "") or "")
        static_meta = self._extract_static_html_evidence(
            raw_html,
            http_meta.get("final_url") or url,
            verified=bool(http_meta.get("response_ok")),
        )

        resolved_url = http_meta.get("final_url") or url
        site_files = await asyncio.to_thread(self._fetch_site_files, resolved_url)
        pagespeed_meta = await asyncio.to_thread(self._fetch_google_pagespeed, resolved_url)
        crux_meta = await asyncio.to_thread(self._fetch_crux_telemetry, resolved_url)
        try:
            mobile_dom = await self._run_targeted_playwright(
                http_meta.get("final_url") or url,
                pagespeed_meta.get("psi_raw") or {},
                mode="mobile",
            )
        except Exception as exc:  # defensive outer boundary
            print(f"[Hybrid Scanner] Mobile Playwright skipped: {exc}")
            mobile_dom = self._empty_dom_meta(error=str(exc))

        dom_meta = mobile_dom
        if self._needs_browser_retry(mobile_dom, static_meta):
            try:
                desktop_dom = await self._run_targeted_playwright(
                    http_meta.get("final_url") or url,
                    pagespeed_meta.get("psi_raw") or {},
                    mode="desktop",
                )
                dom_meta = self._merge_dom_attempts(mobile_dom, desktop_dom)
            except Exception as exc:
                print(f"[Hybrid Scanner] Desktop retry skipped: {exc}")

        evidence_meta = self._merge_static_and_dom(static_meta, dom_meta)

        # Resolve the target business in Google Places only after page evidence exists, so the
        # page title can help identify a business when the user supplies only a domain.
        place_query_name = self._business_name_hint(target_domain, business_name, evidence_meta)
        places_meta = await asyncio.to_thread(
            self._fetch_google_places, target_domain, place_query_name
        )

        combined: Dict[str, Any] = {
            "domain": target_domain,
            "url": url,
            **http_meta,
            **site_files,
            **pagespeed_meta,
            **crux_meta,
            **places_meta,
            **evidence_meta,
        }

        # A response may be blocked to requests but available in the browser, or vice versa.
        combined["is_reachable"] = bool(
            http_meta.get("is_reachable") or dom_meta.get("browser_loaded")
        )
        combined["has_ssl"] = bool(
            urllib.parse.urlparse(combined.get("final_url") or url).scheme == "https"
        )

        # First-pass journey/context inference chooses the most commercially relevant internal pages.
        # Legacy business_type values are weak hints only; strong page/action evidence wins.
        initial_architecture_profile = infer_architecture_profile(combined, business_type)

        # Bounded multi-page journey inspection. This is passive: GET requests only, same origin,
        # no form submissions, no cart mutation, no login and no customer data entry.
        candidate_links = self._union_strings(
            static_meta.get("internal_links"),
            dom_meta.get("internal_links"),
        )
        journey_meta = await asyncio.to_thread(
            self._scan_priority_journey_pages,
            resolved_url,
            candidate_links,
            str(initial_architecture_profile.get("journey_model") or "general"),
            list(initial_architecture_profile.get("context_tags") or []),
        )
        self._merge_journey_evidence(combined, journey_meta)

        # Render exactly one highest-priority customer-journey page in Chromium. Static GETs remain
        # the bounded breadth pass; this one extra render catches JavaScript-only widget/form failures.
        browser_journey_url = str(journey_meta.get("browser_journey_candidate_url") or "")
        if browser_journey_url:
            try:
                browser_journey = await self._run_targeted_playwright(
                    browser_journey_url, {}, mode="mobile", capture_evidence=True
                )
                self._merge_browser_journey_evidence(combined, browser_journey, browser_journey_url)
            except Exception as exc:
                combined["browser_journey_probe"] = {"url": browser_journey_url, "browser_loaded": False, "error": str(exc)[:220]}
                combined["browser_journey_rendered"] = False
        else:
            combined["browser_journey_probe"] = {}
            combined["browser_journey_rendered"] = False

        # Safely verify known third-party booking destinations discovered on the homepage/journey.
        provider_health = await asyncio.to_thread(
            self._check_external_booking_provider_health, combined.get("booking_provider_links") or []
        )
        combined["external_booking_provider_health"] = provider_health
        if provider_health.get("error_signals"):
            existing = list(combined.get("conversion_error_signals") or [])
            combined["conversion_error_signals"] = existing + list(provider_health.get("error_signals") or [])
            combined["conversion_path_error_detected"] = True

        # Re-infer after the bounded journey sample because booking/quote/checkout/proof pages can
        # expose a clearer revenue path than a generic homepage.
        architecture_profile = infer_architecture_profile(combined, business_type)
        combined["architecture_profile"] = architecture_profile
        # Legacy alias retained for current report/frontend integrations.
        combined["business_profile"] = architecture_profile
        combined["h1_relevance_status"] = self._assess_h1_relevance(combined, architecture_profile)
        combined["business_type_validation"] = self._business_type_validation(business_type, architecture_profile)

        # Local competitor benchmarking is contextual evidence only. It does not directly change
        # Revenue Readiness. Target identity must be independently credible and competitors must
        # share the same customer-journey architecture before entering the combined benchmark.
        competitor_benchmark = await asyncio.to_thread(
            self._fetch_local_competitors,
            places_meta,
            architecture_profile,
            combined,
        )
        combined["competitor_benchmark"] = competitor_benchmark
        combined["competitor_data_available"] = bool(competitor_benchmark.get("available"))

        combined["scan_quality"] = self._build_scan_quality(combined)
        combined["evidence_coverage"] = self._evidence_coverage(combined)
        combined["scanner_engine_version"] = self.ENGINE_VERSION
        combined["scan_started_at"] = scan_started_at
        combined["scan_completed_at"] = self._utc_now()
        return combined

    @staticmethod
    def _normalize_url(target_domain: str) -> str:
        """Backward-compatible normalizer with strict public-network validation."""
        return validate_public_http_url(target_domain).url

    def _fast_http_preflight(self, url: str) -> Dict[str, Any]:
        preflight: Dict[str, Any] = {
            "is_reachable": False,
            "response_ok": False,
            "has_ssl": url.startswith("https://"),
            "status_code": 0,
            "headers": {},
            "final_url": url,
            "redirect_chain": [],
            "https_redirect_enforced": None,
            "http_preflight_error": "",
            "http_bot_challenge_suspected": False,
            "http_html_length": 0,
            "http_html_sha256": "",
            "_http_html": "",
        }
        try:
            response = self.safe_http.get(url, timeout=(5, 12), allow_redirects=True, max_bytes=1_600_000)
            history = [
                {"status_code": r.status_code, "url": r.url, "location": r.headers.get("Location")}
                for r in response.history
            ]
            preflight.update(
                {
                    "is_reachable": True,
                    "response_ok": 200 <= response.status_code < 400,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "final_url": response.url,
                    "redirect_chain": history,
                    "has_ssl": urllib.parse.urlparse(response.url).scheme == "https",
                }
            )
            raw_html = response.text or ""
            # Keep a bounded in-memory copy only for evidence extraction; it is removed before final scan output.
            bounded_html = raw_html[:1_500_000]
            preflight["_http_html"] = bounded_html
            preflight["http_html_length"] = len(raw_html)
            preflight["http_html_sha256"] = hashlib.sha256(raw_html.encode("utf-8", errors="ignore")).hexdigest() if raw_html else ""
            body_sample = bounded_html[:12000].lower()
            preflight["http_bot_challenge_suspected"] = (
                response.status_code in {403, 429}
                or any(pattern in body_sample for pattern in BOT_CHALLENGE_PATTERNS)
            )
        except Exception as exc:
            preflight["http_preflight_error"] = str(exc)
            print(f"[Hybrid Scanner] HTTP preflight failed for {url}: {exc}")

        preflight["https_redirect_enforced"] = self._check_https_redirect(url)
        return preflight

    def _check_https_redirect(self, url: str) -> Optional[bool]:
        """Return True/False only when the HTTP redirect behavior is actually conclusive.

        A WAF/challenge/4xx/5xx response is not evidence that HTTPS enforcement is missing;
        those cases remain UNKNOWN (None).
        """
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                return None
            http_url = urllib.parse.urlunparse(
                ("http", parsed.netloc, parsed.path or "/", parsed.params, parsed.query, "")
            )
            response = self.safe_http.get(http_url, timeout=(4, 8), allow_redirects=True, max_bytes=180_000)
            final_scheme = urllib.parse.urlparse(response.url).scheme.lower()
            if final_scheme == "https":
                return True

            body_sample = (response.text or "")[:12000].lower()
            ambiguous = (
                response.status_code >= 400
                or any(pattern in body_sample for pattern in BOT_CHALLENGE_PATTERNS)
            )
            if ambiguous:
                return None

            # A successful final HTTP document with no HTTPS redirect is conclusive.
            if 200 <= response.status_code < 400 and final_scheme == "http":
                return False
        except Exception:
            return None
        return None

    def _fetch_site_files(self, url: str) -> Dict[str, Any]:
        parsed = urllib.parse.urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        out: Dict[str, Any] = {
            "robots_valid": None,
            "robots_status_code": None,
            "sitemap_present": None,
            "sitemap_status_code": None,
        }

        sitemap_candidates: List[str] = [f"{origin}/sitemap.xml"]
        try:
            robots = self.safe_http.get(f"{origin}/robots.txt", timeout=(4, 8), allow_redirects=True, max_bytes=300_000)
            out["robots_status_code"] = robots.status_code
            if robots.status_code == 200 and (robots.text or "").strip():
                out["robots_valid"] = True
                for line in robots.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        candidate = line.split(":", 1)[1].strip()
                        if candidate.startswith(("http://", "https://")):
                            sitemap_candidates.insert(0, candidate)
            elif robots.status_code in {404, 410}:
                out["robots_valid"] = False
        except Exception:
            pass

        for candidate in dict.fromkeys(sitemap_candidates):
            try:
                sitemap = self.safe_http.get(candidate, timeout=(4, 8), allow_redirects=True, max_bytes=500_000)
                out["sitemap_status_code"] = sitemap.status_code
                sample = (sitemap.text or "")[:2000].lower()
                if sitemap.status_code == 200 and ("<urlset" in sample or "<sitemapindex" in sample):
                    out["sitemap_present"] = True
                    out["sitemap_url"] = sitemap.url
                    break
                if sitemap.status_code in {404, 410} and out["sitemap_present"] is None:
                    out["sitemap_present"] = False
            except Exception:
                continue
        return out

    def _fetch_google_pagespeed(self, url: str) -> Dict[str, Any]:
        encoded_url = urllib.parse.quote(url, safe="")
        endpoint = (
            "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
            f"?url={encoded_url}&category=PERFORMANCE&category=SEO&strategy=mobile"
        )
        if self.google_api_key:
            endpoint += f"&key={self.google_api_key}"

        unavailable = {
            "performance_score": None,
            "google_seo_score": None,
            "pagespeed_api_status": "unavailable",
            "pagespeed_error": "",
            "psi_raw": {},
            "psi_lcp_ms": None,
            "psi_cls": None,
            "psi_viewport_configured": None,
            "psi_render_blocking_count": None,
            "psi_tap_targets_flagged": None,
            "psi_lazy_images_score": None,
        }

        try:
            try:
                read_timeout = float(os.environ.get("PAGESPEED_READ_TIMEOUT_SECONDS", "45"))
            except (TypeError, ValueError):
                read_timeout = 45.0
            # Google Lighthouse can legitimately take longer than 20 seconds.
            read_timeout = max(20.0, min(read_timeout, 120.0))

            response = self.session.get(endpoint, timeout=(5, read_timeout))
            if response.status_code != 200:
                unavailable["pagespeed_error"] = f"HTTP {response.status_code}"
                return unavailable

            data = response.json()
            lighthouse = data.get("lighthouseResult") or {}
            categories = lighthouse.get("categories") or {}
            audits = lighthouse.get("audits") or {}

            def category_score(name: str) -> Optional[float]:
                raw = (categories.get(name) or {}).get("score")
                numeric = self._to_float(raw)
                return round(numeric * 100, 1) if numeric is not None else None

            tap_audit = audits.get("tap-targets") or {}
            tap_details = (tap_audit.get("details") or {}).get("items")
            tap_flagged = len(tap_details) if isinstance(tap_details, list) else None

            blocking = audits.get("render-blocking-resources") or {}
            blocking_items = (blocking.get("details") or {}).get("items")
            blocking_count = len(blocking_items) if isinstance(blocking_items, list) else None

            return {
                "performance_score": category_score("performance"),
                "google_seo_score": category_score("seo"),
                "pagespeed_api_status": "success",
                "pagespeed_error": "",
                "psi_raw": data,
                "psi_lcp_ms": self._audit_numeric(audits, "largest-contentful-paint"),
                "psi_cls": self._audit_numeric(audits, "cumulative-layout-shift"),
                "psi_viewport_configured": self._audit_pass(audits, "viewport"),
                "psi_render_blocking_count": blocking_count,
                "psi_tap_targets_flagged": tap_flagged,
                "psi_lazy_images_score": (audits.get("offscreen-images") or {}).get("score"),
            }
        except requests.Timeout as exc:
            unavailable["pagespeed_error"] = f"timeout: {exc}"
            print(f"[Hybrid Scanner] PageSpeed API timeout: {exc}")
            return unavailable
        except Exception as exc:
            unavailable["pagespeed_error"] = str(exc)
            print(f"[Hybrid Scanner] PageSpeed API error: {exc}")
            return unavailable

    @staticmethod
    def _audit_numeric(audits: Dict[str, Any], audit_id: str) -> Optional[float]:
        value = (audits.get(audit_id) or {}).get("numericValue")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _audit_pass(audits: Dict[str, Any], audit_id: str) -> Optional[bool]:
        audit = audits.get(audit_id)
        if not isinstance(audit, dict) or audit.get("score") is None:
            return None
        try:
            return float(audit.get("score")) >= 0.9
        except (TypeError, ValueError):
            return None

    def _fetch_crux_telemetry(self, url: str) -> Dict[str, Any]:
        if not self.google_api_key:
            return {
                "crux_available": False,
                "crux_reason": "No API key configured",
                "crux_lcp_ms": None,
                "crux_cls": None,
                "crux_inp_ms": None,
                "real_user_speed_grade": "UNKNOWN",
            }

        endpoint = f"https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={self.google_api_key}"
        parsed = urllib.parse.urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        try:
            response = self.session.post(endpoint, json={"origin": origin}, timeout=(4, 12))
            if response.status_code == 200:
                metrics = (response.json().get("record") or {}).get("metrics") or {}
                lcp = self._crux_p75(metrics, "largest_contentful_paint")
                cls_value = self._crux_p75(metrics, "cumulative_layout_shift")
                inp = self._crux_p75(metrics, "interaction_to_next_paint")
                cls_float = self._to_float(cls_value)
                return {
                    "crux_available": True,
                    "crux_reason": "",
                    "crux_lcp_ms": self._to_float(lcp),
                    "crux_cls": cls_float,
                    "crux_inp_ms": self._to_float(inp),
                    "real_user_speed_grade": self._grade_core_web_vitals(
                        self._to_float(lcp), self._to_float(inp), cls_float
                    ),
                }
            if response.status_code == 404:
                reason = "Insufficient traffic for CrUX dataset"
            else:
                reason = f"CrUX HTTP {response.status_code}"
        except Exception as exc:
            reason = str(exc)
            print(f"[Hybrid Scanner] CrUX API error: {exc}")
        return {
            "crux_available": False,
            "crux_reason": reason,
            "crux_lcp_ms": None,
            "crux_cls": None,
            "crux_inp_ms": None,
            "real_user_speed_grade": "UNKNOWN",
        }

    @staticmethod
    def _crux_p75(metrics: Dict[str, Any], name: str) -> Any:
        return ((metrics.get(name) or {}).get("percentiles") or {}).get("p75")

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            parsed = float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        if parsed is None or not math.isfinite(parsed):
            return None
        return parsed

    @staticmethod
    def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
        parsed = HybridScanner._to_float(value)
        return int(parsed) if parsed is not None else default

    @staticmethod
    def _grade_core_web_vitals(lcp: Optional[float], inp: Optional[float], cls_value: Optional[float]) -> str:
        values = [value for value in (lcp, inp, cls_value) if value is not None]
        if not values:
            return "UNKNOWN"
        if (lcp is not None and lcp > 4000) or (inp is not None and inp > 500) or (cls_value is not None and cls_value > 0.25):
            return "POOR"
        if (lcp is not None and lcp > 2500) or (inp is not None and inp > 200) or (cls_value is not None and cls_value > 0.1):
            return "NEEDS_IMPROVEMENT"
        return "GOOD"

    @staticmethod
    def _host_from_url(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            if not text.startswith(("http://", "https://")):
                text = "https://" + text
            host = urllib.parse.urlparse(text).netloc.lower().split("@")[-1].split(":")[0]
            return host[4:] if host.startswith("www.") else host
        except Exception:
            return ""

    @staticmethod
    def _business_name_hint(target_domain: str, business_name: str, evidence: Dict[str, Any]) -> str:
        explicit = str(business_name or "").strip()
        if explicit:
            return explicit[:100]
        title = str((evidence or {}).get("title") or "").strip()
        if title:
            # Most business titles put the brand before a pipe/dash. Keep this conservative.
            piece = re.split(r"\s*[|–—]\s*|\s+-\s+", title, maxsplit=1)[0].strip()
            if 2 <= len(piece) <= 80:
                return piece
        host = HybridScanner._host_from_url(target_domain)
        stem = host.split(".")[0] if host else str(target_domain or "")
        return re.sub(r"[-_]+", " ", stem).strip()[:100]

    def _fetch_google_places(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
        if not self.places_api_key:
            return {"places_found": False, "places_confidence": "unknown", "places_reason": "Google API key unavailable", "benchmark_identity_verified": False}

        query = str(business_name or "").strip() or self._host_from_url(target_domain) or str(target_domain or "")
        endpoint = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.places_api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.rating,places.userRatingCount,"
                "places.formattedAddress,places.location,places.primaryType,places.types,places.websiteUri"
            ),
        }
        target_host = self._host_from_url(target_domain)
        domain_stem = re.sub(r"[^a-z0-9]+", " ", (target_host.split(".")[0] if target_host else "").lower()).strip()

        def tokens(value: str) -> set[str]:
            stop = {"the", "and", "for", "inc", "ltd", "llc", "corp", "company", "co", "group"}
            return {x for x in re.findall(r"[a-z0-9]+", str(value or "").lower()) if len(x) >= 3 and x not in stop}

        q_tokens = tokens(query)
        stem_tokens = tokens(domain_stem)
        try:
            response = self.session.post(endpoint, json={"textQuery": query, "pageSize": 5}, headers=headers, timeout=(4, 12))
            if response.status_code != 200:
                return {"places_found": False, "places_confidence": "unknown", "places_reason": f"Places HTTP {response.status_code}", "benchmark_identity_verified": False}
            places = response.json().get("places") or []
            if not places:
                return {"places_found": False, "places_confidence": "unknown", "places_reason": "No matching place", "benchmark_identity_verified": False}

            def candidate_components(place: Dict[str, Any]) -> Tuple[float, bool, float, float, str]:
                website_host = self._host_from_url(place.get("websiteUri") or "")
                display = str((place.get("displayName") or {}).get("text") or "")
                d_tokens = tokens(display)
                domain_match = bool(target_host and website_host and (website_host == target_host or website_host.endswith("." + target_host) or target_host.endswith("." + website_host)))
                q_similarity = len(q_tokens & d_tokens) / max(1, len(q_tokens | d_tokens)) if q_tokens and d_tokens else 0.0
                stem_similarity = len(stem_tokens & d_tokens) / max(1, len(stem_tokens)) if stem_tokens else 0.0
                score = (100.0 if domain_match else 0.0) + q_similarity * 30.0 + stem_similarity * 20.0
                score += min(2.0, (self._to_float(place.get("userRatingCount")) or 0.0) / 500.0)
                return score, domain_match, q_similarity, stem_similarity, website_host

            place = max(places, key=lambda x: candidate_components(x)[0])
            best_score, domain_match, q_similarity, stem_similarity, website_host = candidate_components(place)
            # Strongest proof is the site's own domain. If Google has no website, a very strong name
            # match may still be used. A conflicting Google website domain is never silently accepted.
            no_conflicting_site = not website_host
            benchmark_identity_verified = bool(domain_match or (no_conflicting_site and q_similarity >= 0.72 and stem_similarity >= 0.50))
            if domain_match:
                confidence = "high"
                basis = "website_domain"
            elif benchmark_identity_verified:
                confidence = "medium"
                basis = "strong_name_no_conflicting_domain"
            elif q_similarity >= 0.45:
                confidence = "low"
                basis = "name_only_unverified"
            else:
                confidence = "low"
                basis = "weak_name_match"
            location = place.get("location") or {}
            return {
                "places_found": True,
                "places_confidence": confidence,
                "place_match_basis": basis,
                "place_identity_score": round(best_score, 1),
                "place_name_similarity": round(q_similarity, 3),
                "place_domain_stem_similarity": round(stem_similarity, 3),
                "benchmark_identity_verified": benchmark_identity_verified,
                "benchmark_identity_reason": "Verified target identity" if benchmark_identity_verified else "Google Place target identity could not be tied confidently to the scanned domain; local commercial benchmark will be withheld.",
                "place_id": place.get("id"),
                "place_display_name": (place.get("displayName") or {}).get("text", ""),
                "google_rating": self._to_float(place.get("rating")),
                "google_review_count": self._to_int(place.get("userRatingCount"), 0),
                "place_formatted_address": place.get("formattedAddress") or "",
                "place_location": {"latitude": self._to_float(location.get("latitude")), "longitude": self._to_float(location.get("longitude"))},
                "place_primary_type": place.get("primaryType") or "",
                "place_types": list(place.get("types") or []),
                "place_website_uri": place.get("websiteUri") or "",
                "has_visual_review_proof": None,
            }
        except Exception as exc:
            print(f"[Hybrid Scanner] Places API error: {exc}")
            return {"places_found": False, "places_confidence": "unknown", "places_reason": str(exc), "benchmark_identity_verified": False}

    @staticmethod
    def _competitor_search_text(journey_model: str) -> str:
        return architecture_competitor_search_text(journey_model)

    @staticmethod
    def _competitor_search_query(target_place: Dict[str, Any], architecture_profile: Dict[str, Any]) -> str:
        """Build a specific Places fallback query from verified target identity + offering evidence.

        A generic journey query such as ``local service provider`` can surface telecoms, stores or
        unrelated service businesses.  Prefer the target's specific Google type and strong journey
        phrases (for example ``general contractor custom home renovation``) and only fall back to
        the broad journey query when neither is available.
        """
        generic_types = {
            "", "establishment", "point_of_interest", "service", "business", "organization",
            "store", "professional_service", "local_business",
        }
        primary = str((target_place or {}).get("place_primary_type") or "").strip().lower()
        type_candidates = [primary] + [str(x or "").strip().lower() for x in ((target_place or {}).get("place_types") or [])]
        specific_type = next((x for x in type_candidates if x and x not in generic_types), "")

        generic_signal_phrases = {
            "contact us", "contact", "book", "booking", "reserve", "reservation", "order",
            "verified reservation path", "verified order-online path", "verified add-to-cart",
            "verified checkout context", "direct-purchase journey",
        }
        offering_terms: List[str] = []
        for raw in ((architecture_profile or {}).get("journey_signals") or (architecture_profile or {}).get("signals") or []):
            text = str(raw or "").strip().lower()
            if ":" in text and text.split(":", 1)[0] in {"hero", "meta", "action"}:
                text = text.split(":", 1)[1].strip()
            text = re.sub(r"[^a-z0-9&+ /-]+", " ", text)
            text = " ".join(text.split())
            if not text or text in generic_signal_phrases or text.startswith("direct_journey_hint"):
                continue
            if len(text) < 4 or len(text) > 42:
                continue
            if text not in offering_terms:
                offering_terms.append(text)
            if len(offering_terms) >= 2:
                break

        parts: List[str] = []
        if specific_type:
            friendly = specific_type.replace("_", " ")
            # Google types can end in generic suffixes; keep them because they still anchor category.
            parts.append(friendly)
        parts.extend(offering_terms)
        query = " ".join(dict.fromkeys(parts)).strip()
        if query:
            return query[:120]
        return architecture_competitor_search_text(str((architecture_profile or {}).get("journey_model") or "general"))

    @staticmethod
    def _places_candidate_key(place: Dict[str, Any]) -> str:
        place_id = str((place or {}).get("id") or "").strip()
        if place_id:
            return "id:" + place_id
        website = HybridScanner._host_from_url(str((place or {}).get("websiteUri") or ""))
        if website:
            return "web:" + website
        name = str(((place or {}).get("displayName") or {}).get("text") or "").strip().lower()
        return "name:" + re.sub(r"\s+", " ", name)

    @staticmethod
    def _expected_competitor_actions(journey_model: str) -> set:
        return architecture_expected_actions(journey_model)

    def _competitor_commercial_score(self, signals: Dict[str, Any], journey_model: str, context_tags: Optional[List[str]] = None) -> Optional[float]:
        if not isinstance(signals, dict) or not (signals.get("static_html_verified") or signals.get("browser_loaded")):
            return None
        model = str(journey_model or "general")
        tags = {str(x) for x in (context_tags or []) if x}
        actions = set(str(x) for x in (signals.get("mobile_cta_types") or []) if x)
        expected = self._expected_competitor_actions(model)
        score = 0.0
        if actions & expected:
            score += 36.0
        elif actions:
            score += 16.0

        if model in {"lead_quote", "appointment_consultation", "reservation_event", "demo_sales"} and signals.get("forms_present"):
            score += 10.0
        elif model in {"direct_purchase", "membership_subscription"} and signals.get("forms_present"):
            score += 4.0

        if model in {"lead_quote", "appointment_consultation", "reservation_event"} and signals.get("click_to_call_present"):
            score += 8.0
        if model == "demo_sales" and signals.get("pricing_linked"):
            score += 9.0
        if signals.get("reviews_visible") or signals.get("social_proof_present"):
            score += 14.0
        if signals.get("privacy_policy_linked") or signals.get("terms_linked"):
            score += 5.0
        if model == "direct_purchase" and (signals.get("shipping_info_linked") or signals.get("return_policy_linked")):
            score += 10.0
        if "regulated_high_trust" in tags and signals.get("credential_signals_present"):
            score += 7.0
        if "enterprise_considered_purchase" in tags and signals.get("case_studies_portfolio_present"):
            score += 7.0
        if signals.get("mobile_viewport_configured"):
            score += 6.0
        if signals.get("schema_present"):
            score += 3.0
        return round(min(100.0, score), 1)

    @staticmethod
    def _coarse_business_category_from_place(primary_type: str, place_types: Optional[List[str]] = None) -> str:
        text = " ".join([str(primary_type or "")] + [str(x or "") for x in (place_types or [])]).lower().replace("_", " ")
        groups = {
            "construction_trades": ("contractor", "construction", "roofer", "roofing", "electrician", "plumber", "plumbing", "carpenter", "painter", "home builder", "remodel", "renovation"),
            "healthcare": ("physio", "physiotherapist", "medical", "doctor", "dentist", "dental", "chiropr", "clinic", "health", "therapy", "therapist"),
            "legal": ("lawyer", "attorney", "law firm", "legal service"),
            "hospitality_event": ("restaurant", "hotel", "lodging", "cater", "wedding", "event venue", "tour", "charter", "travel agency"),
            "retail_commerce": ("store", "retail", "shopping", "clothing", "furniture", "jewelry", "supermarket"),
            "technology_telecom": ("software", "telecommunication", "internet service", "computer", "it service", "technology"),
            "finance_insurance": ("bank", "insurance", "financial", "accounting", "accountant", "mortgage"),
        }
        for category, terms in groups.items():
            if any(term in text for term in terms):
                return category
        return "unknown"

    @staticmethod
    def _coarse_business_category_from_content(signals: Dict[str, Any], profile: Dict[str, Any]) -> str:
        title = str(signals.get("title") or "")
        meta = str(signals.get("meta_description") or "")
        h1 = " ".join(str(x) for x in (signals.get("h1_tags") or []) if x)
        page = str(signals.get("page_text") or "")[:12000]
        text = f"{title} {meta} {h1} {page}".lower()
        weighted = {
            "construction_trades": ("general contractor", "construction", "renovation", "custom home", "home builder", "roofing", "electrician", "plumbing", "remodel"),
            "healthcare": ("physiotherapy", "physiotherapist", "dental clinic", "dentist", "medical clinic", "chiropractic", "patient", "therapy clinic"),
            "legal": ("law firm", "lawyer", "attorney", "legal services", "immigration law"),
            "hospitality_event": ("restaurant", "wedding venue", "event venue", "hotel", "catering", "charter", "cruise", "reservation"),
            "retail_commerce": ("shop now", "add to cart", "checkout", "online store", "shipping", "buy now"),
            "technology_telecom": ("software platform", "saas", "telecommunications", "internet provider", "managed it", "cloud services"),
            "finance_insurance": ("insurance", "financial advisor", "accounting firm", "accountant", "mortgage broker"),
        }
        scores: Dict[str, int] = {}
        for category, terms in weighted.items():
            scores[category] = sum(1 for term in terms if term in text)
        category, score = max(scores.items(), key=lambda kv: kv[1])
        if score >= 2:
            return category

        # A resolved high-confidence journey can support a coarse category only when its signals
        # are category-specific enough. This is deliberately conservative.
        model = str((profile or {}).get("journey_model") or "")
        tags = {str(x) for x in ((profile or {}).get("context_tags") or []) if x}
        if "regulated_high_trust" in tags and any(x in text for x in ("physio", "dental", "medical", "patient")):
            return "healthcare"
        if model == "direct_purchase" and any(x in text for x in ("add to cart", "checkout", "shop now")):
            return "retail_commerce"
        if model == "reservation_event" and any(x in text for x in ("restaurant", "wedding", "venue", "charter", "hotel")):
            return "hospitality_event"
        return "unknown"

    @classmethod
    def _competitor_probe_identity_check(cls, competitor: Dict[str, Any], signals: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        expected = cls._coarse_business_category_from_place(
            str((competitor or {}).get("primary_type") or ""),
            list((competitor or {}).get("place_types") or []),
        )
        observed = cls._coarse_business_category_from_content(signals, profile)
        conflict = bool(expected != "unknown" and observed != "unknown" and expected != observed)
        return {
            "expected_category": expected,
            "observed_category": observed,
            "conflict": conflict,
            "reason": (
                f"Google Places category '{expected}' conflicts with probed website content category '{observed}'. "
                "The website probe is excluded from the benchmark because the fetched content may be stale, compromised, redirected or otherwise not representative."
                if conflict else ""
            ),
        }

    def _probe_competitor_website(self, competitor: Dict[str, Any], target_profile: Dict[str, Any]) -> Dict[str, Any]:
        url = str((competitor or {}).get("website") or "").strip()
        if not url:
            return {"website_probed": False, "commercial_score": None, "probe_reason": "No website URL"}
        try:
            response = self.safe_http.get(
                self._normalize_url(url), timeout=(3, 7), allow_redirects=True, max_bytes=800_000,
                headers={"User-Agent": "TrillokaBot/3.2 Secure Local Benchmark Probe"},
            )
            if not (200 <= response.status_code < 400):
                return {"website_probed": False, "commercial_score": None, "probe_reason": f"HTTP {response.status_code}"}
            html_text = (response.text or "")[:750_000]
            signals = self._extract_static_html_evidence(html_text, response.url, verified=True)
            profile = infer_architecture_profile(signals, "auto")
            identity_check = self._competitor_probe_identity_check(competitor, signals, profile)
            if identity_check.get("conflict"):
                return {
                    "website_probed": False,
                    "commercial_score": None,
                    "architecture_profile": profile,
                    "probe_identity_check": identity_check,
                    "probe_reason": "PROBE_CONTENT_MISMATCH: " + str(identity_check.get("reason") or "category conflict"),
                    "commercial_features": {
                        "actions": list(signals.get("mobile_cta_types") or []),
                        "forms": bool(signals.get("forms_present")),
                        "click_to_call": bool(signals.get("click_to_call_present")),
                        "pricing": bool(signals.get("pricing_linked")),
                        "social_proof": bool(signals.get("reviews_visible") or signals.get("social_proof_present")),
                        "mobile_viewport": bool(signals.get("mobile_viewport_configured")),
                    },
                }
            commercial = self._competitor_commercial_score(signals, str(profile.get("journey_model") or "general"), list(profile.get("context_tags") or []))
            return {
                "website_probed": bool(signals.get("static_html_verified")),
                "commercial_score": commercial,
                "architecture_profile": profile,
                "probe_identity_check": identity_check,
                "commercial_features": {
                    "actions": list(signals.get("mobile_cta_types") or []),
                    "forms": bool(signals.get("forms_present")),
                    "click_to_call": bool(signals.get("click_to_call_present")),
                    "pricing": bool(signals.get("pricing_linked")),
                    "social_proof": bool(signals.get("reviews_visible") or signals.get("social_proof_present")),
                    "mobile_viewport": bool(signals.get("mobile_viewport_configured")),
                },
            }
        except Exception as exc:
            return {"website_probed": False, "commercial_score": None, "probe_reason": str(exc)}

    @staticmethod
    def _local_index(rating: Optional[float], review_count: Optional[int], commercial_score: Optional[float], max_reviews: int) -> Optional[float]:
        components = []
        if commercial_score is not None:
            components.append((float(commercial_score), 0.50))
        if rating is not None:
            components.append((max(0.0, min(100.0, float(rating) * 20.0)), 0.30))
        if review_count is not None and max_reviews > 0:
            review_component = 100.0 * math.log1p(max(0, int(review_count))) / math.log1p(max_reviews)
            components.append((max(0.0, min(100.0, review_component)), 0.20))
        if not components:
            return None
        total_weight = sum(weight for _, weight in components)
        return round(sum(value * weight for value, weight in components) / total_weight, 1)

    @staticmethod
    def _competitor_relevance_score(target_profile: Dict[str, Any], target_place: Dict[str, Any], competitor: Dict[str, Any]) -> Tuple[float, bool, str]:
        comp_profile = competitor.get("architecture_profile") if isinstance(competitor.get("architecture_profile"), dict) else {}
        target_model = str((target_profile or {}).get("journey_model") or "general")
        comp_model = str((comp_profile or {}).get("journey_model") or "general")
        if target_model == "general" or bool((target_profile or {}).get("provisional")):
            return 0.0, False, "Target journey model is provisional"
        if comp_model != target_model or bool((comp_profile or {}).get("provisional")):
            return 0.0, False, "Customer journey model is not sufficiently comparable"

        score = 45.0  # same commercial journey is mandatory and carries the largest share.
        target_primary = str((target_place or {}).get("place_primary_type") or "")
        comp_primary = str(competitor.get("primary_type") or "")
        if target_primary and comp_primary and target_primary == comp_primary:
            score += 25.0
        target_types = {str(x) for x in ((target_place or {}).get("place_types") or []) if x}
        comp_types = {str(x) for x in (competitor.get("place_types") or []) if x}
        shared_types = target_types & comp_types
        type_compatible = bool((target_primary and comp_primary and target_primary == comp_primary) or shared_types)
        if shared_types:
            score += 10.0

        # Journey equality alone is too broad (for example a heliport and a private cruise can both
        # expose a booking action). Require either Google-type compatibility or meaningful overlap in
        # non-generic journey evidence before a business can enter the commercial benchmark.
        generic_signal_tokens = {"action", "hero", "meta", "contact", "book", "booking", "reserve", "reservation", "customer", "journey", "verified", "path"}
        def signal_tokens(profile: Dict[str, Any]) -> set[str]:
            raw = profile.get("journey_signals") or profile.get("signals") or []
            tokens: set[str] = set()
            for item in raw:
                for token in re.findall(r"[a-z0-9]+", str(item or "").lower()):
                    if len(token) >= 4 and token not in generic_signal_tokens:
                        tokens.add(token)
            return tokens
        target_signal_tokens = signal_tokens(target_profile or {})
        comp_signal_tokens = signal_tokens(comp_profile or {})
        offering_overlap = target_signal_tokens & comp_signal_tokens
        if len(offering_overlap) >= 2:
            score += 10.0
        elif len(offering_overlap) == 1:
            score += 4.0

        target_tags = {str(x) for x in ((target_profile or {}).get("context_tags") or []) if x}
        comp_tags = {str(x) for x in ((comp_profile or {}).get("context_tags") or []) if x}
        meaningful_tags = target_tags & comp_tags & {"regulated_high_trust", "local_location_dependent", "commerce_payment", "enterprise_considered_purchase", "hospitality_event"}
        score += min(15.0, 5.0 * len(meaningful_tags))

        expected = architecture_expected_actions(target_model)
        actions = {str(x) for x in (((competitor.get("commercial_features") or {}).get("actions") or [])) if x}
        if expected & actions:
            score += 10.0
        score = min(100.0, score)
        offering_compatible = bool(type_compatible or len(offering_overlap) >= 2)
        eligible = bool(score >= 65.0 and offering_compatible)
        if eligible:
            reason = "Comparable journey/context with offering/type support"
        elif not offering_compatible:
            reason = "Same broad journey, but offering/type evidence is not sufficiently comparable"
        else:
            reason = "Relevance below benchmark threshold"
        return round(score, 1), eligible, reason

    def _fetch_local_competitors(self, target_place: Dict[str, Any], architecture_profile: Dict[str, Any], target_scan: Dict[str, Any]) -> Dict[str, Any]:
        journey_model = str((architecture_profile or {}).get("journey_model") or "general")
        context_tags = list((architecture_profile or {}).get("context_tags") or [])
        base = {
            "available": False,
            "status": "unavailable",
            "business_type": journey_model,  # legacy key
            "journey_model": journey_model,
            "sample_count": 0,
            "benchmark_basis": "VERIFIED_TARGET_IDENTITY_PLUS_JOURNEY_CONTEXT_PLUS_PUBLIC_HOMEPAGE_STRUCTURE",
            "source_label": "Google Places + public website structure",
            "does_not_directly_change_readiness_score": True,
            "target_identity_verified": bool((target_place or {}).get("benchmark_identity_verified")),
        }
        if not self.places_api_key:
            return {**base, "reason": "Google API key unavailable"}
        if not (target_place or {}).get("places_found"):
            return {**base, "reason": "Target business could not be located in Google Places"}
        if not (target_place or {}).get("benchmark_identity_verified"):
            return {**base, "reason": str((target_place or {}).get("benchmark_identity_reason") or "Target Place identity was not confidently tied to the scanned domain")}
        if bool((architecture_profile or {}).get("provisional")):
            return {**base, "reason": "Journey model is provisional; competitor benchmark withheld until the customer journey is resolved"}

        location = (target_place or {}).get("place_location") or {}
        lat = self._to_float(location.get("latitude"))
        lng = self._to_float(location.get("longitude"))
        if lat is None or lng is None:
            return {**base, "reason": "Target Place has no usable latitude/longitude"}

        radius = self._to_float(os.environ.get("TRILLOKA_COMPETITOR_RADIUS_METERS")) or 8000.0
        radius = max(1000.0, min(25000.0, radius))
        max_results = self._to_int(os.environ.get("TRILLOKA_COMPETITOR_MAX_RESULTS"), 8) or 8
        max_results = max(4, min(12, max_results))
        field_mask = (
            "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress,"
            "places.location,places.primaryType,places.types,places.websiteUri"
        )
        headers = {"Content-Type": "application/json", "X-Goog-Api-Key": self.places_api_key, "X-Goog-FieldMask": field_mask}
        endpoint = "https://places.googleapis.com/v1/places:searchNearby"
        primary_type = str((target_place or {}).get("place_primary_type") or "").strip().lower()
        generic_place_types = {"", "establishment", "point_of_interest", "service", "business", "organization", "store", "professional_service", "local_business"}
        search_query = self._competitor_search_query(target_place, architecture_profile)
        body: Dict[str, Any] = {
            "maxResultCount": max_results,
            "rankPreference": "POPULARITY",
            "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius}},
        }
        # Nearby type filtering is excellent when Google exposes a specific type, but generic
        # types such as ``service`` create noisy peer sets and are intentionally not used.
        if primary_type and primary_type not in generic_place_types:
            body["includedPrimaryTypes"] = [primary_type]

        nearby_places: List[Dict[str, Any]] = []
        nearby_status = "not_attempted"
        nearby_retry_status = "not_needed"
        nearby_error_detail = ""
        try:
            response = self.session.post(endpoint, json=body, headers=headers, timeout=(4, 12))
            nearby_status = f"http_{response.status_code}"
            if response.status_code == 200:
                nearby_places = response.json().get("places") or []
            else:
                try:
                    nearby_error_detail = str((response.json().get("error") or {}).get("message") or "")[:240]
                except Exception:
                    nearby_error_detail = str(response.text or "")[:240]
                # Google type tables evolve and a Places primaryType can occasionally be returned
                # even when it is not accepted as a Nearby filter in the caller's API version.
                # Retry once without the type restriction before falling back to Text Search.
                if response.status_code == 400 and "includedPrimaryTypes" in body:
                    retry_body = dict(body)
                    retry_body.pop("includedPrimaryTypes", None)
                    retry = self.session.post(endpoint, json=retry_body, headers=headers, timeout=(4, 12))
                    nearby_retry_status = f"http_{retry.status_code}"
                    if retry.status_code == 200:
                        nearby_places = retry.json().get("places") or []
                print(f"[Hybrid Scanner] Nearby competitor search HTTP {response.status_code}; evaluating retry/text fallback")
        except Exception as exc:
            nearby_status = "error"
            nearby_error_detail = str(exc)[:240]
            print(f"[Hybrid Scanner] Nearby competitor search error: {exc}")

        # Text search is used when Nearby is empty, the Google type is generic, too few candidates
        # expose websites, or strong offering language exists that can make the query materially
        # more specific than the broad journey.  Results are merged and deduplicated.
        text_places: List[Dict[str, Any]] = []
        text_status = "not_needed"
        nearby_websites = sum(bool(str(x.get("websiteUri") or "")) for x in nearby_places)
        strong_offering_query = bool(search_query and search_query != self._competitor_search_text(journey_model))
        need_text = bool(
            not nearby_places
            or primary_type in generic_place_types
            or nearby_websites < 3
            or (strong_offering_query and len(nearby_places) < max_results)
        )
        if need_text:
            try:
                text_endpoint = "https://places.googleapis.com/v1/places:searchText"
                text_body = {
                    "textQuery": search_query or self._competitor_search_text(journey_model),
                    "pageSize": max_results,
                    "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius}},
                }
                response = self.session.post(text_endpoint, json=text_body, headers=headers, timeout=(4, 12))
                text_status = f"http_{response.status_code}"
                if response.status_code == 200:
                    text_places = response.json().get("places") or []
            except Exception as exc:
                text_status = "error"
                print(f"[Hybrid Scanner] Text competitor search error: {exc}")

        # Specific text results are preferred when the target type is generic; otherwise Nearby
        # remains the primary source and text results merely improve coverage.
        combined_places = (text_places + nearby_places) if primary_type in generic_place_types else (nearby_places + text_places)
        places: List[Dict[str, Any]] = []
        seen_place_keys: set[str] = set()
        for place in combined_places:
            marker = self._places_candidate_key(place)
            if not marker or marker in seen_place_keys:
                continue
            seen_place_keys.add(marker)
            places.append(place)
            if len(places) >= max_results:
                break

        search_strategy = "nearby+specific_text" if nearby_places and text_places else ("specific_text" if text_places else "nearby")
        target_id = str((target_place or {}).get("place_id") or "")
        target_host = self._host_from_url((target_place or {}).get("place_website_uri") or target_scan.get("domain") or "")
        competitors: List[Dict[str, Any]] = []
        for place in places:
            place_id = str(place.get("id") or "")
            website = str(place.get("websiteUri") or "")
            website_host = self._host_from_url(website)
            if target_id and place_id == target_id:
                continue
            if target_host and website_host and (website_host == target_host or website_host.endswith("." + target_host) or target_host.endswith("." + website_host)):
                continue
            competitors.append({
                "place_id": place_id,
                "name": str((place.get("displayName") or {}).get("text") or "").strip(),
                "rating": self._to_float(place.get("rating")),
                "review_count": self._to_int(place.get("userRatingCount"), 0),
                "website": website,
                "address": str(place.get("formattedAddress") or ""),
                "primary_type": str(place.get("primaryType") or ""),
                "place_types": list(place.get("types") or []),
                "website_probed": False,
                "commercial_score": None,
                "benchmark_eligible": False,
            })
            if len(competitors) >= max_results - 1:
                break

        if not competitors:
            return {**base, "reason": "No nearby businesses remained after excluding the target", "radius_meters": int(radius)}

        probe_indices = [i for i, comp in enumerate(competitors) if comp.get("website")][:5]
        if probe_indices:
            with ThreadPoolExecutor(max_workers=min(4, len(probe_indices))) as pool:
                futures = {pool.submit(self._probe_competitor_website, competitors[i], architecture_profile): i for i in probe_indices}
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        competitors[i].update(future.result() or {})
                    except Exception as exc:
                        competitors[i]["probe_reason"] = str(exc)

        target_commercial = self._competitor_commercial_score(target_scan, journey_model, context_tags)

        # First decide commercial comparability. Reputation context may include a wider nearby set,
        # but the combined Local Benchmark must use one consistent peer set for *every* component.
        reputation_reviews = [self._to_int(target_place.get("google_review_count"), 0) or 0] + [int(c.get("review_count") or 0) for c in competitors]
        reputation_max_reviews = max(1, max(reputation_reviews))
        for comp in competitors:
            comp["presence_index"] = self._local_index(comp.get("rating"), comp.get("review_count"), None, reputation_max_reviews)
            relevance, eligible, reason = self._competitor_relevance_score(architecture_profile, target_place, comp)
            comp["benchmark_relevance_score"] = relevance
            comp["benchmark_eligible"] = bool(eligible and comp.get("website_probed") and comp.get("commercial_score") is not None)
            comp["benchmark_exclusion_reason"] = "" if comp["benchmark_eligible"] else (reason if comp.get("website_probed") else str(comp.get("probe_reason") or "Website not successfully probed"))
            comp["local_index"] = None

        scored = [c for c in competitors if c.get("benchmark_eligible")]
        comparable_reviews = [self._to_int(target_place.get("google_review_count"), 0) or 0] + [int(c.get("review_count") or 0) for c in scored]
        benchmark_max_reviews = max(1, max(comparable_reviews))
        target_index = self._local_index(
            self._to_float(target_place.get("google_rating")),
            self._to_int(target_place.get("google_review_count"), 0),
            target_commercial,
            benchmark_max_reviews,
        )
        for comp in scored:
            comp["local_index"] = self._local_index(comp.get("rating"), comp.get("review_count"), comp.get("commercial_score"), benchmark_max_reviews)

        scored = [c for c in scored if c.get("local_index") is not None]
        ratings = [float(c["rating"]) for c in scored if c.get("rating") is not None]
        reviews = [int(c.get("review_count") or 0) for c in scored]
        commercial = [float(c["commercial_score"]) for c in scored if c.get("commercial_score") is not None]
        reputation_ratings = [float(c["rating"]) for c in competitors if c.get("rating") is not None]
        reputation_review_counts = [int(c.get("review_count") or 0) for c in competitors]
        website_url_count = sum(bool(c.get("website")) for c in competitors)
        website_probe_success_count = sum(bool(c.get("website_probed")) for c in competitors)
        avg_index = round(sum(float(c["local_index"]) for c in scored) / len(scored), 1) if scored else None
        top = max(scored, key=lambda c: float(c["local_index"])) if scored else None
        top_index = self._to_float((top or {}).get("local_index"))
        available = bool(target_index is not None and avg_index is not None and len(scored) >= 3)
        result = {
            **base,
            "available": available,
            "status": "measured" if available else "partial",
            "reason": "" if available else "Fewer than 3 journey/context-relevant competitors had enough public website evidence for a stable benchmark",
            "radius_meters": int(radius),
            "competitor_search_strategy": search_strategy,
            "competitor_search_query": search_query,
            "target_google_primary_type": primary_type or None,
            "nearby_search_status": nearby_status,
            "nearby_retry_status": nearby_retry_status,
            "nearby_error_detail": nearby_error_detail or None,
            "text_search_status": text_status,
            "target_place_name": target_place.get("place_display_name") or "",
            "target_address": str(target_place.get("place_formatted_address") or ""),
            "target_google_rating": self._to_float(target_place.get("google_rating")),
            "target_google_review_count": self._to_int(target_place.get("google_review_count"), 0),
            "target_commercial_score": target_commercial,
            "target_local_index": target_index,
            "sample_count": len(scored),
            "discovered_count": len(competitors),
            "places_sample_count": len(competitors),
            "commercial_benchmark_sample_count": len(scored),
            "website_url_coverage_pct": round(100.0 * website_url_count / len(competitors), 1) if competitors else None,
            "website_probe_success_count": website_probe_success_count,
            "website_coverage_pct": round(100.0 * website_probe_success_count / len(competitors), 1) if competitors else None,
            "local_avg_index": avg_index,
            "local_top_index": top_index,
            "gap_to_local_avg": round(max(0.0, float(avg_index) - float(target_index)), 1) if available else None,
            "gap_to_local_leader": round(max(0.0, float(top_index) - float(target_index)), 1) if available and top_index is not None else None,
            "target_vs_local_avg_delta": round(float(target_index) - float(avg_index), 1) if available else None,
            "local_avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "local_top_rating": max(ratings) if ratings else None,
            "local_avg_review_count": round(sum(reviews) / len(reviews)) if reviews else None,
            "local_top_review_count": max(reviews) if reviews else None,
            "reputation_context_sample_count": len(competitors),
            "reputation_context_avg_rating": round(sum(reputation_ratings) / len(reputation_ratings), 2) if reputation_ratings else None,
            "reputation_context_avg_review_count": round(sum(reputation_review_counts) / len(reputation_review_counts)) if reputation_review_counts else None,
            "local_avg_commercial_score": round(sum(commercial) / len(commercial), 1) if commercial else None,
            "local_top_commercial_score": max(commercial) if commercial else None,
            "local_leader_name": (top or {}).get("name") or "",
            "competitors": competitors,
            "method_note": (
                "The target Google Place must be tied confidently to the scanned domain before benchmarking. Nearby candidates are then filtered by the same inferred customer-journey model plus context/action relevance. "
                "Only competitors with a successfully probed public website and relevance score >=65 enter the combined Local Benchmark Index. Rating, review-count and commercial averages shown as local benchmark values all use that same eligible peer set. Blocked or mismatched businesses remain broader reputation context only. "
                "The benchmark is contextual and does not directly change Revenue Readiness."
            ),
        }
        return result

    def _extract_static_html_evidence(self, html_text: str, url: str, verified: bool) -> Dict[str, Any]:
        """Extract evidence from the HTTP HTML so a browser-side error does not blank the audit."""
        results = self._empty_dom_meta()
        if not verified or not html_text or len(html_text.strip()) < 80:
            return results

        probe = _StaticHTMLProbe()
        try:
            probe.feed(html_text)
            probe.close()
        except Exception as exc:
            results["static_html_error"] = str(exc)
            return results

        visible_text = " ".join(probe.visible_parts)
        text_lower = visible_text.lower()
        html_lower = html_text.lower()
        title = " ".join(probe.title_parts).strip()
        meta_description = ""
        viewport_content = ""
        for meta in probe.metas:
            if meta.get("name", "").lower() == "description" and not meta_description:
                meta_description = meta.get("content", "").strip()
            if meta.get("name", "").lower() == "viewport" and not viewport_content:
                viewport_content = meta.get("content", "").strip()

        h1_tags = [" ".join(parts).strip() for parts in probe.h1_parts if " ".join(parts).strip()]
        schema_types = self._extract_static_schema_types(probe.schema_scripts)
        links = []
        raw_internal_link_inputs = []
        for action in probe.actions:
            href = urllib.parse.urljoin(url, str(action.get("href") or ""))
            text = str(action.get("text") or "")
            raw_internal_link_inputs.append({"href": href, "text": text})
            links.append({"href": href.lower(), "text": text.lower()})
        for link in probe.links:
            href = urllib.parse.urljoin(url, str(link.get("href") or ""))
            raw_internal_link_inputs.append({"href": href, "text": ""})
            links.append({"href": href.lower(), "text": ""})

        detected_phones = sorted(set(match.group(0).strip() for match in PHONE_RE.finditer(visible_text)))
        schema_phone = bool(re.search(r'"telephone"\s*:', "\n".join(probe.schema_scripts), re.I))
        tel_present = any(str(item.get("href") or "").lower().startswith("tel:") for item in probe.actions)
        whatsapp_present = any(
            "wa.me" in str(item.get("href") or "").lower()
            or "whatsapp.com" in str(item.get("href") or "").lower()
            for item in probe.actions
        )

        image_count = len(probe.images)
        missing_alt = 0
        with_alt = 0
        lazy_count = 0
        same_origin_images = 0
        origin = urllib.parse.urlparse(url).netloc.lower()
        for image in probe.images:
            alt_present = "alt" in image
            aria = image.get("aria-label") or image.get("aria-labelledby")
            role = image.get("role", "").lower()
            if alt_present or aria or role in {"presentation", "none"}:
                with_alt += 1
            else:
                missing_alt += 1
            if image.get("loading", "").lower() == "lazy":
                lazy_count += 1
            src = image.get("src", "")
            if src:
                src_host = urllib.parse.urlparse(urllib.parse.urljoin(url, src)).netloc.lower()
                if src_host == origin and not re.search(r"logo|icon|favicon|sprite", src, re.I):
                    same_origin_images += 1

        form_valid_flags: List[bool] = []
        unlinked_forms = 0
        form_field_counts: List[int] = []
        form_required_counts: List[int] = []
        for form in probe.forms:
            structurally_valid = bool(str(form.get("action") or "").strip()) or bool(
                form.get("has_inputs") and form.get("has_submit")
            )
            form_valid_flags.append(structurally_valid)
            form_field_counts.append(self._to_int(form.get("field_count"), 0) or 0)
            form_required_counts.append(self._to_int(form.get("required_field_count"), 0) or 0)
            if not structurally_valid:
                unlinked_forms += 1

        action_types = sorted(
            {
                self._classify_action_text(str(item.get("text") or ""), str(item.get("href") or ""))
                for item in probe.actions
            }
            - {"other"}
        )

        internal_links = self._same_origin_internal_links(url, raw_internal_link_inputs)
        booking_provider_links = self._extract_booking_provider_links(url, probe.actions)
        conversion_error_signals = self._detect_conversion_error_signals(visible_text, html_lower, url)
        content_signals = self._static_content_signals(visible_text, links, schema_types, probe)
        ai_flags = {
            "tailwind_classes": len(re.findall(r'\b(?:flex|grid|bg-[\w-]+|text-[\w-]+|rounded|shadow)\b', html_text)),
            "shadcn_markers": "data-slot=" in html_lower or "shadcn" in html_lower,
            "lucide_icons": html_lower.count("lucide"),
            "generic_headline": bool(
                re.search(
                    r"empowering.*business|next-gen|unlock.*potential|transform.*digital|innovative solutions|streamline.*workflow|leverage.*power|cutting-edge|seamless.*experience",
                    " ".join(h1_tags).lower(),
                )
            ),
            "unlinked_forms": unlinked_forms,
            "has_custom_photos": same_origin_images > 0,
            "has_retargeting_pixel": False,
        }

        measurement_platforms = self._detect_measurement_platforms(html_lower)
        has_ga4 = "Google Analytics / GTM" in measurement_platforms
        has_meta_pixel = "Meta Pixel" in measurement_platforms
        has_clarity = "Microsoft Clarity" in measurement_platforms
        has_hotjar = "Hotjar" in measurement_platforms
        has_other_measurement = bool(set(measurement_platforms) - {"Google Analytics / GTM", "Meta Pixel", "Microsoft Clarity", "Hotjar"})
        retargeting = has_meta_pixel or any(
            marker in html_lower for marker in ("googleadservices.com/pagead/conversion", "doubleclick.net", "aw-")
        )
        ai_flags["has_retargeting_pixel"] = retargeting
        ai_score, ai_status = self._calculate_template_pattern_index(visible_text, ai_flags)
        cms, cms_confidence = self._detect_cms_static(html_lower, probe.generator)

        canonical_present = any("canonical" in str(link.get("rel", "")).lower() and bool(link.get("href")) for link in probe.links)
        favicon_present = any(
            "icon" in str(link.get("rel", "")).lower() and bool(link.get("href")) for link in probe.links
        )

        results.update(
            {
                "static_html_verified": True,
                "static_html_error": "",
                "metadata_evidence_status": "verified",
                "image_evidence_status": "verified",
                "tracking_evidence_status": "verified",
                "form_evidence_status": "verified",
                "technical_evidence_status": "verified",
                "content_signal_status": "verified",
                "title": title,
                "meta_description": meta_description,
                "page_text": visible_text,
                "visible_word_count": len(re.findall(r"\b\w+[\w'’-]*\b", visible_text)),
                "page_html_length": len(html_text),
                "page_content_len": len(html_text),
                "h1_tags": h1_tags,
                "h1_dom_count": None,
                "h1_dom_text": [],
                "h1_source_count": len(h1_tags),
                "h1_status": "present" if h1_tags else "unknown",
                "image_count": image_count,
                "total_images": image_count,
                "missing_alt_images": missing_alt,
                "images_with_alt": with_alt,
                "lazy_image_count": lazy_count,
                "lazy_loading_status": "NOT_APPLICABLE" if image_count == 0 else ("PASS" if lazy_count > 0 else "UNKNOWN"),
                "custom_photography_signal": same_origin_images > 0,
                "custom_photography_status": "UNKNOWN",
                "favicon_present": favicon_present,
                "html_lang_present": bool(probe.html_lang.strip()),
                "canonical_present": canonical_present,
                "mobile_viewport_configured": bool(viewport_content),
                "schema_types": schema_types,
                "schema_present": bool(schema_types or probe.schema_scripts or re.search(r"\bitemscope\b|\btypeof=", html_lower)),
                "has_clarity": has_clarity,
                "has_hotjar": has_hotjar,
                "has_ga4": has_ga4,
                "has_meta_pixel": has_meta_pixel,
                "has_other_measurement": has_other_measurement,
                "measurement_layer_present": bool(measurement_platforms),
                "measurement_platforms": measurement_platforms,
                "retargeting_pixel_installed": retargeting,
                "phone_number_visible": bool(detected_phones) or schema_phone,
                "phone_visibility_status": "verified",
                "detected_phone_numbers": detected_phones,
                "click_to_call_present": tel_present,
                "click_to_call_status": "verified",
                "whatsapp_present": whatsapp_present,
                "live_chat_present": self._detect_live_chat(html_lower, visible_text),
                "forms_present": bool(probe.forms),
                "form_action_valid": all(form_valid_flags) if form_valid_flags else None,
                "form_field_counts": form_field_counts,
                "form_required_field_counts": form_required_counts,
                "form_min_field_count": min(form_field_counts) if form_field_counts else None,
                "form_max_field_count": max(form_field_counts) if form_field_counts else None,
                "form_max_required_field_count": max(form_required_counts) if form_required_counts else None,
                "checkout_form_field_count": (
                    max(form_field_counts)
                    if form_field_counts and content_signals.get("checkout_context_detected")
                    else None
                ),
                "form_functional_status": "UNKNOWN" if probe.forms else "NOT_APPLICABLE",
                "form_payload_fired": False,
                "mobile_primary_cta_present": bool(action_types),
                # Static HTML cannot prove persistence/visibility after scrolling.
                "mobile_sticky_cta_present": False,
                "mobile_cta_visible": False,
                "mobile_cta_status": "unknown",
                "mobile_cta_types": action_types,
                "mobile_cta_type": action_types[0] if action_types else "unknown",
                "add_to_cart_visible": any(t in action_types for t in ("add_to_cart", "buy")),
                "order_online_present": "order" in action_types,
                "reservation_present": "reserve" in action_types,
                "booking_action_present": "book" in action_types,
                "directions_present": "directions" in action_types,
                "internal_links": internal_links,
                "booking_provider_links": booking_provider_links,
                "conversion_error_signals": conversion_error_signals,
                "conversion_path_error_detected": bool(conversion_error_signals),
                "ai_flags": ai_flags,
                "ai_spectrum_pct": ai_score,
                "ai_spectrum_status": ai_status,
                "cms_platform": cms,
                "cms_confidence": cms_confidence,
                **content_signals,
            }
        )
        results["has_qualitative_analytics"] = bool(results["has_clarity"] or results["has_hotjar"])
        results["measurement_layer_present"] = bool(results.get("measurement_platforms"))
        return results

    @staticmethod
    def _extract_static_schema_types(raw_scripts: List[str]) -> List[str]:
        found: List[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                item_type = value.get("@type")
                if isinstance(item_type, str):
                    found.append(item_type)
                elif isinstance(item_type, list):
                    found.extend(str(x) for x in item_type)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        for raw in raw_scripts:
            try:
                walk(json.loads(raw))
            except Exception:
                continue
        return sorted(set(item.strip() for item in found if str(item).strip()))

    @staticmethod
    def _classify_action_text(text: str, href: str) -> str:
        """Classify an actual customer action conservatively.

        Earlier versions searched loose substrings across link text + href, which could classify
        ``Facebook`` as ``book`` or a legal ``removal-order`` page as an ecommerce order CTA.
        This version uses word boundaries, intent phrases and path-segment evidence.
        """
        label = " ".join(str(text or "").strip().lower().split())
        raw_href = str(href or "").strip().lower()
        try:
            parsed = urllib.parse.urlparse(raw_href)
            path = urllib.parse.unquote(parsed.path or "").lower()
        except Exception:
            path = raw_href
        href_tokens = " ".join(x for x in re.split(r"[/_?&=#.-]+", path) if x)
        combined = f"{label} {href_tokens}".strip()

        if raw_href.startswith("tel:") or re.search(r"\bcall(?:\s+(?:now|us|today|restaurant))?\b", label):
            return "call"
        if re.search(r"\b(?:directions?|get directions)\b", label) or "maps.google" in raw_href or "google.com/maps" in raw_href:
            return "directions"
        if re.search(r"\badd\s+to\s+(?:cart|bag)\b", combined):
            return "add_to_cart"
        if re.search(r"\b(?:checkout|buy\s+now|purchase\s+now|complete\s+purchase)\b", label) or re.search(r"(?:^|\s)checkout(?:\s|$)", href_tokens):
            return "buy"
        if re.search(r"\b(?:order\s+(?:online|now|pickup|delivery)|start\s+(?:an?\s+)?order|place\s+(?:an?\s+)?order)\b", label) or re.search(r"(?:^|\s)(?:order-online|online-order)(?:\s|$)", path.replace("/", " ")):
            return "order"
        # Hospitality booking language is distinct from appointment booking.
        if re.search(r"\b(?:reserve(?:\s+(?:now|a\s+table|a\s+room|a\s+spot))?|make\s+(?:a\s+)?reservation|book\s+(?:a\s+)?(?:table|room|venue|tour|charter|cruise))\b", label) or re.search(r"(?:^|\s)reservations?(?:\s|$)", href_tokens):
            return "reserve"
        if re.search(r"\b(?:book\s+(?:a\s+)?demo|request\s+(?:a\s+)?demo|schedule\s+(?:a\s+)?demo)\b", label):
            return "demo"
        if re.search(r"\b(?:book(?:\s+(?:now|online|appointment|consultation|a\s+consultation))?|schedule\s+(?:an?\s+)?(?:appointment|consultation))\b", label) or re.search(r"(?:^|\s)(?:book|booking|appointment|appointments)(?:\s|$)", href_tokens):
            return "book"
        if re.search(r"\b(?:get|request|receive)\s+(?:a\s+)?(?:free\s+)?quote\b|\b(?:free\s+)?estimate\b", label) or re.search(r"(?:^|\s)(?:quote|estimate)(?:\s|$)", href_tokens):
            return "quote"
        if re.search(r"\b(?:start\s+(?:a\s+)?(?:free\s+)?trial|free\s+trial|try\s+free)\b", label):
            return "trial"
        if re.search(r"\b(?:subscribe|join\s+(?:the\s+)?(?:list|newsletter|community)|sign\s+up\s+for\s+(?:the\s+)?newsletter)\b", label):
            return "subscribe"
        if re.search(r"\b(?:contact(?:\s+us)?|get\s+in\s+touch|send\s+(?:us\s+)?a\s+message)\b", label) or re.search(r"(?:^|\s)contact(?:\s|$)", href_tokens):
            return "contact"
        if re.search(r"\b(?:live\s+chat|chat\s+(?:now|with\s+us)|whatsapp)\b", label) or "wa.me" in raw_href or "whatsapp.com" in raw_href:
            return "chat"
        return "other"

    @staticmethod
    def _same_origin_internal_links(base_url: str, links: List[Dict[str, str]]) -> List[str]:
        parsed = urllib.parse.urlparse(base_url)
        origin_host = parsed.netloc.lower().split(":")[0]
        out: List[str] = []
        seen = set()
        blocked_ext = re.compile(r"\.(?:jpg|jpeg|png|gif|webp|svg|pdf|zip|css|js|xml|ico|mp4|mp3|woff2?)(?:$|\?)", re.I)
        for item in links or []:
            raw = str(item.get("href") or "").strip()
            if not raw or raw.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue
            absolute = urllib.parse.urljoin(base_url, raw)
            parts = urllib.parse.urlparse(absolute)
            host = parts.netloc.lower().split(":")[0]
            if parts.scheme not in {"http", "https"} or host != origin_host:
                continue
            clean = urllib.parse.urlunparse((parts.scheme, parts.netloc, parts.path or "/", "", "", ""))
            if blocked_ext.search(clean) or re.search(r"/(?:wp-admin|admin|logout|signout)(?:/|$)", parts.path, re.I):
                continue
            if clean not in seen:
                seen.add(clean)
                out.append(clean)
            if len(out) >= 120:
                break
        return out

    @staticmethod
    def _detect_credential_signals(visible_text: str, links: Optional[List[Dict[str, str]]] = None, schema_types: Optional[List[str]] = None) -> List[str]:
        text = str(visible_text or "")
        lower = text.lower()
        patterns = (
            ("general_certification", r"\b(?:licensed|insured|bonded|certified|accredited|bbb accredited|trustpilot)\b"),
            ("healthcare_registration", r"\b(?:registered physiotherapists?|registered massage therapists?|registered massage therapy|registered nurse|nurse practitioner|licensed practical nurse|occupational therapist|speech[- ]language pathologist|registered clinical counsellor|registered psychologist|registered dietitian)\b"),
            ("medical_credentials", r"\b(?:medical director|board[- ]certified|licensed physician|physician|doctor of medicine|nurse injector|md\s*,|rn\s*,|np\s*,)\b"),
            ("legal_credentials", r"\b(?:law society|barrister(?:\s+and\s+solicitor)?|solicitor|licensed lawyer|member of the bar|king'?s counsel|queen'?s counsel)\b"),
            ("professional_credentials", r"\b(?:chartered professional accountant|professional engineer|p\.?\s*eng\.?|architect\s+aibc|aibc\b|cpa\b|pmp\b)\b"),
            ("trade_credentials", r"\b(?:red seal|worksafebc|work\s*safe\s*bc|licensed contractor|licensed electrician|licensed plumber)\b"),
            ("security_compliance", r"\b(?:soc\s*2(?:\s*type\s*[12])?|iso\s*27001|pci\s*dss|hipaa\s+compliant|gdpr\s+compliant)\b"),
            ("secure_purchase", r"\b(?:secure checkout|secure payment|256[- ]bit encrypted|pci compliant)\b"),
        )
        found = [name for name, pattern in patterns if re.search(pattern, lower, re.I)]
        # Explicit professional validation/member links are additional evidence, but only when the
        # link text itself describes verification/membership rather than merely naming an association.
        for item in links or []:
            label = f"{item.get('text') or ''} {item.get('href') or ''}".lower()
            if re.search(r"\b(?:verify|verification|registry|member|membership|licen[cs]e)\b", label) and re.search(r"\b(?:college|society|association|board|registry)\b", label):
                found.append("professional_registry_link")
                break
        return sorted(set(found))

    @staticmethod
    def _detect_conversion_error_signals(visible_text: str, html_lower: str, url: str) -> List[Dict[str, Any]]:
        # Customer-facing failures must be visible evidence. Searching arbitrary script/source text can
        # create false positives because libraries often contain dormant error-message strings.
        haystack = str(visible_text or "")[:300_000]
        signals: List[Dict[str, Any]] = []
        for key, pattern, message in CONVERSION_ERROR_PATTERNS:
            match = re.search(pattern, haystack, re.I)
            if not match:
                continue
            context = " ".join(match.group(0).split())[:180]
            signals.append({
                "key": key,
                "url": str(url or ""),
                "message": message,
                "observed_text": context,
                "evidence_surface": "customer_visible_text",
                "confidence": "high",
                "severity": 0.95 if key.startswith("recaptcha_") else 0.85,
            })
        return signals

    @staticmethod
    def _journey_role(url: str) -> str:
        path = urllib.parse.unquote(urllib.parse.urlparse(str(url or "")).path).lower().strip("/")
        tokens = [token for token in re.split(r"[/_.-]+", path) if token]
        token_set = set(tokens)
        joined = " ".join(tokens)
        if token_set & {"contact", "enquiry", "inquiry", "quote", "estimate"} or re.search(r"\brequest (?:a )?(?:quote|estimate)\b", joined):
            return "contact_or_lead"
        if token_set & {"book", "booking", "appointment", "appointments", "consultation", "reservation", "reservations", "reserve"}:
            return "booking"
        if token_set & {"cart", "checkout"} or "order online" in joined or "online order" in joined or "place order" in joined:
            return "commerce_conversion"
        if token_set & {"pricing", "plans", "packages", "demo", "trial", "signup"} or "sign up" in joined:
            return "evaluation"
        if token_set & {"about", "team", "staff", "reviews", "testimonials", "portfolio", "projects", "customers"} or "case studies" in joined:
            return "proof"
        # A law firm's /legal-services/ page is not a policy page. Keep policy matching narrow.
        if token_set & {"privacy", "terms", "policy", "cookies", "cookie"} or "terms of service" in joined or "terms and conditions" in joined:
            return "policy"
        return "support"

    def _select_priority_journey_urls(self, base_url: str, candidates: List[str], journey_model: str, limit: int, context_tags: Optional[List[str]] = None) -> List[str]:
        parsed = urllib.parse.urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        model = str(journey_model or "general")
        terms = list(JOURNEY_PAGE_TERMS.get(model, JOURNEY_PAGE_TERMS["general"]))
        tags = {str(x) for x in (context_tags or []) if x}
        if "regulated_high_trust" in tags:
            terms = ["credentials", "team", "privacy"] + terms
        if "hospitality_event" in tags:
            terms = ["events", "charter", "cruise", "reservation", "venue", "wedding"] + terms
        if "commerce_payment" in tags:
            terms = ["checkout", "cart", "shipping", "returns"] + terms
        if "enterprise_considered_purchase" in tags:
            terms = ["case-studies", "projects", "customers", "pricing", "solutions"] + terms
        terms = list(dict.fromkeys(terms))

        scored: List[Tuple[float, str]] = []
        seen = set()
        for url in candidates or []:
            if url in seen or url.rstrip("/") == base_url.rstrip("/"):
                continue
            seen.add(url)
            low = urllib.parse.unquote(url).lower()
            score = 0.0
            for idx, term in enumerate(terms):
                if term in low:
                    score += max(2.0, 12.0 - idx * 0.45)
            if any(term in low for term in POLICY_TERMS):
                score += 4.0
            if any(term in low for term in PROOF_TERMS):
                score += 4.0
            role = self._journey_role(url)
            if role in {"contact_or_lead", "booking", "commerce_conversion", "evaluation"}:
                score += 7.5
            elif role == "proof":
                score += 3.0
            elif role == "policy":
                score += 2.0
            if score > 0:
                scored.append((score, url))

        guessed = list(JOURNEY_PAGE_GUESSES.get(model, JOURNEY_PAGE_GUESSES["general"]))
        existing = {url for _, url in scored}
        for idx, path in enumerate(guessed):
            guessed_url = urllib.parse.urljoin(origin + "/", path.lstrip("/"))
            if guessed_url not in existing and guessed_url.rstrip("/") != base_url.rstrip("/"):
                scored.append((3.4 - idx * 0.18, guessed_url))
                existing.add(guessed_url)

        ranked = sorted(scored, key=lambda item: (-item[0], len(item[1]), item[1]))
        ordered = [url for _, url in ranked]
        # Preserve breadth: one conversion/evaluation path, one proof path, one policy path, then fill by relevance.
        selected: List[str] = []
        role_groups = (
            {"contact_or_lead", "booking", "commerce_conversion", "evaluation"},
            {"proof"},
            {"policy"},
        )
        for allowed in role_groups:
            candidate = next((url for url in ordered if url not in selected and self._journey_role(url) in allowed), None)
            if candidate and len(selected) < limit:
                selected.append(candidate)
        for url in ordered:
            if len(selected) >= limit:
                break
            if url not in selected:
                selected.append(url)
        return selected

    def _scan_priority_journey_pages(self, base_url: str, candidates: List[str], journey_model: str, context_tags: Optional[List[str]] = None) -> Dict[str, Any]:
        raw_limit = self._to_int(os.environ.get("TRILLOKA_JOURNEY_MAX_PAGES"), 5) or 5
        limit = max(2, min(6, raw_limit))
        urls = self._select_priority_journey_urls(base_url, candidates, journey_model, limit, context_tags)
        pages: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        credential_types: List[str] = []
        text_samples: List[str] = []
        booking_provider_links: List[Dict[str, Any]] = []
        aggregate = {
            "reviews_visible": False,
            "social_proof_present": False,
            "trust_badges_present": False,
            "credential_signals_present": False,
            "privacy_policy_linked": False,
            "terms_linked": False,
            "about_team_linked": False,
            "faq_present": False,
            "case_studies_portfolio_present": False,
            "return_policy_linked": False,
            "shipping_info_linked": False,
            "pricing_linked": False,
            "blog_present": False,
        }
        for url in urls:
            try:
                response = self.safe_http.get(url, timeout=(3, 7), allow_redirects=True, max_bytes=800_000)
                status = int(response.status_code)
                if not (200 <= status < 400):
                    role = self._journey_role(url)
                    pages.append({"url": url, "status_code": status, "role": role, "verified": False})
                    if (status in {404, 410} or status >= 500) and role in {"contact_or_lead", "booking", "commerce_conversion", "evaluation"}:
                        errors.append({
                            "key": "conversion_destination_http_error",
                            "url": str(url),
                            "message": f"A customer conversion destination returned HTTP {status}.",
                            "observed_text": f"HTTP {status}",
                            "evidence_surface": "http_destination_status",
                            "confidence": "high",
                            "severity": 0.90,
                        })
                    continue
                html_text = (response.text or "")[:750_000]
                evidence = self._extract_static_html_evidence(html_text, response.url, verified=True)
                page_errors = list(evidence.get("conversion_error_signals") or [])
                errors.extend(page_errors)
                page_credential_types = list(evidence.get("credential_signal_types") or [])
                credential_types.extend(page_credential_types)
                booking_provider_links.extend(list(evidence.get("booking_provider_links") or []))
                role = self._journey_role(response.url)
                for key in aggregate:
                    aggregate[key] = bool(aggregate[key] or evidence.get(key))
                path_lower = urllib.parse.urlparse(response.url).path.lower()
                if role == "policy":
                    if "privacy" in path_lower:
                        aggregate["privacy_policy_linked"] = True
                    if "terms" in path_lower or "legal" in path_lower:
                        aggregate["terms_linked"] = True
                if role == "proof":
                    if any(token in path_lower for token in ("about", "team", "staff")):
                        aggregate["about_team_linked"] = True
                    if any(token in path_lower for token in ("review", "testimonial")):
                        aggregate["reviews_visible"] = True
                        aggregate["social_proof_present"] = True
                    if any(token in path_lower for token in ("case-stud", "case_stud", "portfolio", "work", "project", "customer")):
                        aggregate["case_studies_portfolio_present"] = True
                        aggregate["social_proof_present"] = True
                if page_credential_types:
                    aggregate["credential_signals_present"] = True
                    aggregate["trust_badges_present"] = True
                sample = str(evidence.get("page_text") or "")[:5000]
                # Policy/legal boilerplate is still scanned for policy evidence, but is deliberately
                # excluded from journey/context language inference ("in the event", "we reserve", etc.).
                if sample and role != "policy":
                    text_samples.append(sample)
                pages.append({
                    "url": response.url,
                    "status_code": status,
                    "role": role,
                    "verified": True,
                    "forms_present": bool(evidence.get("forms_present")),
                    "cta_types": evidence.get("mobile_cta_types") or [],
                    "conversion_error_signals": page_errors,
                    "credential_signal_types": page_credential_types,
                    "reviews_visible": bool(evidence.get("reviews_visible")),
                    "privacy_policy_linked": bool(evidence.get("privacy_policy_linked")),
                    "terms_linked": bool(evidence.get("terms_linked")),
                })
            except Exception as exc:
                pages.append({"url": url, "status_code": None, "role": self._journey_role(url), "verified": False, "error": str(exc)[:220]})

        verified_count = sum(1 for page in pages if page.get("verified"))
        # The extra Chromium page is the highest-ranked verified conversion/evaluation page.
        browser_candidate = next((page.get("url") for page in pages if page.get("verified") and page.get("role") in {"contact_or_lead", "booking", "commerce_conversion", "evaluation"}), None)
        return {
            "journey_evidence_status": "verified" if verified_count else "unavailable",
            "journey_pages_scanned": pages,
            "journey_pages_verified": verified_count,
            "journey_page_limit": limit,
            "journey_error_signals": errors,
            "conversion_path_error_detected": bool(errors),
            "credential_signal_types": sorted(set(credential_types)),
            "booking_provider_links": self._dedupe_booking_provider_links(booking_provider_links),
            "browser_journey_candidate_url": browser_candidate,
            "journey_text_sample": "\n".join(text_samples)[:18000],
            **aggregate,
        }

    @staticmethod
    def _merge_journey_evidence(target: Dict[str, Any], journey: Dict[str, Any]) -> None:
        target["journey_evidence_status"] = journey.get("journey_evidence_status", "unavailable")
        target["journey_pages_scanned"] = journey.get("journey_pages_scanned") or []
        target["journey_pages_verified"] = journey.get("journey_pages_verified") or 0
        target["journey_page_limit"] = journey.get("journey_page_limit") or 0
        target["journey_text_sample"] = journey.get("journey_text_sample") or ""
        target["browser_journey_candidate_url"] = journey.get("browser_journey_candidate_url")
        target["booking_provider_links"] = HybridScanner._dedupe_booking_provider_links(
            list(target.get("booking_provider_links") or []) + list(journey.get("booking_provider_links") or [])
        )
        existing_errors = list(target.get("conversion_error_signals") or [])
        journey_errors = list(journey.get("journey_error_signals") or [])
        dedup_errors = []
        seen = set()
        for item in existing_errors + journey_errors:
            marker = (str(item.get("key") or ""), str(item.get("url") or ""), str(item.get("observed_text") or ""))
            if marker not in seen:
                seen.add(marker)
                dedup_errors.append(item)
        target["conversion_error_signals"] = dedup_errors
        target["conversion_path_error_detected"] = bool(dedup_errors)
        target["credential_signal_types"] = sorted(set(
            list(target.get("credential_signal_types") or []) + list(journey.get("credential_signal_types") or [])
        ))
        target["credential_signals_present"] = bool(
            target.get("credential_signals_present") or journey.get("credential_signals_present") or target["credential_signal_types"]
        )
        # Cross-page positives are monotonic. A missing signal on a secondary page never erases a
        # positive already verified on the homepage.
        for key in (
            "reviews_visible", "social_proof_present", "trust_badges_present",
            "privacy_policy_linked", "terms_linked", "about_team_linked", "faq_present",
            "case_studies_portfolio_present", "return_policy_linked", "shipping_info_linked",
            "pricing_linked", "blog_present",
        ):
            if journey.get(key) is True:
                target[key] = True
        if target.get("credential_signals_present"):
            target["trust_badges_present"] = True
        target["social_proof_present"] = bool(
            target.get("reviews_visible") or target.get("trust_badges_present") or target.get("case_studies_portfolio_present") or target.get("social_proof_present")
        )
        target["privacy_terms_linked"] = bool(target.get("privacy_policy_linked") and target.get("terms_linked"))

    @staticmethod
    def _utc_now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def _safe_evidence_url(url: str) -> str:
        try:
            parts = urllib.parse.urlparse(str(url or ""))
            host = parts.hostname or ""
            port = f":{parts.port}" if parts.port else ""
            return urllib.parse.urlunparse((parts.scheme, host + port, parts.path or "/", "", "", ""))
        except Exception:
            return str(url or "")[:500]

    @staticmethod
    def _booking_provider_for_host(host: str) -> Optional[str]:
        normalized = str(host or "").lower().split(":")[0].strip(".")
        for provider, domains in BOOKING_PROVIDER_HOSTS.items():
            if any(normalized == domain or normalized.endswith("." + domain) for domain in domains):
                return provider
        return None

    @classmethod
    def _extract_booking_provider_links(cls, base_url: str, links: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        for item in links or []:
            raw = str(item.get("href") or "").strip()
            if not raw:
                continue
            absolute = urllib.parse.urljoin(base_url, raw)
            parts = urllib.parse.urlparse(absolute)
            if parts.scheme not in {"http", "https"}:
                continue
            provider = cls._booking_provider_for_host(parts.hostname or "")
            if not provider:
                continue
            label = str(item.get("text") or "").strip()[:160]
            found.append({
                "provider": provider,
                "url": absolute,
                "display_url": cls._safe_evidence_url(absolute),
                "label": label,
                "action_type": cls._classify_action_text(label, absolute),
            })
        return cls._dedupe_booking_provider_links(found)

    @staticmethod
    def _dedupe_booking_provider_links(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen = set()
        for item in items or []:
            if not isinstance(item, dict):
                continue
            key = (str(item.get("provider") or ""), str(item.get("url") or ""))
            if not key[1] or key in seen:
                continue
            seen.add(key)
            out.append(dict(item))
            if len(out) >= 8:
                break
        return out

    def _check_external_booking_provider_health(self, links: List[Dict[str, Any]]) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for item in self._dedupe_booking_provider_links(links)[:4]:
            provider = str(item.get("provider") or "Booking provider")
            url = str(item.get("url") or "")
            result = {
                "provider": provider,
                "url": self._safe_evidence_url(url),
                "status": "unknown",
                "status_code": None,
                "checked_at": self._utc_now(),
                "method": "passive external booking destination GET",
            }
            try:
                response = self.safe_http.get(url, timeout=(4, 10), allow_redirects=True, max_bytes=250_000)
                code = int(response.status_code)
                result["status_code"] = code
                result["final_url"] = self._safe_evidence_url(response.url)
                if 200 <= code < 400:
                    result["status"] = "reachable"
                elif code in {401, 403, 429}:
                    result["status"] = "restricted_or_rate_limited_unknown"
                elif code in {404, 410} or code >= 500:
                    result["status"] = "broken"
                    errors.append({
                        "key": "external_booking_destination_error",
                        "url": self._safe_evidence_url(url),
                        "message": f"The external {provider} booking destination returned HTTP {code}.",
                        "observed_text": f"{provider} HTTP {code}",
                        "evidence_surface": "external_booking_destination_status",
                        "confidence": "high",
                        "severity": 0.95,
                        "provider": provider,
                    })
                else:
                    result["status"] = "unknown"
            except Exception as exc:
                result["status"] = "network_unknown"
                result["error"] = str(exc)[:180]
            checks.append(result)
        return {
            "checked": bool(checks),
            "checks": checks,
            "broken_count": sum(1 for item in checks if item.get("status") == "broken"),
            "error_signals": errors,
        }

    @staticmethod
    def _merge_browser_journey_evidence(target: Dict[str, Any], browser_probe: Dict[str, Any], url: str) -> None:
        if not isinstance(browser_probe, dict):
            return
        summary = {
            "url": str(url or ""),
            "browser_loaded": bool(browser_probe.get("browser_loaded")),
            "dom_complete": bool(browser_probe.get("dom_complete")),
            "browser_status_code": browser_probe.get("browser_status_code"),
            "forms_present": browser_probe.get("forms_present"),
            "form_action_valid": browser_probe.get("form_action_valid"),
            "cta_types": browser_probe.get("mobile_cta_types") or [],
            "conversion_error_signals": browser_probe.get("conversion_error_signals") or [],
            "booking_provider_links": browser_probe.get("booking_provider_links") or [],
            "evidence_screenshot_mime": browser_probe.get("evidence_screenshot_mime") or "",
            "evidence_screenshot_b64": browser_probe.get("evidence_screenshot_b64") or "",
            "evidence_screenshot_sha256": browser_probe.get("evidence_screenshot_sha256") or "",
        }
        target["browser_journey_probe"] = summary
        target["browser_journey_rendered"] = bool(browser_probe.get("browser_loaded"))
        target["browser_journey_url"] = str(url or "")
        existing = list(target.get("conversion_error_signals") or [])
        extra = list(browser_probe.get("conversion_error_signals") or [])
        merged_errors: List[Dict[str, Any]] = []
        seen = set()
        for item in existing + extra:
            marker = (str(item.get("key") or ""), str(item.get("url") or ""), str(item.get("observed_text") or ""))
            if marker not in seen:
                seen.add(marker)
                merged_errors.append(item)
        target["conversion_error_signals"] = merged_errors
        target["conversion_path_error_detected"] = bool(merged_errors)
        target["booking_provider_links"] = HybridScanner._dedupe_booking_provider_links(
            list(target.get("booking_provider_links") or []) + list(browser_probe.get("booking_provider_links") or [])
        )
        # Positive trust/policy evidence on the rendered journey page can strengthen the aggregate;
        # negative evidence never erases a homepage/cross-page positive.
        for key in (
            "reviews_visible", "social_proof_present", "trust_badges_present", "credential_signals_present",
            "privacy_policy_linked", "terms_linked", "about_team_linked", "case_studies_portfolio_present",
            "return_policy_linked", "shipping_info_linked", "pricing_linked",
        ):
            if browser_probe.get(key) is True:
                target[key] = True
        target["credential_signal_types"] = sorted(set(
            list(target.get("credential_signal_types") or []) + list(browser_probe.get("credential_signal_types") or [])
        ))
        target["privacy_terms_linked"] = bool(target.get("privacy_policy_linked") and target.get("terms_linked"))

    @staticmethod
    def _infer_business_subtype(vertical: str, text: str) -> str:
        # Deprecated compatibility shim. V7 no longer expands industry subtypes.
        return ""

    @staticmethod
    def _primary_conversion_gap_present(data: Dict[str, Any], journey_model: str) -> Optional[bool]:
        if str(data.get("mobile_cta_status") or "unknown").lower() != "verified":
            return None
        model = str(journey_model or "general")
        cta_types = set(str(x) for x in (data.get("mobile_cta_types") or []) if x)
        form_usable = bool(data.get("forms_present") and data.get("form_action_valid") is not False)
        call = bool(data.get("click_to_call_present"))
        expected = architecture_expected_actions(model)
        if model == "direct_purchase":
            return not bool(data.get("add_to_cart_visible") or {"add_to_cart", "buy", "order", "checkout"} & cta_types)
        if model in {"lead_quote", "appointment_consultation", "reservation_event", "demo_sales"}:
            return not bool(form_usable or call or (expected & cta_types))
        if model == "membership_subscription":
            return not bool((expected & cta_types) or form_usable)
        return not bool(data.get("mobile_primary_cta_present") or form_usable or call)

    @classmethod
    def _select_conversion_error_confirmation_url(
        cls,
        signals: List[Dict[str, Any]],
        browser_journey_probe: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Choose the strongest affected customer-journey URL for passive re-confirmation.

        First preference is an already-rendered journey page that carried the same error.
        Otherwise, rank actual contact/booking/checkout paths above homepage/support/proof/policy
        pages. This prevents a duplicated site-wide error string on the homepage or a policy page
        from stealing confirmation away from the revenue-bearing path that originally exposed it.
        """
        usable = [x for x in (signals or []) if isinstance(x, dict) and x.get("url")]
        if not usable:
            return ""

        initial_urls = [str(x.get("url") or "") for x in usable if x.get("url")]
        expected_keys = {str(x.get("key") or "") for x in usable if x.get("key")}
        first_browser = browser_journey_probe if isinstance(browser_journey_probe, dict) else {}
        first_browser_url = str(first_browser.get("url") or "")
        first_browser_keys = {
            str(x.get("key") or "")
            for x in (first_browser.get("conversion_error_signals") or [])
            if isinstance(x, dict) and x.get("key")
        }
        if (
            first_browser_url
            and first_browser_url in initial_urls
            and (not expected_keys or bool(first_browser_keys & expected_keys))
        ):
            return first_browser_url

        role_rank = {
            "contact_or_lead": 0,
            "booking": 0,
            "commerce_conversion": 0,
            "evaluation": 1,
            "support": 2,
            "proof": 3,
            "policy": 5,
        }
        ranked_urls = sorted(
            dict.fromkeys(initial_urls),
            key=lambda u: (
                role_rank.get(cls._journey_role(u), 4),
                len(urllib.parse.urlparse(u).path or "/"),
                u,
            ),
        )
        return ranked_urls[0] if ranked_urls else ""

    async def confirm_high_impact_findings(
        self,
        scan_data: Dict[str, Any],
        audit_results: Dict[str, Any],
        business_type: str = "auto",
        threshold_points: float = 3.5,
    ) -> Dict[str, Any]:
        """Passively re-check findings capable of producing a large deduction.

        The final scorer treats a high-impact candidate as UNKNOWN/unscored unless this phase confirms it.
        Rechecks are bounded and grouped so normal scans do not repeat every collection step.
        """
        packages = (audit_results or {}).get("tiered_remediation_packages") or {}
        raw = [x for x in (packages.get("all_scoring_leaks") or []) if isinstance(x, dict)]
        candidates: List[Dict[str, Any]] = []
        seen_rules = set()
        for leak in raw:
            loss = self._to_float(leak.get("pre_dedupe_penalty"))
            if loss is None:
                loss = self._to_float(leak.get("final_score_loss")) or 0.0
            rule = str(leak.get("rule_key") or "")
            if loss >= float(threshold_points) and rule and rule not in seen_rules:
                seen_rules.add(rule)
                candidates.append(leak)
        candidates = candidates[:8]
        if not candidates:
            return {
                "completed": True,
                "threshold_points": float(threshold_points),
                "candidate_count": 0,
                "results": {},
                "completed_at": self._utc_now(),
            }

        profile_for_confirmation = (audit_results or {}).get("architecture_profile") or (audit_results or {}).get("business_profile") or scan_data.get("architecture_profile") or scan_data.get("business_profile") or {}
        canonical_type = str((profile_for_confirmation or {}).get("journey_model") or (audit_results or {}).get("business_type") or "general")
        base_url = str(scan_data.get("final_url") or scan_data.get("url") or scan_data.get("domain") or "")
        results: Dict[str, Any] = {}

        # One second homepage browser pass can confirm several mobile/form/path candidates at once.
        browser_rules = {"form_architecture", "primary_conversion_path", "click_to_call", "mobile_sticky_cta", "lead_form_friction"}
        need_home_browser = any(str(x.get("rule_key")) in browser_rules for x in candidates)
        second_home: Dict[str, Any] = {}
        if need_home_browser:
            try:
                second_home = await self._run_targeted_playwright(base_url, {}, mode="mobile", capture_evidence=False)
            except Exception as exc:
                second_home = {"browser_loaded": False, "browser_error": str(exc)}

        # Re-render the affected journey page only when a severe customer-path error needs proof.
        error_candidate = next((x for x in candidates if str(x.get("rule_key")) == "conversion_path_error"), None)
        second_error_probe: Dict[str, Any] = {}
        error_url = ""
        if error_candidate:
            signals = [x for x in (((error_candidate.get("evidence") or {}).get("error_signals") or [])) if isinstance(x, dict)]
            error_url = self._select_conversion_error_confirmation_url(
                signals,
                scan_data.get("browser_journey_probe") if isinstance(scan_data, dict) else {},
            )
            if error_url and self._booking_provider_for_host(urllib.parse.urlparse(error_url).hostname or ""):
                # External booking destinations are confirmed with the provider health checker, not Chromium.
                health = await asyncio.to_thread(self._check_external_booking_provider_health, [
                    {"provider": self._booking_provider_for_host(urllib.parse.urlparse(error_url).hostname or ""), "url": error_url}
                ])
                second_error_probe = {"external_provider_health": health}
            elif error_url:
                try:
                    second_error_probe = await self._run_targeted_playwright(
                        error_url, {}, mode="mobile", capture_evidence=True, post_load_wait_ms=1200
                    )
                except Exception as exc:
                    second_error_probe = {"browser_loaded": False, "browser_error": str(exc)}

        # A fresh static-visible-text pass gives an independent second collection method for
        # deterministic customer-facing errors. It is used only as corroboration of an error
        # already observed in a rendered customer journey; raw script/source strings alone never confirm it.
        second_error_static: Dict[str, Any] = {}
        first_rendered_error_keys: set[str] = set()
        expected_error_keys: set[str] = set()
        if error_candidate and error_url:
            expected_error_keys = {
                str(x.get("key") or "")
                for x in (((error_candidate.get("evidence") or {}).get("error_signals") or []))
                if isinstance(x, dict) and x.get("key")
            }
            first_browser = scan_data.get("browser_journey_probe") if isinstance(scan_data, dict) else {}
            if isinstance(first_browser, dict) and str(first_browser.get("url") or "").rstrip("/") == error_url.rstrip("/"):
                first_rendered_error_keys = {
                    str(x.get("key") or "")
                    for x in (first_browser.get("conversion_error_signals") or [])
                    if isinstance(x, dict) and x.get("key")
                }
            try:
                r = await asyncio.to_thread(self.safe_http.get, error_url, timeout=(4, 10), allow_redirects=True, max_bytes=800_000)
                if 200 <= int(r.status_code) < 400:
                    second_error_static = self._extract_static_html_evidence((r.text or "")[:750000], r.url, verified=True)
                    second_error_static["status_code"] = int(r.status_code)
                    second_error_static["url"] = r.url
                else:
                    second_error_static = {"status_code": int(r.status_code), "url": r.url}
            except Exception as exc:
                second_error_static = {"error": str(exc)[:220], "url": error_url}

        second_http = None
        if any(str(x.get("rule_key")) == "unsecured_ssl" for x in candidates):
            second_http = await asyncio.to_thread(self._fast_http_preflight, base_url)

        second_perf: Dict[str, Any] = {}
        if any(str(x.get("rule_key")) == "core_web_vitals" for x in candidates):
            second_perf = await asyncio.to_thread(self._fetch_google_pagespeed, base_url)
            # CrUX can independently corroborate performance without forcing a duplicate lab failure.
            second_perf.update(await asyncio.to_thread(self._fetch_crux_telemetry, base_url))

        # A small second static pass supports negative policy/ecommerce/B2B evidence without another full crawl.
        static_rules = {
            "checkout_cost_transparency", "guest_checkout_barrier", "checkout_complexity",
            "return_policy_discoverability", "shipping_info_discoverability", "delivery_expectation_clarity",
            "b2b_pricing_transparency",
        }
        need_static = any(str(x.get("rule_key")) in static_rules for x in candidates)
        second_static_combined: Dict[str, Any] = {}
        if need_static:
            try:
                r = await asyncio.to_thread(self.safe_http.get, base_url, timeout=(4, 10), allow_redirects=True, max_bytes=800_000)
                if 200 <= int(r.status_code) < 400:
                    second_static_combined = self._extract_static_html_evidence((r.text or "")[:750000], r.url, verified=True)
                    links = self._union_strings(scan_data.get("internal_links"), [str(x.get("url")) for x in scan_data.get("journey_pages_scanned", []) if isinstance(x, dict) and x.get("url")])
                    context_tags = list((profile_for_confirmation or {}).get("context_tags") or [])
                    j2 = await asyncio.to_thread(self._scan_priority_journey_pages, r.url, links, canonical_type, context_tags)
                    self._merge_journey_evidence(second_static_combined, j2)
            except Exception as exc:
                second_static_combined = {"confirmation_error": str(exc)[:220]}

        for leak in candidates:
            rule = str(leak.get("rule_key") or "")
            confirmed: Optional[bool] = None
            status_override = ""
            method = ""
            observed: Dict[str, Any] = {}
            if rule == "unsecured_ssl" and isinstance(second_http, dict):
                confirmed = bool(second_http.get("is_reachable") and second_http.get("has_ssl") is False)
                method = "second HTTP preflight"
                observed = {"final_url": second_http.get("final_url"), "has_ssl": second_http.get("has_ssl"), "status_code": second_http.get("status_code")}
            elif rule == "core_web_vitals" and second_perf:
                perf = self._to_float(second_perf.get("performance_score"))
                crux_grade = str(second_perf.get("real_user_speed_grade") or "UNKNOWN")
                if perf is not None:
                    confirmed = perf < 60 or crux_grade == "POOR"
                elif crux_grade != "UNKNOWN":
                    confirmed = crux_grade == "POOR"
                method = "second Google PageSpeed/CrUX collection"
                observed = {"performance_score": perf, "crux_grade": crux_grade}
            elif rule == "conversion_path_error":
                if second_error_probe.get("external_provider_health"):
                    health = second_error_probe["external_provider_health"]
                    confirmed = bool((health or {}).get("broken_count"))
                    observed = health
                    method = "second external booking-provider health check"
                elif second_error_probe or second_error_static:
                    rendered_signals = [x for x in (second_error_probe.get("conversion_error_signals") or []) if isinstance(x, dict)]
                    static_signals = [x for x in (second_error_static.get("conversion_error_signals") or []) if isinstance(x, dict)]
                    rendered_keys = {str(x.get("key") or "") for x in rendered_signals if x.get("key")}
                    static_keys = {str(x.get("key") or "") for x in static_signals if x.get("key")}
                    expected = expected_error_keys or rendered_keys or static_keys
                    rendered_match = bool(rendered_keys & expected) if expected else bool(rendered_signals)
                    static_match = bool(static_keys & expected) if expected else bool(static_signals)
                    first_rendered_match = bool(first_rendered_error_keys & expected) if expected else bool(first_rendered_error_keys)

                    # Preferred confirmation is a fresh rendered reproduction. If a dynamic widget is
                    # intermittent, a fresh static-visible reproduction can corroborate the first rendered
                    # observation. This prevents one clean race-condition render from erasing a real error.
                    initial_signals = [x for x in (((error_candidate.get("evidence") or {}).get("error_signals") or [])) if isinstance(x, dict)]
                    initial_urls = {str(x.get("url") or "") for x in initial_signals if x.get("url")}
                    if second_error_probe.get("browser_loaded") and rendered_match:
                        confirmed = True
                        method = "second rendered customer-journey pass"
                    elif first_rendered_match and static_match:
                        confirmed = True
                        method = "first rendered observation + fresh static-visible corroboration"
                    elif static_match and len(initial_urls) >= 2:
                        # Exact customer-visible error repeated across multiple first-pass pages and a fresh
                        # visible-text collection is meaningful corroboration even when JS timing prevents a
                        # second Chromium reproduction. It is scored conservatively, not as fully confirmed.
                        status_override = "CORROBORATED"
                        method = "multi-page visible-text evidence + fresh static-visible corroboration"
                    elif second_error_probe.get("browser_loaded") and not rendered_match and not static_match:
                        confirmed = False
                        method = "second rendered + fresh static corroboration pass"
                    else:
                        confirmed = None
                        method = "bounded rendered/static customer-journey confirmation"
                    observed = {
                        "url": error_url,
                        "expected_error_keys": sorted(expected),
                        "first_rendered_error_keys": sorted(first_rendered_error_keys),
                        "second_rendered_error_keys": sorted(rendered_keys),
                        "fresh_static_error_keys": sorted(static_keys),
                        "browser_loaded": second_error_probe.get("browser_loaded"),
                        "static_status_code": second_error_static.get("status_code"),
                    }
            elif rule == "form_architecture" and second_home:
                if second_home.get("browser_loaded"):
                    confirmed = bool(second_home.get("forms_present") and second_home.get("form_action_valid") is False)
                method = "second rendered homepage form inspection"
                observed = {"forms_present": second_home.get("forms_present"), "form_action_valid": second_home.get("form_action_valid")}
            elif rule == "primary_conversion_path" and second_home:
                confirmed = self._primary_conversion_gap_present(second_home, canonical_type)
                method = "second rendered primary-action inspection"
                observed = {"mobile_cta_types": second_home.get("mobile_cta_types") or [], "forms_present": second_home.get("forms_present"), "click_to_call_present": second_home.get("click_to_call_present")}
            elif rule == "click_to_call" and second_home:
                if str(second_home.get("click_to_call_status") or "").lower() == "verified":
                    confirmed = not bool(second_home.get("click_to_call_present"))
                method = "second rendered mobile click-to-call inspection"
                observed = {"click_to_call_present": second_home.get("click_to_call_present"), "status": second_home.get("click_to_call_status")}
            elif rule == "mobile_sticky_cta" and second_home:
                if str(second_home.get("mobile_cta_status") or "").lower() == "verified":
                    confirmed = not bool(second_home.get("mobile_sticky_cta_present"))
                method = "second rendered mobile sticky-action inspection"
                observed = {"mobile_sticky_cta_present": second_home.get("mobile_sticky_cta_present"), "mobile_cta_types": second_home.get("mobile_cta_types") or []}
            elif rule == "lead_form_friction" and second_home:
                fields = self._to_float(second_home.get("form_max_field_count"))
                confirmed = fields is not None and fields > 8
                method = "second rendered lead-form field count"
                observed = {"form_max_field_count": fields}
            elif rule in static_rules and second_static_combined:
                if rule == "checkout_cost_transparency":
                    confirmed = bool(second_static_combined.get("late_cost_disclosure_risk"))
                elif rule == "guest_checkout_barrier":
                    v = second_static_combined.get("guest_checkout_available")
                    confirmed = (v is False) if v is not None else None
                elif rule == "checkout_complexity":
                    fields = self._to_float(second_static_combined.get("checkout_form_field_count"))
                    confirmed = fields is not None and fields > 12
                elif rule == "return_policy_discoverability":
                    confirmed = not bool(second_static_combined.get("return_policy_linked"))
                elif rule == "shipping_info_discoverability":
                    confirmed = not bool(second_static_combined.get("shipping_info_linked"))
                elif rule == "delivery_expectation_clarity":
                    v = second_static_combined.get("delivery_date_visible")
                    confirmed = (v is False) if v is not None else None
                elif rule == "b2b_pricing_transparency":
                    confirmed = not bool(second_static_combined.get("pricing_linked"))
                method = "second bounded static journey inspection"
                observed = {
                    "return_policy_linked": second_static_combined.get("return_policy_linked"),
                    "shipping_info_linked": second_static_combined.get("shipping_info_linked"),
                    "pricing_linked": second_static_combined.get("pricing_linked"),
                    "checkout_form_field_count": second_static_combined.get("checkout_form_field_count"),
                }

            status = status_override or ("CONFIRMED" if confirmed is True else "DISPUTED" if confirmed is False else "UNCONFIRMED")
            results[rule] = {
                "status": status,
                "candidate_pre_dedupe_points": self._to_float(leak.get("pre_dedupe_penalty")) or self._to_float(leak.get("final_score_loss")) or 0.0,
                "method": method or "No safe passive recheck was available",
                "observed": observed,
                "checked_at": self._utc_now(),
            }

        return {
            "completed": True,
            "threshold_points": float(threshold_points),
            "candidate_count": len(candidates),
            "results": results,
            "completed_at": self._utc_now(),
            "policy": "High-impact candidates at or above the threshold require independent passive confirmation or corroboration before the final score may deduct them; corroborated-only findings are reduced-confidence.",
        }

    @staticmethod
    def _business_type_validation(requested: str, automatic: Dict[str, Any]) -> Dict[str, Any]:
        raw = str(requested or "auto").strip().lower().replace("-", "_").replace(" ", "_")
        confidence = HybridScanner._to_float((automatic or {}).get("confidence")) or 0.0
        journey = str((automatic or {}).get("journey_model") or "general")
        provisional = bool((automatic or {}).get("provisional"))
        direct_models = {
            "lead_quote", "appointment_consultation", "reservation_event", "direct_purchase",
            "demo_sales", "membership_subscription", "general",
        }
        direct_hint = raw if raw in direct_models else ""
        legacy_hint = raw if raw not in direct_models and raw not in {"", "auto", "unknown", "none"} else ""
        mismatch = bool(direct_hint and direct_hint != "general" and journey != direct_hint and confidence >= 0.75)
        return {
            "requested_journey_hint": direct_hint or "auto",
            "requested_legacy_hint": legacy_hint or "auto",
            "automatic_journey_model": journey,
            "automatic_confidence": round(confidence, 2),
            "provisional": provisional,
            "mismatch_warning": mismatch,
            "message": (
                "V7 scores the observable customer journey plus context tags. A direct journey selection can resolve close ambiguity, but unsupported selections remain provisional; legacy industry values are weak compatibility hints only."
            ),
        }

    def _static_content_signals(
        self,
        visible_text: str,
        links: List[Dict[str, str]],
        schema_types: List[str],
        probe: _StaticHTMLProbe,
    ) -> Dict[str, Any]:
        text_lower = visible_text.lower()
        hrefs = [str(item.get("href") or "") for item in links]
        link_text = [str(item.get("text") or "") for item in links]
        schema_lower = " ".join(schema_types).lower()
        address_visible = bool(
            re.search(
                r"\b\d{1,6}\s+[a-z0-9.'’\- ]+\s(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|drive|dr\.?|lane|ln\.?|way|highway|hwy\.?|place|pl\.?|court|ct\.?)\b",
                text_lower,
                re.I,
            )
            or any("maps.google" in href or "google.com/maps" in href for href in hrefs)
            or "postaladdress" in schema_lower
        )
        credential_signal_types = self._detect_credential_signals(visible_text, links, schema_types)
        trust_badges = bool(credential_signal_types)
        reviews_visible = bool("aggregaterating" in schema_lower or re.search(r"\b(testimonials?|customer reviews?|client reviews?|reviews?)\b", text_lower))
        guarantee_refund = bool(re.search(r"\b(money[- ]back|refund policy|satisfaction guarantee|guaranteed)\b", text_lower))
        about_team = any(re.search(r"\b(about|our team|team|our story|who we are)\b", text) for text in link_text)
        faq = "faqpage" in schema_lower or bool(re.search(r"\b(frequently asked questions|faqs?)\b", text_lower))
        case_studies = any(re.search(r"\b(case studies|portfolio|our work|projects|success stories)\b", text) for text in link_text)
        blog = any(re.search(r"\b(blog|insights|resources|articles|news)\b", text) for text in link_text)
        social = any(any(domain in href for domain in SOCIAL_DOMAINS) for href in hrefs)
        privacy = any("privacy" in text or "/privacy" in href for text, href in zip(link_text, hrefs))
        terms = any(re.search(r"\bterms\b", text) or "/terms" in href or "terms-of" in href for text, href in zip(link_text, hrefs))
        cookie_banner = bool(
            probe.cookie_markup
            or re.search(r"\b(cookie settings|cookie preferences|accept cookies|manage cookies)\b", text_lower)
        )

        # Passive commercial-journey evidence. These are observed facts only;
        # the scanner never mutates a cart or submits a customer-facing form.
        urlish = " ".join(hrefs).lower()
        checkout_context = bool(
            re.search(r"\b(cart|checkout|order summary|payment method|shipping address|billing address)\b", text_lower)
            or re.search(r"/(?:cart|checkout)(?:/|\?|$)", urlish)
        )
        guest_checkout_available = (
            True
            if checkout_context and re.search(r"\b(guest checkout|continue as guest|checkout as guest)\b", text_lower)
            else (
                False
                if checkout_context and re.search(
                    r"\b(create an account|sign in to checkout|login to checkout|register to checkout)\b",
                    text_lower,
                )
                else None
            )
        )
        late_cost_disclosure_risk = bool(
            checkout_context
            and re.search(
                r"\b(shipping|tax(?:es)?|fees?)\s+(?:will be\s+)?calculated at checkout\b|\bcalculated at checkout\b",
                text_lower,
            )
        )
        delivery_date_visible = (
            bool(re.search(r"\b(arrives? by|delivery by|estimated delivery|delivery date|delivers? on)\b", text_lower))
            if checkout_context
            else None
        )
        shipping_info_linked = any(
            re.search(r"\b(shipping|delivery)\b", text)
            or re.search(r"/(?:shipping|delivery)(?:/|\?|$)", href)
            for text, href in zip(link_text, hrefs)
        )
        return_policy_linked = any(
            re.search(r"\b(return|refund)\b", text)
            or re.search(r"/(?:returns?|refunds?)(?:/|\?|$)", href)
            for text, href in zip(link_text, hrefs)
        )
        pricing_linked = any(
            re.search(r"\b(pricing|plans?|packages?)\b", text)
            or re.search(r"/(?:pricing|plans?|packages?)(?:/|\?|$)", href)
            for text, href in zip(link_text, hrefs)
        )
        plan_matrix_signal = bool(
            len(re.findall(r"(?:\$|€|£)\s*\d+(?:[.,]\d+)?", visible_text)) >= 2
            and re.search(r"\b(month|monthly|year|yearly|annual|plan|tier)\b", text_lower)
        )
        image_evidence_blob = " ".join(
            " ".join(str(image.get(key) or "") for key in ("alt", "title", "src", "class", "id"))
            for image in probe.images
        ).lower()
        product_ui_preview_signal = bool(
            re.search(r"\b(dashboard|interface|product tour|app preview|software screenshot|see it in action)\b", text_lower)
            or re.search(r"dashboard|interface|ui[-_ ]?(?:preview|screenshot)|app[-_ ]?screenshot|product[-_ ]?screenshot", image_evidence_blob)
        )

        bylines = bool(
            probe.has_author_markup
            or re.search(r"(?:^|\n|\s)by\s+[A-Z][A-Za-z.'’\-]+(?:\s+[A-Z][A-Za-z.'’\-]+)+", visible_text)
        )
        return {
            "address_location_visible": address_visible,
            "trust_badges_present": trust_badges,
            "credential_signals_present": bool(credential_signal_types),
            "credential_signal_types": credential_signal_types,
            "reviews_visible": reviews_visible,
            "guarantee_refund_present": guarantee_refund,
            "about_team_linked": about_team,
            "social_proof_present": reviews_visible or trust_badges or case_studies,
            "faq_present": faq,
            "case_studies_portfolio_present": case_studies,
            "blog_present": blog,
            "social_links_present": social,
            "privacy_policy_linked": privacy,
            "terms_linked": terms,
            "privacy_terms_linked": privacy and terms,
            "cookie_banner_present": cookie_banner,
            "checkout_context_detected": checkout_context,
            "guest_checkout_available": guest_checkout_available,
            "late_cost_disclosure_risk": late_cost_disclosure_risk,
            "delivery_date_visible": delivery_date_visible,
            "shipping_info_linked": shipping_info_linked,
            "return_policy_linked": return_policy_linked,
            "pricing_linked": pricing_linked,
            "plan_matrix_signal": plan_matrix_signal,
            "product_ui_preview_signal": product_ui_preview_signal,
            "author_bylines_present": bylines,
            "publication_dates_visible": probe.has_publication_date_markup,
        }

    @staticmethod
    def _detect_cms_static(content_lower: str, generator: str) -> Tuple[str, str]:
        joined = f"{content_lower}\n{(generator or '').lower()}"
        checks = (
            ("WordPress", ("wp-content", "wp-includes", "wordpress")),
            ("Shopify", ("cdn.shopify.com", "myshopify", "shopify")),
            ("Wix", ("wixstatic.com", "wix.com", "wix")),
            ("Squarespace", ("static1.squarespace.com", "squarespace")),
            ("Webflow", ("webflow.js", "webflow.css", "webflow")),
            ("Next.js", ("/_next/", "__next_data__", "next.js")),
        )
        for name, markers in checks:
            hits = sum(marker in joined for marker in markers)
            if hits >= 2:
                return name, "high"
            if hits == 1:
                return name, "medium"
        if "id=\"root\"" in content_lower or "id='root'" in content_lower or "id=\"app\"" in content_lower:
            return "Modern JavaScript Stack", "low"
        return "Not confidently identified", "low"

    @staticmethod
    def _needs_browser_retry(dom: Dict[str, Any], static: Dict[str, Any]) -> bool:
        if not dom.get("browser_loaded"):
            return True
        if dom.get("bot_challenge_suspected"):
            return True
        if len(str(dom.get("page_text") or "")) < 100 and bool(static.get("static_html_verified")):
            return True
        if str(dom.get("h1_status") or "unknown") == "unknown":
            return True
        if str(dom.get("mobile_cta_status") or "unknown") != "verified":
            return True
        return False

    @staticmethod
    def _dom_attempt_score(dom: Dict[str, Any]) -> int:
        score = 0
        if dom.get("browser_loaded"):
            score += 4
        if dom.get("dom_complete"):
            score += 2
        if str(dom.get("h1_status") or "unknown") in {"present", "missing"}:
            score += 2
        if str(dom.get("mobile_cta_status") or "unknown") == "verified":
            score += 3
        if len(str(dom.get("page_text") or "")) >= 100:
            score += 2
        if not dom.get("bot_challenge_suspected"):
            score += 1
        return score

    @staticmethod
    def _dom_evidence_complete(data: Dict[str, Any]) -> bool:
        """Whether a rendered pass is safe to use for negative presence claims."""
        return bool(
            data.get("browser_loaded")
            and data.get("dom_complete")
            and not data.get("bot_challenge_suspected")
            and int(data.get("browser_blocked_request_count") or 0) == 0
            and len(str(data.get("page_text") or "")) >= 20
        )

    @staticmethod
    def _static_evidence_complete(data: Dict[str, Any]) -> bool:
        return bool(
            data.get("static_html_verified")
            and not data.get("static_html_error")
        )

    @staticmethod
    def _union_strings(*values: Any) -> List[str]:
        found: List[str] = []
        for value in values:
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    text = str(item or "").strip()
                    if text and text not in found:
                        found.append(text)
        return found

    @classmethod
    def _presence_consensus(
        cls,
        first_value: Any,
        second_value: Any,
        *,
        first_negative_verified: bool,
        second_negative_verified: bool,
        allow_first_only_negative: bool = True,
        allow_second_only_negative: bool = True,
    ) -> Optional[bool]:
        """Merge a presence/absence fact without allowing a false negative to erase proof.

        True is monotonic: if either reliable source observes the feature, the merged result is True.
        False is emitted only when a source is allowed to make a conclusive negative claim.
        Otherwise the result is UNKNOWN (None).
        """
        if first_value is True or second_value is True:
            return True

        first_false = first_value is False
        second_false = second_value is False

        if first_false and second_false:
            if (first_negative_verified and allow_first_only_negative) or (
                second_negative_verified and allow_second_only_negative
            ):
                return False
            return None

        if first_false and first_negative_verified and allow_first_only_negative:
            return False
        if second_false and second_negative_verified and allow_second_only_negative:
            return False
        return None

    def _merge_dom_attempts(self, first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
        primary, secondary = (second, first) if self._dom_attempt_score(second) > self._dom_attempt_score(first) else (first, second)
        merged = dict(primary)

        # Fill genuinely absent/unknown scalar values from the weaker attempt.
        for key, value in secondary.items():
            current = merged.get(key)
            if current in (None, "", [], {}) and value not in (None, "", [], {}):
                merged[key] = value
            if isinstance(current, str) and current.lower() == "unknown" and isinstance(value, str) and value.lower() != "unknown":
                merged[key] = value

        first_complete = self._dom_evidence_complete(first)
        second_complete = self._dom_evidence_complete(second)

        # H1 presence is monotonic across browser attempts. A single positive observation wins.
        first_h1 = str(first.get("h1_status") or "unknown").lower()
        second_h1 = str(second.get("h1_status") or "unknown").lower()
        if "present" in {first_h1, second_h1}:
            merged["h1_status"] = "present"
            merged["h1_tags"] = self._union_strings(first.get("h1_tags"), second.get("h1_tags"))
            merged["h1_dom_text"] = self._union_strings(first.get("h1_dom_text"), second.get("h1_dom_text"))
            merged["h1_dom_count"] = max(self._to_int(first.get("h1_dom_count"), 0) or 0, self._to_int(second.get("h1_dom_count"), 0) or 0)
            merged["h1_source_count"] = max(self._to_int(first.get("h1_source_count"), 0) or 0, self._to_int(second.get("h1_source_count"), 0) or 0)
        elif first_h1 == "missing" and second_h1 == "missing" and (first_complete or second_complete):
            merged["h1_status"] = "missing"
        elif first_h1 == "missing" and first_complete and second_h1 == "unknown":
            merged["h1_status"] = "missing"
        elif second_h1 == "missing" and second_complete and first_h1 == "unknown":
            merged["h1_status"] = "missing"
        else:
            merged["h1_status"] = "unknown"

        # Presence facts from mobile + desktop use evidence consensus. A positive observation
        # on either viewport cannot be erased by the other viewport missing it.
        dom_presence_keys = (
            "phone_number_visible", "click_to_call_present", "whatsapp_present", "live_chat_present",
            "favicon_present", "html_lang_present", "canonical_present", "mobile_viewport_configured",
            "schema_present", "has_clarity", "has_hotjar", "has_qualitative_analytics",
            "has_other_measurement", "measurement_layer_present", "has_ga4", "has_meta_pixel", "retargeting_pixel_installed", "forms_present",
            "address_location_visible", "trust_badges_present", "credential_signals_present", "reviews_visible",
            "guarantee_refund_present", "about_team_linked", "social_proof_present",
            "faq_present", "case_studies_portfolio_present", "blog_present", "social_links_present",
            "privacy_policy_linked", "terms_linked", "privacy_terms_linked", "cookie_banner_present",
            "shipping_info_linked", "return_policy_linked", "pricing_linked",
            "plan_matrix_signal", "product_ui_preview_signal",
            "author_bylines_present", "publication_dates_visible",
        )
        for key in dom_presence_keys:
            consensus = self._presence_consensus(
                first.get(key),
                second.get(key),
                first_negative_verified=first_complete,
                second_negative_verified=second_complete,
            )
            if consensus is not None:
                merged[key] = consensus
            elif key in merged and merged.get(key) is False:
                # Do not preserve a weak negative when neither rendered pass was complete.
                merged[key] = None

        # Preserve/union positive evidence payloads.
        merged["detected_phone_numbers"] = self._union_strings(
            first.get("detected_phone_numbers"), second.get("detected_phone_numbers")
        )
        merged["schema_types"] = self._union_strings(first.get("schema_types"), second.get("schema_types"))
        merged["credential_signal_types"] = self._union_strings(first.get("credential_signal_types"), second.get("credential_signal_types"))
        merged["measurement_platforms"] = self._union_strings(first.get("measurement_platforms"), second.get("measurement_platforms"))
        merged["measurement_layer_present"] = bool(merged.get("measurement_platforms") or merged.get("measurement_layer_present"))
        merged["credential_signals_present"] = bool(merged.get("credential_signal_types") or merged.get("credential_signals_present"))
        merged["internal_links"] = self._union_strings(first.get("internal_links"), second.get("internal_links"))
        merged["booking_provider_links"] = self._dedupe_booking_provider_links(
            list(first.get("booking_provider_links") or []) + list(second.get("booking_provider_links") or [])
        )
        merged["conversion_error_signals"] = list(first.get("conversion_error_signals") or []) + [
            item for item in (second.get("conversion_error_signals") or [])
            if item not in (first.get("conversion_error_signals") or [])
        ]
        merged["conversion_path_error_detected"] = bool(merged["conversion_error_signals"])

        if merged.get("phone_number_visible") is not None:
            merged["phone_visibility_status"] = "verified"
        else:
            merged["phone_visibility_status"] = "unknown"
        if merged.get("click_to_call_present") is not None:
            merged["click_to_call_status"] = "verified"
        else:
            merged["click_to_call_status"] = "unknown"

        # Mobile CTA evidence must come from the mobile viewport. A desktop retry may recover
        # document evidence but must never masquerade as mobile sticky-CTA verification.
        mobile_attempt = first if first.get("browser_mode", "mobile") == "mobile" else second
        mobile_status = str(mobile_attempt.get("mobile_cta_status") or "unknown").lower()
        if mobile_status == "verified":
            for key in (
                "mobile_cta_visible", "mobile_primary_cta_present", "mobile_sticky_cta_present",
                "mobile_cta_status", "mobile_cta_type", "mobile_cta_types", "mobile_cta_evidence",
                "add_to_cart_visible", "order_online_present", "reservation_present", "booking_action_present", "directions_present",
            ):
                merged[key] = mobile_attempt.get(key)
        elif mobile_status == "partial":
            merged["mobile_cta_status"] = "partial"
            merged["mobile_cta_types"] = list(mobile_attempt.get("mobile_cta_types") or [])
            merged["mobile_cta_evidence"] = list(mobile_attempt.get("mobile_cta_evidence") or [])
            merged["mobile_cta_type"] = mobile_attempt.get("mobile_cta_type") or "unknown"
            for key in (
                "mobile_cta_visible", "mobile_primary_cta_present", "mobile_sticky_cta_present",
                "add_to_cart_visible", "order_online_present", "reservation_present", "booking_action_present", "directions_present",
            ):
                merged[key] = True if mobile_attempt.get(key) is True else None
        else:
            merged["mobile_cta_status"] = "unknown"
            merged["mobile_primary_cta_present"] = None
            merged["mobile_sticky_cta_present"] = None
            merged["mobile_cta_visible"] = None

        merged["browser_retry_used"] = True
        merged["browser_attempts"] = [first.get("browser_mode", "mobile"), second.get("browser_mode", "desktop")]
        return merged

    def _merge_static_and_dom(self, static: Dict[str, Any], dom: Dict[str, Any]) -> Dict[str, Any]:
        """Merge raw-HTML and rendered-DOM facts using evidence consensus.

        V4 invariant: proof of presence from either reliable source wins. A source that misses
        something is not allowed to erase proof collected by another source. Negative visible-
        content claims require a complete rendered DOM; structural metadata may also use a
        complete static HTML document as conclusive evidence.
        """
        merged = dict(static or {})
        dom = dom or {}
        static_complete = self._static_evidence_complete(static)
        dom_complete = self._dom_evidence_complete(dom)

        # Always preserve browser-quality diagnostics.
        for key in ("browser_loaded", "dom_complete", "browser_status_code", "browser_error", "bot_challenge_suspected", "browser_mode", "browser_retry_used", "browser_attempts"):
            if key in dom:
                merged[key] = dom.get(key)

        # H1: positive evidence from either source wins. Missing requires a complete rendered DOM
        # or agreement from both complete evidence paths.
        static_h1 = str(static.get("h1_status") or "unknown").lower()
        dom_h1 = str(dom.get("h1_status") or "unknown").lower()
        if "present" in {static_h1, dom_h1}:
            merged["h1_status"] = "present"
            merged["h1_tags"] = self._union_strings(static.get("h1_tags"), dom.get("h1_tags"))
            merged["h1_dom_text"] = self._union_strings(dom.get("h1_dom_text"))
            merged["h1_dom_count"] = dom.get("h1_dom_count")
            merged["h1_source_count"] = max(self._to_int(static.get("h1_source_count"), 0) or 0, self._to_int(dom.get("h1_source_count"), 0) or 0)
        elif dom_h1 == "missing" and dom_complete:
            merged["h1_status"] = "missing"
            for key in ("h1_tags", "h1_dom_count", "h1_dom_text", "h1_source_count"):
                if key in dom:
                    merged[key] = dom.get(key)
        else:
            merged["h1_status"] = "unknown"

        # Browser content/metadata values supplement static text; non-empty values never erase a
        # better static value. Page text is merged by choosing the richer rendered/static body.
        static_text = str(static.get("page_text") or "")
        dom_text = str(dom.get("page_text") or "")
        if len(dom_text) >= len(static_text) and len(dom_text) >= 20:
            merged["page_text"] = dom_text
            merged["visible_word_count"] = dom.get("visible_word_count")
        elif static_text:
            merged["page_text"] = static_text
            merged["visible_word_count"] = static.get("visible_word_count")

        for key in ("title", "meta_description"):
            static_value = str(static.get(key) or "").strip()
            dom_value = str(dom.get(key) or "").strip()
            if dom_value and not static_value:
                merged[key] = dom_value
            elif static_value:
                merged[key] = static_value
            elif dom_value:
                merged[key] = dom_value

        if dom.get("page_html_length"):
            merged["page_html_length"] = max(self._to_int(static.get("page_html_length"), 0) or 0, self._to_int(dom.get("page_html_length"), 0) or 0)
            merged["page_content_len"] = merged["page_html_length"]

        # Structural/document presence. Static HTML may make a conclusive negative claim; rendered
        # DOM may overturn it with positive evidence.
        structural_presence_keys = (
            "favicon_present", "html_lang_present", "canonical_present", "mobile_viewport_configured",
            "schema_present",
        )
        for key in structural_presence_keys:
            consensus = self._presence_consensus(
                static.get(key),
                dom.get(key),
                first_negative_verified=static_complete,
                second_negative_verified=dom_complete,
                allow_first_only_negative=True,
                allow_second_only_negative=True,
            )
            merged[key] = consensus

        merged["schema_types"] = self._union_strings(static.get("schema_types"), dom.get("schema_types"))
        merged["credential_signal_types"] = self._union_strings(static.get("credential_signal_types"), dom.get("credential_signal_types"))
        merged["credential_signals_present"] = bool(merged.get("credential_signal_types") or static.get("credential_signals_present") or dom.get("credential_signals_present"))
        merged["internal_links"] = self._union_strings(static.get("internal_links"), dom.get("internal_links"))
        merged["booking_provider_links"] = self._dedupe_booking_provider_links(
            list(static.get("booking_provider_links") or []) + list(dom.get("booking_provider_links") or [])
        )
        merged["conversion_error_signals"] = list(static.get("conversion_error_signals") or []) + [
            item for item in (dom.get("conversion_error_signals") or [])
            if item not in (static.get("conversion_error_signals") or [])
        ]
        merged["conversion_path_error_detected"] = bool(merged["conversion_error_signals"])
        if merged["schema_types"]:
            merged["schema_present"] = True

        # Visible/trust/contact signals: any positive source wins. A raw-HTML miss by itself is not
        # enough to fail because client-rendered/lazy content may not exist in the initial source.
        visible_presence_keys = (
            "address_location_visible", "trust_badges_present", "credential_signals_present", "reviews_visible",
            "guarantee_refund_present", "about_team_linked", "social_proof_present",
            "faq_present", "case_studies_portfolio_present", "blog_present", "social_links_present",
            "privacy_policy_linked", "terms_linked", "privacy_terms_linked", "cookie_banner_present",
            "shipping_info_linked", "return_policy_linked", "pricing_linked",
            "plan_matrix_signal", "product_ui_preview_signal",
            "author_bylines_present", "publication_dates_visible",
        )
        for key in visible_presence_keys:
            consensus = self._presence_consensus(
                static.get(key),
                dom.get(key),
                first_negative_verified=static_complete,
                second_negative_verified=dom_complete,
                allow_first_only_negative=False,
                allow_second_only_negative=True,
            )
            merged[key] = consensus

        # Checkout-specific facts are only meaningful when a checkout/cart context was observed.
        merged["checkout_context_detected"] = bool(
            static.get("checkout_context_detected") or dom.get("checkout_context_detected")
        )
        if merged["checkout_context_detected"]:
            guest_values = [
                value for value in (
                    static.get("guest_checkout_available"),
                    dom.get("guest_checkout_available"),
                )
                if value is not None
            ]
            merged["guest_checkout_available"] = (
                True if True in guest_values else (False if False in guest_values else None)
            )
            merged["late_cost_disclosure_risk"] = bool(
                static.get("late_cost_disclosure_risk") or dom.get("late_cost_disclosure_risk")
            )
            delivery_values = [
                value for value in (
                    static.get("delivery_date_visible"),
                    dom.get("delivery_date_visible"),
                )
                if value is not None
            ]
            merged["delivery_date_visible"] = (
                True if True in delivery_values else (False if False in delivery_values else None)
            )
        else:
            merged["guest_checkout_available"] = None
            merged["late_cost_disclosure_risk"] = False
            merged["delivery_date_visible"] = None

        # Phone visibility and instant actions use the same positive-wins rule. Static HTML can prove
        # presence; a negative becomes conclusive only with a complete rendered DOM.
        for key in ("phone_number_visible", "click_to_call_present", "whatsapp_present", "live_chat_present"):
            consensus = self._presence_consensus(
                static.get(key),
                dom.get(key),
                first_negative_verified=static_complete,
                second_negative_verified=dom_complete,
                allow_first_only_negative=False,
                allow_second_only_negative=True,
            )
            merged[key] = consensus

        merged["detected_phone_numbers"] = self._union_strings(
            static.get("detected_phone_numbers"), dom.get("detected_phone_numbers")
        )
        merged["phone_visibility_status"] = "verified" if merged.get("phone_number_visible") is not None else "unknown"
        merged["click_to_call_status"] = "verified" if merged.get("click_to_call_present") is not None else "unknown"

        # Tracking presence: a positive in either source wins. A rendered negative is conclusive;
        # static-only negatives stay UNKNOWN because tags can be injected dynamically.
        for key in (
            "has_clarity", "has_hotjar", "has_qualitative_analytics", "has_other_measurement",
            "measurement_layer_present", "has_ga4", "has_meta_pixel", "retargeting_pixel_installed",
        ):
            consensus = self._presence_consensus(
                static.get(key),
                dom.get(key),
                first_negative_verified=static_complete,
                second_negative_verified=dom_complete,
                allow_first_only_negative=False,
                allow_second_only_negative=True,
            )
            merged[key] = consensus

        merged["measurement_platforms"] = self._union_strings(static.get("measurement_platforms"), dom.get("measurement_platforms"))
        merged["measurement_layer_present"] = bool(merged.get("measurement_platforms") or merged.get("measurement_layer_present"))

        # Forms can be inserted by JavaScript. Positive evidence wins; static-only absence is unknown.
        forms_consensus = self._presence_consensus(
            static.get("forms_present"),
            dom.get("forms_present"),
            first_negative_verified=static_complete,
            second_negative_verified=dom_complete,
            allow_first_only_negative=False,
            allow_second_only_negative=True,
        )
        merged["forms_present"] = forms_consensus
        if dom.get("form_action_valid") is not None and dom_complete:
            merged["form_action_valid"] = dom.get("form_action_valid")
        elif static.get("form_action_valid") is not None:
            merged["form_action_valid"] = static.get("form_action_valid")
        if dom.get("form_functional_status") not in (None, "", "UNKNOWN"):
            merged["form_functional_status"] = dom.get("form_functional_status")
        if "form_payload_fired" in dom:
            merged["form_payload_fired"] = dom.get("form_payload_fired")

        form_source = dom if dom_complete and isinstance(dom.get("form_field_counts"), list) else static
        for key in (
            "form_field_counts",
            "form_required_field_counts",
            "form_min_field_count",
            "form_max_field_count",
            "form_max_required_field_count",
        ):
            if key in form_source:
                merged[key] = form_source.get(key)
        merged["checkout_form_field_count"] = (
            merged.get("form_max_field_count") if merged.get("checkout_context_detected") else None
        )

        # Mobile CTA evidence remains browser/mobile-only; raw HTML cannot prove visibility/stickiness.
        dom_mobile_status = str(dom.get("mobile_cta_status") or "unknown").lower()
        if dom_mobile_status == "verified":
            for key in (
                "mobile_cta_visible", "mobile_primary_cta_present", "mobile_sticky_cta_present",
                "mobile_cta_status", "mobile_cta_type", "mobile_cta_types", "mobile_cta_evidence",
                "add_to_cart_visible", "order_online_present", "reservation_present", "booking_action_present", "directions_present",
            ):
                merged[key] = dom.get(key)
        elif dom_mobile_status == "partial":
            merged["mobile_cta_status"] = "partial"
            merged["mobile_cta_types"] = self._union_strings(merged.get("mobile_cta_types"), dom.get("mobile_cta_types"))
            merged["mobile_cta_evidence"] = list(dom.get("mobile_cta_evidence") or [])
            for key in (
                "mobile_cta_visible", "mobile_primary_cta_present", "mobile_sticky_cta_present",
                "add_to_cart_visible", "order_online_present", "reservation_present", "booking_action_present", "directions_present",
            ):
                if dom.get(key) is True:
                    merged[key] = True
                elif merged.get(key) is not True:
                    merged[key] = None

        # Images: rendered DOM is preferred when available; otherwise keep complete static evidence.
        if (self._to_int(dom.get("total_images"), 0) or 0) > 0 or (dom_complete and dom.get("missing_alt_images") is not None):
            for key in (
                "image_count", "total_images", "missing_alt_images", "images_with_alt", "lazy_image_count",
                "lazy_loading_status", "custom_photography_signal", "custom_photography_status",
            ):
                if key in dom:
                    merged[key] = dom.get(key)
            merged["image_evidence_status"] = "verified"

        if dom.get("ai_spectrum_status") == "heuristic":
            merged["ai_spectrum_pct"] = dom.get("ai_spectrum_pct")
            merged["ai_spectrum_status"] = "heuristic"
            merged["ai_flags"] = dom.get("ai_flags") or merged.get("ai_flags") or {}

        if str(dom.get("cms_platform") or "") and dom.get("cms_platform") != "Not confidently identified":
            merged["cms_platform"] = dom.get("cms_platform")
            merged["cms_confidence"] = dom.get("cms_confidence", "low")

        # Evidence-status markers describe collection availability; individual booleans can still be
        # None/UNKNOWN when neither source is conclusive.
        if static_complete or dom_complete:
            merged["metadata_evidence_status"] = "verified"
            merged["technical_evidence_status"] = "verified"
            merged["content_signal_status"] = "verified"
            merged["tracking_evidence_status"] = "verified"
            merged["form_evidence_status"] = "verified"

        return merged

    def _empty_dom_meta(self, error: str = "") -> Dict[str, Any]:
        return {
            "browser_loaded": False,
            "dom_complete": False,
            "browser_status_code": None,
            "browser_error": error,
            "bot_challenge_suspected": False,
            "static_html_verified": False,
            "static_html_error": "",
            "metadata_evidence_status": "unknown",
            "image_evidence_status": "unknown",
            "tracking_evidence_status": "unknown",
            "form_evidence_status": "unknown",
            "technical_evidence_status": "unknown",
            "content_signal_status": "unknown",
            "title": "",
            "meta_description": "",
            "h1_tags": [],
            "h1_dom_count": None,
            "h1_dom_text": [],
            "h1_source_count": None,
            "h1_status": "unknown",
            "image_count": 0,
            "missing_alt_images": 0,
            "images_with_alt": 0,
            "total_images": 0,
            "page_content_len": 0,
            "page_html_length": 0,
            "page_text": "",
            "visible_word_count": 0,
            "click_to_call_present": False,
            "click_to_call_status": "unknown",
            "phone_number_visible": False,
            "phone_visibility_status": "unknown",
            "detected_phone_numbers": [],
            "mobile_cta_visible": False,
            "mobile_primary_cta_present": False,
            "mobile_sticky_cta_present": False,
            "mobile_cta_status": "unknown",
            "mobile_cta_type": "unknown",
            "mobile_cta_types": [],
            "add_to_cart_visible": False,
            "order_online_present": False,
            "reservation_present": False,
            "booking_action_present": False,
            "directions_present": False,
            "whatsapp_present": False,
            "live_chat_present": False,
            "form_payload_fired": False,
            "forms_present": False,
            "form_action_valid": None,
            "form_field_counts": [],
            "form_required_field_counts": [],
            "form_min_field_count": None,
            "form_max_field_count": None,
            "form_max_required_field_count": None,
            "checkout_form_field_count": None,
            "form_functional_status": "UNKNOWN",
            "tap_targets_flagged": [],
            "ai_spectrum_pct": None,
            "ai_spectrum_status": "unknown",
            "ai_flags": {},
            "cms_platform": "Not confidently identified",
            "cms_confidence": "low",
            "has_clarity": False,
            "has_hotjar": False,
            "has_qualitative_analytics": False,
            "has_other_measurement": False,
            "measurement_layer_present": False,
            "measurement_platforms": [],
            "has_ga4": False,
            "has_meta_pixel": False,
            "retargeting_pixel_installed": False,
            "favicon_present": None,
            "html_lang_present": None,
            "schema_present": None,
            "schema_types": [],
            "canonical_present": None,
            "mobile_viewport_configured": None,
            "lazy_loading_status": "UNKNOWN",
            "address_location_visible": None,
            "trust_badges_present": None,
            "credential_signals_present": None,
            "credential_signal_types": [],
            "reviews_visible": None,
            "guarantee_refund_present": None,
            "about_team_linked": None,
            "social_proof_present": None,
            "faq_present": None,
            "case_studies_portfolio_present": None,
            "blog_present": None,
            "social_links_present": None,
            "privacy_policy_linked": None,
            "terms_linked": None,
            "privacy_terms_linked": None,
            "cookie_banner_present": None,
            "checkout_context_detected": False,
            "guest_checkout_available": None,
            "late_cost_disclosure_risk": False,
            "delivery_date_visible": None,
            "shipping_info_linked": None,
            "return_policy_linked": None,
            "pricing_linked": None,
            "plan_matrix_signal": None,
            "product_ui_preview_signal": None,
            "author_bylines_present": None,
            "publication_dates_visible": None,
            "internal_links": [],
            "booking_provider_links": [],
            "conversion_error_signals": [],
            "evidence_screenshot_mime": "",
            "evidence_screenshot_b64": "",
            "evidence_screenshot_sha256": "",
            "conversion_path_error_detected": False,
            "journey_evidence_status": "unknown",
            "journey_pages_scanned": [],
            "journey_pages_verified": 0,
            "journey_text_sample": "",
            "custom_photography_status": "UNKNOWN",
            "custom_photography_signal": False,
        }

    async def _hydrate_lazy_content(self, page: Any) -> None:
        """Bounded non-interactive scroll sweep to reveal lazy-rendered page sections.

        This never clicks or submits anything. It only scrolls through a handful of positions and
        returns to the top before evidence collection. Failure is non-fatal.
        """
        try:
            metrics = await page.evaluate(
                """() => ({
                    height: Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0),
                    viewport: window.innerHeight || 800
                })"""
            )
            height = self._to_int((metrics or {}).get("height"), 0) or 0
            viewport = max(1, self._to_int((metrics or {}).get("viewport"), 800) or 800)
            if height <= viewport * 1.25:
                return

            max_y = max(0, height - viewport)
            # At most five reveal positions keeps the pass fast and deterministic.
            positions = sorted({
                min(max_y, int(max_y * fraction))
                for fraction in (0.20, 0.40, 0.60, 0.80, 1.00)
            })
            for y in positions:
                await page.evaluate("y => window.scrollTo(0, y)", y)
                await page.wait_for_timeout(120)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(180)
        except Exception:
            # Lazy hydration is an evidence enhancer, never a reason to fail the scan.
            return

    async def _run_targeted_playwright(
        self, url: str, psi_data: Dict[str, Any], mode: str = "mobile", capture_evidence: bool = False,
        post_load_wait_ms: int = 0,
    ) -> Dict[str, Any]:
        results = self._empty_dom_meta()
        # Validate the browser's top-level destination before Chromium is launched.  The
        # validated IPv4 is pinned into Chromium's resolver so the socket cannot be switched
        # to a private address between our DNS check and page navigation.  IPv6-only sites
        # remain statically scannable rather than weakening the browser guardrail.
        try:
            browser_target = await asyncio.to_thread(validate_public_http_url, url)
        except NetworkTargetError as exc:
            results["browser_error"] = f"network target blocked: {exc}"
            results["browser_security_status"] = "BLOCKED_UNSAFE_TARGET"
            return results
        pinned_ipv4 = browser_target.preferred_ipv4
        if not pinned_ipv4:
            results["browser_error"] = "Strict browser SSRF mode requires a validated public IPv4 target; static evidence remains available."
            results["browser_security_status"] = "IPV6_ONLY_STATIC_FALLBACK"
            return results
        results["browser_security_status"] = "PUBLIC_TARGET_PINNED"
        results["browser_blocked_request_count"] = 0
        results["browser_blocked_requests"] = []
        audits = (psi_data.get("lighthouseResult") or {}).get("audits") or {}
        tap_items = ((audits.get("tap-targets") or {}).get("details") or {}).get("items")
        if isinstance(tap_items, list):
            results["tap_targets_flagged"] = [
                ((item.get("node") or {}).get("selector"))
                for item in tap_items
                if ((item.get("node") or {}).get("selector"))
            ]

        async with async_playwright() as playwright:
            launch_kwargs: Dict[str, Any] = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--no-proxy-server",
                    f"--host-resolver-rules=MAP {browser_target.host} {pinned_ipv4}",
                ],
            }
            chromium_executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
            if chromium_executable:
                launch_kwargs["executable_path"] = chromium_executable
            browser = await playwright.chromium.launch(**launch_kwargs)
            if mode == "desktop":
                viewport = {"width": 1365, "height": 900}
                user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
                )
            else:
                viewport = {"width": 390, "height": 844}
                user_agent = (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
                )
            context = await browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                service_workers="block",
            )
            results["browser_mode"] = mode
            booking_trusted_hosts = tuple(
                domain
                for domains in BOOKING_PROVIDER_HOSTS.values()
                for domain in domains
            )
            # WebRTC/WebTransport are unnecessary for passive website evidence and can create
            # alternate network paths outside ordinary fetch/navigation interception.
            await context.add_init_script(
                """
                (() => {
                  try { Object.defineProperty(window, 'RTCPeerConnection', {value: undefined, configurable: false}); } catch(e) {}
                  try { Object.defineProperty(window, 'webkitRTCPeerConnection', {value: undefined, configurable: false}); } catch(e) {}
                  try { Object.defineProperty(window, 'WebTransport', {value: undefined, configurable: false}); } catch(e) {}
                })();
                """
            )
            page = await context.new_page()

            async def _record_blocked(request_url: str, reason: str) -> None:
                results["browser_blocked_request_count"] = int(results.get("browser_blocked_request_count") or 0) + 1
                items = results.setdefault("browser_blocked_requests", [])
                if isinstance(items, list) and len(items) < 20:
                    items.append({"url": self._safe_evidence_url(request_url), "reason": str(reason)[:120]})

            async def _guard_route(route, request) -> None:
                request_url = str(request.url or "")
                try:
                    parts = urllib.parse.urlsplit(request_url)
                    scheme = str(parts.scheme or "").lower()
                    if scheme in {"http", "https"}:
                        checked = await asyncio.to_thread(validate_public_http_url, request_url)
                        if not browser_cross_origin_host_allowed(
                            checked.host, browser_target.host, extra_trusted_hosts=booking_trusted_hosts
                        ):
                            raise NetworkTargetError(
                                "Untrusted cross-origin browser destination blocked",
                                "UNTRUSTED_CROSS_ORIGIN",
                            )
                        # The top-level page is pinned.  Because the HTTP preflight has already
                        # resolved redirects, a new cross-host main-frame navigation is unnecessary
                        # for evidence collection and is blocked rather than giving an untrusted page
                        # another unpinned navigation surface. Subresources still require public DNS.
                        if request.is_navigation_request() and request.frame == page.main_frame and checked.host != browser_target.host:
                            raise NetworkTargetError("Cross-host top-level browser navigation blocked", "CROSS_HOST_NAVIGATION")
                        await route.continue_()
                        return
                    if browser_non_network_scheme_allowed(request_url):
                        await route.continue_()
                        return
                    raise NetworkTargetError("Non-web browser network scheme blocked", "INVALID_SCHEME")
                except Exception as exc:
                    await _record_blocked(request_url, getattr(exc, "reason", str(exc)))
                    await route.abort("blockedbyclient")

            async def _guard_websocket(ws_route) -> None:
                ws_url = str(ws_route.url or "")
                try:
                    checked_ws = await asyncio.to_thread(validate_public_websocket_url, ws_url)
                    if not browser_cross_origin_host_allowed(
                        checked_ws.host, browser_target.host, extra_trusted_hosts=booking_trusted_hosts
                    ):
                        raise NetworkTargetError(
                            "Untrusted cross-origin WebSocket destination blocked",
                            "UNTRUSTED_CROSS_ORIGIN",
                        )
                    await ws_route.connect_to_server()
                except Exception as exc:
                    await _record_blocked(ws_url, getattr(exc, "reason", str(exc)))
                    try:
                        await ws_route.close(code=1008, reason="Blocked by scanner network policy")
                    except Exception:
                        pass

            await context.route("**/*", _guard_route)
            if hasattr(context, "route_web_socket"):
                await context.route_web_socket("**/*", _guard_websocket)

            try:
                response = await page.goto(browser_target.url, wait_until="domcontentloaded", timeout=20000)
                results["browser_loaded"] = True
                results["browser_status_code"] = response.status if response else None

                try:
                    await page.wait_for_load_state("load", timeout=6000)
                except Exception:
                    # Dynamic apps can remain network-active indefinitely; allow bounded hydration.
                    await page.wait_for_timeout(1500)

                # Reveal lazy/footer sections before collecting visible-content evidence. This is
                # especially important for reviews, address, phone and policy links that may not be
                # rendered until the visitor moves down the page.
                await self._hydrate_lazy_content(page)
                if post_load_wait_ms and int(post_load_wait_ms) > 0:
                    await page.wait_for_timeout(max(0, min(5000, int(post_load_wait_ms))))

                ready_state = await page.evaluate("document.readyState")
                results["dom_complete"] = ready_state == "complete"
                results["title"] = await page.title()

                meta_desc = page.locator('meta[name="description"]').first
                results["meta_description"] = (
                    (await meta_desc.get_attribute("content")) or ""
                    if await meta_desc.count()
                    else ""
                )

                visible_text = await page.evaluate("document.body ? document.body.innerText : ''")
                visible_text = visible_text or ""
                results["page_text"] = visible_text
                results["visible_word_count"] = len(re.findall(r"\b\w+[\w'’-]*\b", visible_text))

                content_html = await page.content()
                results["page_html_length"] = len(content_html)
                results["page_content_len"] = len(content_html)  # legacy key; do not use for word count
                content_lower = content_html.lower()

                challenge_haystack = f"{results['title']}\n{visible_text[:12000]}\n{content_lower[:12000]}".lower()
                results["bot_challenge_suspected"] = (
                    results.get("browser_status_code") in {403, 429}
                    or any(pattern in challenge_haystack for pattern in BOT_CHALLENGE_PATTERNS)
                )

                # H1 evidence from rendered DOM and serialized source.
                h1_locator = page.locator("h1")
                h1_count = await h1_locator.count()
                h1_text: List[str] = []
                for idx in range(h1_count):
                    try:
                        text = (await h1_locator.nth(idx).inner_text()).strip()
                    except Exception:
                        text = ""
                    if text:
                        h1_text.append(text)
                source_h1_matches = H1_SOURCE_RE.findall(content_html)
                source_h1_text = [TAG_RE.sub(" ", item).strip() for item in source_h1_matches]

                results["h1_dom_count"] = h1_count
                results["h1_dom_text"] = h1_text
                results["h1_source_count"] = len(source_h1_matches)
                # Legacy field remains the rendered H1 text list.
                results["h1_tags"] = h1_text or [text for text in source_h1_text if text]

                if h1_count > 0 or len(source_h1_matches) > 0:
                    results["h1_status"] = "present"
                elif (
                    results["browser_loaded"]
                    and results["dom_complete"]
                    and not results["bot_challenge_suspected"]
                    and len(content_html) > 500
                ):
                    results["h1_status"] = "missing"
                else:
                    results["h1_status"] = "unknown"

                # Images / accessibility / lazy loading signals.
                images = page.locator("img")
                image_count = await images.count()
                missing_alt = 0
                with_alt = 0
                lazy_count = 0
                same_origin_content_images = 0
                origin = urllib.parse.urlparse(page.url).netloc.lower()
                for idx in range(image_count):
                    img = images.nth(idx)
                    alt = await img.get_attribute("alt")
                    aria = await img.get_attribute("aria-label")
                    aria_labelledby = await img.get_attribute("aria-labelledby")
                    role = (await img.get_attribute("role") or "").lower()
                    loading = (await img.get_attribute("loading") or "").lower()
                    src = await img.get_attribute("src") or ""
                    if alt is not None or aria or aria_labelledby or role in {"presentation", "none"}:
                        with_alt += 1
                    else:
                        missing_alt += 1
                    if loading == "lazy":
                        lazy_count += 1
                    if src:
                        src_host = urllib.parse.urlparse(urllib.parse.urljoin(page.url, src)).netloc.lower()
                        if src_host == origin and not re.search(r"logo|icon|favicon|sprite", src, re.I):
                            same_origin_content_images += 1

                results.update(
                    {
                        "image_count": image_count,
                        "total_images": image_count,
                        "missing_alt_images": missing_alt,
                        "images_with_alt": with_alt,
                        "lazy_image_count": lazy_count,
                        "custom_photography_signal": same_origin_content_images > 0,
                        # Same-origin imagery is only a signal, never proof that photography is original.
                        "custom_photography_status": "UNKNOWN",
                    }
                )
                if image_count == 0:
                    results["lazy_loading_status"] = "NOT_APPLICABLE"
                elif lazy_count > 0:
                    results["lazy_loading_status"] = "PASS"
                else:
                    results["lazy_loading_status"] = "UNKNOWN"

                # Metadata / technical document evidence.
                results["favicon_present"] = await page.locator(
                    'link[rel~="icon"], link[rel="shortcut icon"], link[rel="apple-touch-icon"]'
                ).count() > 0
                html_lang = await page.locator("html").get_attribute("lang")
                results["html_lang_present"] = bool((html_lang or "").strip())
                results["canonical_present"] = await page.locator('link[rel="canonical"][href]').count() > 0
                viewport_content = ""
                viewport = page.locator('meta[name="viewport"]').first
                if await viewport.count():
                    viewport_content = (await viewport.get_attribute("content")) or ""
                results["mobile_viewport_configured"] = bool(viewport_content.strip())

                schema_types = await self._extract_schema_types(page)
                results["schema_types"] = schema_types
                results["schema_present"] = bool(schema_types) or await page.locator(
                    '[itemscope], [typeof], script[type="application/ld+json"]'
                ).count() > 0

                # Analytics and tracking evidence. Recognize common alternatives so absence of GA4
                # alone does not become a false "no measurement" conclusion.
                measurement_platforms = self._detect_measurement_platforms(content_lower)
                results["measurement_platforms"] = measurement_platforms
                results["has_ga4"] = "Google Analytics / GTM" in measurement_platforms
                results["has_meta_pixel"] = "Meta Pixel" in measurement_platforms
                results["has_clarity"] = "Microsoft Clarity" in measurement_platforms
                results["has_hotjar"] = "Hotjar" in measurement_platforms
                results["has_qualitative_analytics"] = results["has_clarity"] or results["has_hotjar"]
                results["has_other_measurement"] = bool(set(measurement_platforms) - {"Google Analytics / GTM", "Meta Pixel", "Microsoft Clarity", "Hotjar"})
                results["measurement_layer_present"] = bool(measurement_platforms)
                results["retargeting_pixel_installed"] = results["has_meta_pixel"] or any(
                    marker in content_lower
                    for marker in ("googleadservices.com/pagead/conversion", "doubleclick.net", "aw-")
                )

                # Phone and instant-action evidence are separate facts.
                detected_phones = sorted(set(match.group(0).strip() for match in PHONE_RE.finditer(visible_text)))
                schema_phone = await page.evaluate(
                    """() => Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                    .map(s => s.textContent || '').some(t => /\"telephone\"\\s*:/i.test(t))"""
                )
                tel_count = await page.locator('a[href^="tel:"]').count()
                whatsapp_count = await page.locator('a[href*="wa.me"], a[href*="whatsapp.com"]').count()
                results["detected_phone_numbers"] = detected_phones
                results["phone_number_visible"] = bool(detected_phones) or bool(schema_phone)
                results["phone_visibility_status"] = "verified" if results["browser_loaded"] else "unknown"
                results["click_to_call_present"] = tel_count > 0
                results["click_to_call_status"] = "verified" if results["browser_loaded"] else "unknown"
                results["whatsapp_present"] = whatsapp_count > 0
                results["live_chat_present"] = self._detect_live_chat(content_lower, visible_text)

                # Forms: inspect architecture only. Do NOT submit forms or trigger irreversible actions.
                forms = page.locator("form")
                form_count = await forms.count()
                form_valid_flags: List[bool] = []
                form_field_counts: List[int] = []
                form_required_counts: List[int] = []
                unlinked_forms = 0
                for idx in range(form_count):
                    form = forms.nth(idx)
                    action = (await form.get_attribute("action") or "").strip()
                    meaningful_fields = form.locator(
                        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]), textarea, select'
                    )
                    field_count = await meaningful_fields.count()
                    required_count = await form.locator(
                        'input[required]:not([type="hidden"]), textarea[required], select[required], '
                        'input[aria-required="true"]:not([type="hidden"]), textarea[aria-required="true"], select[aria-required="true"]'
                    ).count()
                    has_inputs = field_count > 0
                    has_submit = await form.locator(
                        'button[type="submit"], input[type="submit"], button:not([type])'
                    ).count() > 0
                    # SPA forms often intentionally omit action; interactive inputs + submit is a valid architecture signal.
                    structurally_valid = bool(action) or (has_inputs and has_submit)
                    form_valid_flags.append(structurally_valid)
                    form_field_counts.append(field_count)
                    form_required_counts.append(required_count)
                    if not structurally_valid:
                        unlinked_forms += 1
                results["forms_present"] = form_count > 0
                results["form_action_valid"] = (
                    all(form_valid_flags) if form_valid_flags else None
                )
                results["form_field_counts"] = form_field_counts
                results["form_required_field_counts"] = form_required_counts
                results["form_min_field_count"] = min(form_field_counts) if form_field_counts else None
                results["form_max_field_count"] = max(form_field_counts) if form_field_counts else None
                results["form_max_required_field_count"] = max(form_required_counts) if form_required_counts else None
                results["form_functional_status"] = "UNKNOWN" if form_count > 0 else "NOT_APPLICABLE"
                results["form_payload_fired"] = False  # legacy field: intentionally no submission

                # CTA evidence before and after scroll.
                initial_actions = await self._collect_action_candidates(page)
                await page.evaluate("window.scrollBy(0, Math.min(700, document.body.scrollHeight || 700))")
                await page.wait_for_timeout(250)
                scrolled_actions = await self._collect_action_candidates(page)
                all_actions = self._dedupe_action_candidates(initial_actions + scrolled_actions)
                cta_types = sorted({a.get("type") for a in all_actions if a.get("type") and a.get("type") != "other"})
                sticky_actions = [a for a in scrolled_actions if a.get("sticky") and a.get("visible")]
                primary_actions = [a for a in all_actions if a.get("type") != "other" and a.get("visible")]
                results["mobile_primary_cta_present"] = bool(primary_actions)
                results["mobile_sticky_cta_present"] = bool(sticky_actions)
                results["mobile_cta_visible"] = results["mobile_sticky_cta_present"]  # legacy alias
                results["mobile_cta_status"] = "verified"
                results["mobile_cta_types"] = cta_types
                results["mobile_cta_type"] = cta_types[0] if cta_types else "unknown"
                results["mobile_cta_evidence"] = all_actions[:20]
                results["add_to_cart_visible"] = any(t in cta_types for t in ("add_to_cart", "buy"))
                results["order_online_present"] = "order" in cta_types
                results["reservation_present"] = "reserve" in cta_types
                results["booking_action_present"] = "book" in cta_types
                results["directions_present"] = "directions" in cta_types

                # Content / trust / navigation signals used only when observed.
                results.update(await self._collect_content_signals(page, visible_text, schema_types))
                dom_links = await page.locator("a[href]").evaluate_all(
                    "els => els.map(a => ({href:(a.href||''), text:(a.innerText||a.getAttribute('aria-label')||'')}))"
                )
                iframe_links = await page.locator("iframe[src]").evaluate_all(
                    "els => els.map(x => ({href:(x.src||''), text:(x.title||x.getAttribute('aria-label')||'')}))"
                )
                results["internal_links"] = self._same_origin_internal_links(page.url, dom_links)
                results["booking_provider_links"] = self._extract_booking_provider_links(page.url, dom_links + iframe_links)
                results["conversion_error_signals"] = self._detect_conversion_error_signals(visible_text, content_lower, page.url)
                results["conversion_path_error_detected"] = bool(results["conversion_error_signals"])
                if capture_evidence and results["conversion_error_signals"] and str(os.environ.get("TRILLOKA_EVIDENCE_SCREENSHOTS", "1")).lower() not in {"0", "false", "no"}:
                    try:
                        shot = await page.screenshot(type="jpeg", quality=45, full_page=False)
                        results["evidence_screenshot_mime"] = "image/jpeg"
                        results["evidence_screenshot_b64"] = base64.b64encode(shot).decode("ascii")
                        results["evidence_screenshot_sha256"] = hashlib.sha256(shot).hexdigest()
                    except Exception as shot_exc:
                        results["evidence_screenshot_error"] = str(shot_exc)[:180]
                results["checkout_form_field_count"] = (
                    results.get("form_max_field_count")
                    if results.get("checkout_context_detected")
                    else None
                )

                # AI/template-pattern heuristic: explicitly a pattern index, not authorship proof.
                ai_flags = await self._collect_template_flags(page)
                ai_flags["unlinked_forms"] = unlinked_forms
                ai_flags["has_retargeting_pixel"] = results["retargeting_pixel_installed"]
                ai_flags["has_custom_photos"] = results["custom_photography_signal"]
                results["ai_flags"] = ai_flags
                ai_score, ai_status = self._calculate_template_pattern_index(visible_text, ai_flags)
                results["ai_spectrum_pct"] = ai_score
                results["ai_spectrum_status"] = ai_status

                cms, cms_confidence = await self._detect_cms(page, content_lower)
                results["cms_platform"] = cms
                results["cms_confidence"] = cms_confidence

                # Security-blocked third-party resources can make negative rendered-DOM
                # observations incomplete. Keep every positive observation, but downgrade
                # browser-only CTA absence to PARTIAL so security hardening cannot manufacture
                # a false conversion leak. UNKNOWN earns no readiness points in the scorer.
                if int(results.get("browser_blocked_request_count") or 0) > 0:
                    results["browser_network_restricted"] = True
                    results["mobile_cta_status"] = "partial"
                    for key in (
                        "mobile_primary_cta_present", "mobile_sticky_cta_present",
                        "mobile_cta_visible", "add_to_cart_visible", "order_online_present",
                        "reservation_present", "booking_action_present", "directions_present",
                    ):
                        if results.get(key) is False:
                            results[key] = None

            except Exception as exc:
                results["browser_error"] = str(exc)
                print(f"[Hybrid Scanner] Playwright note for {url}: {exc}")
            finally:
                await browser.close()

        return results

    async def _extract_schema_types(self, page: Any) -> List[str]:
        raw_scripts: List[str] = await page.locator('script[type="application/ld+json"]').all_text_contents()
        found: List[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                item_type = value.get("@type")
                if isinstance(item_type, str):
                    found.append(item_type)
                elif isinstance(item_type, list):
                    found.extend(str(x) for x in item_type)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        for raw in raw_scripts:
            try:
                walk(json.loads(raw))
            except Exception:
                continue
        return sorted(set(x.strip() for x in found if str(x).strip()))

    @staticmethod
    def _detect_measurement_platforms(content_lower: str) -> List[str]:
        text = str(content_lower or "").lower()
        markers = (
            ("Google Analytics / GTM", ("googletagmanager.com/gtag/js", "googletagmanager.com/gtm.js", "google-analytics.com/analytics.js", "gtag(", "gtm-")),
            ("Meta Pixel", ("connect.facebook.net", "fbevents.js", "fbq(")),
            ("Microsoft Clarity", ("clarity.ms",)),
            ("Hotjar", ("hotjar.com", "static.hotjar.com")),
            ("Matomo", ("matomo.js", "matomo.php", "piwik.js", "piwik.php")),
            ("Plausible", ("plausible.io/js", "plausible.io/api/event")),
            ("Adobe Analytics", ("omtrdc.net", "assets.adobedtm.com", "adobedtm.com", "s_code.js", "alloy.min.js")),
            ("Segment", ("cdn.segment.com/analytics.js", "analytics.load(")),
            ("Mixpanel", ("cdn.mxpnl.com", "mixpanel.init(")),
            ("Amplitude", ("cdn.amplitude.com", "amplitude.init(", "amplitude.getinstance")),
            ("Heap", ("cdn.heapanalytics.com", "heap.load(")),
            ("HubSpot Analytics", ("js.hs-analytics.net", "js.hubspot.com/analytics")),
        )
        return [name for name, needles in markers if any(needle in text for needle in needles)]

    @staticmethod
    def _detect_live_chat(content_lower: str, visible_text: str) -> bool:
        haystack = f"{content_lower}\n{visible_text.lower()}"
        markers = (
            "intercom",
            "drift.com",
            "crisp.chat",
            "tawk.to",
            "livechatinc",
            "zendesk",
            "chat with us",
            "live chat",
        )
        return any(marker in haystack for marker in markers)

    async def _collect_action_candidates(self, page: Any) -> List[Dict[str, Any]]:
        return await page.evaluate(
            r"""() => {
                const classify = (text, href) => {
                    const label = String(text || '').toLowerCase().replace(/\s+/g, ' ').trim();
                    const rawHref = String(href || '').toLowerCase();
                    let path = rawHref;
                    try { path = decodeURIComponent(new URL(rawHref, location.href).pathname || '').toLowerCase(); } catch (e) {}
                    const hrefTokens = path.split(/[\/_?&=#.\-]+/).filter(Boolean).join(' ');
                    if (rawHref.startsWith('tel:') || /\bcall(?:\s+(?:now|us|today|restaurant))?\b/.test(label)) return 'call';
                    if (/\b(?:directions?|get directions)\b/.test(label) || rawHref.includes('maps.google') || rawHref.includes('google.com/maps')) return 'directions';
                    if (/\badd\s+to\s+(?:cart|bag)\b/.test(`${label} ${hrefTokens}`)) return 'add_to_cart';
                    if (/\b(?:checkout|buy\s+now|purchase\s+now|complete\s+purchase)\b/.test(label) || /(?:^|\s)checkout(?:\s|$)/.test(hrefTokens)) return 'buy';
                    if (/\b(?:order\s+(?:online|now|pickup|delivery)|start\s+(?:an?\s+)?order|place\s+(?:an?\s+)?order)\b/.test(label) || /(?:^|\s)(?:order online|online order)(?:\s|$)/.test(hrefTokens)) return 'order';
                    if (/\b(?:reserve(?:\s+(?:now|a\s+table|a\s+room|a\s+spot))?|make\s+(?:a\s+)?reservation|book\s+(?:a\s+)?(?:table|room|venue|tour|charter|cruise))\b/.test(label) || /(?:^|\s)reservations?(?:\s|$)/.test(hrefTokens)) return 'reserve';
                    if (/\b(?:book\s+(?:a\s+)?demo|request\s+(?:a\s+)?demo|schedule\s+(?:a\s+)?demo)\b/.test(label)) return 'demo';
                    if (/\b(?:book(?:\s+(?:now|online|appointment|consultation|a\s+consultation))?|schedule\s+(?:an?\s+)?(?:appointment|consultation))\b/.test(label) || /(?:^|\s)(?:book|booking|appointment|appointments)(?:\s|$)/.test(hrefTokens)) return 'book';
                    if (/\b(?:get|request|receive)\s+(?:a\s+)?(?:free\s+)?quote\b|\b(?:free\s+)?estimate\b/.test(label) || /(?:^|\s)(?:quote|estimate)(?:\s|$)/.test(hrefTokens)) return 'quote';
                    if (/\b(?:start\s+(?:a\s+)?(?:free\s+)?trial|free\s+trial|try\s+free)\b/.test(label)) return 'trial';
                    if (/\b(?:subscribe|join\s+(?:the\s+)?(?:list|newsletter|community)|sign\s+up\s+for\s+(?:the\s+)?newsletter)\b/.test(label)) return 'subscribe';
                    if (/\b(?:contact(?:\s+us)?|get\s+in\s+touch|send\s+(?:us\s+)?a\s+message)\b/.test(label) || /(?:^|\s)contact(?:\s|$)/.test(hrefTokens)) return 'contact';
                    if (/\b(?:live\s+chat|chat\s+(?:now|with\s+us)|whatsapp)\b/.test(label) || rawHref.includes('wa.me') || rawHref.includes('whatsapp.com')) return 'chat';
                    return 'other';
                };
                const elements = Array.from(document.querySelectorAll('a, button, [role="button"]'));
                return elements.map(el => {
                    const style = getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const href = el.getAttribute('href') || '';
                    const text = (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 160);
                    const visible = rect.width > 0 && rect.height > 0 &&
                        style.display !== 'none' && style.visibility !== 'hidden' &&
                        parseFloat(style.opacity || '1') > 0.05;
                    const sticky = style.position === 'fixed' || style.position === 'sticky';
                    const inViewport = rect.bottom >= 0 && rect.top <= window.innerHeight &&
                        rect.right >= 0 && rect.left <= window.innerWidth;
                    return {
                        text, href, visible: visible && inViewport, sticky,
                        type: classify(text, href),
                        x: Math.round(rect.x), y: Math.round(rect.y),
                        width: Math.round(rect.width), height: Math.round(rect.height)
                    };
                }).filter(x => x.visible && (x.type !== 'other' || x.sticky));
            }"""
        )

    @staticmethod
    def _dedupe_action_candidates(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[Any, ...]] = set()
        output: List[Dict[str, Any]] = []
        for item in items:
            key = (item.get("text"), item.get("href"), item.get("type"), item.get("sticky"))
            if key not in seen:
                seen.add(key)
                output.append(item)
        return output

    async def _collect_content_signals(
        self, page: Any, visible_text: str, schema_types: List[str]
    ) -> Dict[str, Any]:
        text_lower = visible_text.lower()
        links = await page.locator("a[href]").evaluate_all(
            "els => els.map(a => ({text:(a.innerText||a.getAttribute('aria-label')||'').trim().toLowerCase(), href:(a.href||'').toLowerCase()}))"
        )
        hrefs = [str(item.get("href") or "") for item in links]
        link_text = [str(item.get("text") or "") for item in links]
        schema_lower = " ".join(schema_types).lower()

        address_visible = bool(
            re.search(
                r"\b\d{1,6}\s+[a-z0-9.'’\- ]+\s(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|drive|dr\.?|lane|ln\.?|way|highway|hwy\.?|place|pl\.?|court|ct\.?)\b",
                text_lower,
                re.I,
            )
            or any("maps.google" in href or "google.com/maps" in href for href in hrefs)
            or "postaladdress" in schema_lower
        )
        credential_signal_types = self._detect_credential_signals(visible_text, links, schema_types)
        trust_badges = bool(credential_signal_types)
        reviews_visible = bool(
            "aggregaterating" in schema_lower
            or re.search(
                r"\b(testimonials?|customer reviews?|client reviews?|google reviews?|reviews?)\b",
                text_lower,
            )
        )
        guarantee_refund = bool(re.search(r"\b(money[- ]back|refund policy|satisfaction guarantee|guaranteed)\b", text_lower))
        about_team = any(re.search(r"\b(about|our team|team|our story|who we are)\b", text) for text in link_text)
        faq = "faqpage" in schema_lower or bool(re.search(r"\b(frequently asked questions|faqs?)\b", text_lower))
        case_studies = any(re.search(r"\b(case studies|portfolio|our work|projects|success stories)\b", text) for text in link_text)
        blog = any(re.search(r"\b(blog|insights|resources|articles|news)\b", text) for text in link_text)
        social = any(any(domain in href for domain in SOCIAL_DOMAINS) for href in hrefs)
        privacy = any("privacy" in text or "/privacy" in href for text, href in zip(link_text, hrefs))
        terms = any(
            re.search(r"\bterms\b", text) or "/terms" in href or "terms-of" in href
            for text, href in zip(link_text, hrefs)
        )
        cookie_banner = bool(
            re.search(r"\b(cookie settings|cookie preferences|accept cookies|manage cookies)\b", text_lower)
            or await page.locator('[class*="cookie"], [id*="cookie"], [class*="consent"], [id*="consent"]').count() > 0
        )

        current_url = str(page.url or "").lower()
        checkout_context = bool(
            re.search(r"/(?:cart|checkout)(?:/|\?|$)", current_url)
            or re.search(r"\b(cart|checkout|order summary|payment method|shipping address|billing address)\b", text_lower)
        )
        guest_checkout_available = (
            True
            if checkout_context and re.search(r"\b(guest checkout|continue as guest|checkout as guest)\b", text_lower)
            else (
                False
                if checkout_context and re.search(
                    r"\b(create an account|sign in to checkout|login to checkout|register to checkout)\b",
                    text_lower,
                )
                else None
            )
        )
        late_cost_disclosure_risk = bool(
            checkout_context
            and re.search(
                r"\b(shipping|tax(?:es)?|fees?)\s+(?:will be\s+)?calculated at checkout\b|\bcalculated at checkout\b",
                text_lower,
            )
        )
        delivery_date_visible = (
            bool(re.search(r"\b(arrives? by|delivery by|estimated delivery|delivery date|delivers? on)\b", text_lower))
            if checkout_context
            else None
        )
        shipping_info_linked = any(
            re.search(r"\b(shipping|delivery)\b", text)
            or re.search(r"/(?:shipping|delivery)(?:/|\?|$)", href)
            for text, href in zip(link_text, hrefs)
        )
        return_policy_linked = any(
            re.search(r"\b(return|refund)\b", text)
            or re.search(r"/(?:returns?|refunds?)(?:/|\?|$)", href)
            for text, href in zip(link_text, hrefs)
        )
        pricing_linked = any(
            re.search(r"\b(pricing|plans?|packages?)\b", text)
            or re.search(r"/(?:pricing|plans?|packages?)(?:/|\?|$)", href)
            for text, href in zip(link_text, hrefs)
        )
        plan_matrix_signal = bool(
            len(re.findall(r"(?:\$|€|£)\s*\d+(?:[.,]\d+)?", visible_text)) >= 2
            and re.search(r"\b(month|monthly|year|yearly|annual|plan|tier)\b", text_lower)
        )
        media_preview_count = await page.locator(
            'img[alt*="dashboard" i], img[alt*="interface" i], img[alt*="screenshot" i], '
            'img[src*="dashboard" i], img[src*="screenshot" i], video, [aria-label*="product tour" i]'
        ).count()
        product_ui_preview_signal = bool(
            re.search(r"\b(dashboard|interface|product tour|app preview|software screenshot|see it in action)\b", text_lower)
            or media_preview_count > 0
        )

        bylines = bool(
            await page.locator('[rel="author"], [class*="author"], [itemprop="author"]').count() > 0
            or re.search(r"(?:^|\n)\s*by\s+[A-Z][A-Za-z.'’\-]+(?:\s+[A-Z][A-Za-z.'’\-]+)+", visible_text)
        )
        publication_dates = bool(
            await page.locator('time[datetime], meta[property="article:published_time"], [itemprop="datePublished"]').count() > 0
        )
        return {
            "address_location_visible": address_visible,
            "trust_badges_present": trust_badges,
            "credential_signals_present": bool(credential_signal_types),
            "credential_signal_types": credential_signal_types,
            "reviews_visible": reviews_visible,
            "guarantee_refund_present": guarantee_refund,
            "about_team_linked": about_team,
            "social_proof_present": reviews_visible or trust_badges or case_studies,
            "faq_present": faq,
            "case_studies_portfolio_present": case_studies,
            "blog_present": blog,
            "social_links_present": social,
            "privacy_policy_linked": privacy,
            "terms_linked": terms,
            "privacy_terms_linked": privacy and terms,
            "cookie_banner_present": cookie_banner,
            "checkout_context_detected": checkout_context,
            "guest_checkout_available": guest_checkout_available,
            "late_cost_disclosure_risk": late_cost_disclosure_risk,
            "delivery_date_visible": delivery_date_visible,
            "shipping_info_linked": shipping_info_linked,
            "return_policy_linked": return_policy_linked,
            "pricing_linked": pricing_linked,
            "plan_matrix_signal": plan_matrix_signal,
            "product_ui_preview_signal": product_ui_preview_signal,
            "author_bylines_present": bylines,
            "publication_dates_visible": publication_dates,
        }

    async def _collect_template_flags(self, page: Any) -> Dict[str, Any]:
        return await page.evaluate(
            """() => {
                const all = Array.from(document.querySelectorAll('*'));
                let tailwind = 0;
                all.forEach(el => {
                    const cls = typeof el.className === 'string' ? el.className : '';
                    if (/\\b(flex|grid|bg-\\w+|text-\\w+|p-\\d+|m-\\d+|rounded|shadow|border|hover:|md:|lg:)\\b/.test(cls)) tailwind++;
                });
                const svgs = Array.from(document.querySelectorAll('svg'));
                const lucide = svgs.filter(svg => (svg.outerHTML || '').includes('lucide')).length;
                const headings = Array.from(document.querySelectorAll('h1,h2,h3')).map(h => h.innerText || '');
                const generic = [
                    /empowering.*business/i, /next-gen/i, /unlock.*potential/i,
                    /transform.*digital/i, /innovative solutions/i,
                    /streamline.*workflow/i, /leverage.*power/i,
                    /cutting-edge/i, /seamless.*experience/i
                ].some(p => headings.some(h => p.test(h)));
                return {
                    tailwind_classes: tailwind,
                    shadcn_markers: document.querySelectorAll('[data-slot], [class*="shadcn"]').length > 0,
                    lucide_icons: lucide,
                    generic_headline: generic,
                    unlinked_forms: 0,
                    has_custom_photos: false,
                    has_retargeting_pixel: false
                };
            }"""
        )

    def _calculate_template_pattern_index(self, text: str, flags: Dict[str, Any]) -> Tuple[Optional[float], str]:
        text = (text or "").strip()
        score = 0.0
        evidence_count = 0

        # Tooling signals increase template-pattern likelihood, not AI authorship probability.
        if flags.get("tailwind_classes", 0) > 20:
            score += 12.0
            evidence_count += 1
        if flags.get("shadcn_markers"):
            score += 10.0
            evidence_count += 1
        if flags.get("lucide_icons", 0) > 5:
            score += 6.0
            evidence_count += 1
        if flags.get("generic_headline"):
            score += 15.0
            evidence_count += 1
        if flags.get("unlinked_forms", 0) > 0:
            score += 5.0
            evidence_count += 1

        text_score = self._analyze_text_template_patterns(text)
        if text_score > 0:
            score += text_score
            evidence_count += 1

        if len(text) < 100 and evidence_count == 0:
            return None, "unknown"
        return round(max(0.0, min(100.0, score)), 1), "heuristic"

    @staticmethod
    def _analyze_text_template_patterns(text: str) -> float:
        if not text or len(text.strip()) < 100:
            return 0.0
        lower = text.lower()
        buzzwords = (
            "in today's digital",
            "testament to",
            "delve into",
            "seamless integration",
            "elevate your",
            "unlock your potential",
            "beacon of",
            "crucial to understand",
            "cutting-edge",
            "transformative",
            "revolutionary",
        )
        hits = sum(1 for phrase in buzzwords if phrase in lower)
        score = min(18.0, hits * 3.0)

        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.split()) >= 4]
        if len(sentences) >= 8:
            lengths = [len(s.split()) for s in sentences]
            avg = sum(lengths) / len(lengths)
            variance = sum((n - avg) ** 2 for n in lengths) / len(lengths)
            if variance < 12:
                score += 6.0
        return score

    async def _detect_cms(self, page: Any, content_lower: str) -> Tuple[str, str]:
        generator = page.locator('meta[name="generator"]').first
        generator_value = ""
        if await generator.count():
            generator_value = ((await generator.get_attribute("content")) or "").strip()
        gen_lower = generator_value.lower()

        signals = [content_lower, gen_lower]
        joined = "\n".join(signals)
        checks = (
            ("WordPress", ("wp-content", "wp-includes", "wordpress")),
            ("Shopify", ("cdn.shopify.com", "myshopify", "shopify")),
            ("Wix", ("wixstatic.com", "wix.com", "wix")),
            ("Squarespace", ("static1.squarespace.com", "squarespace")),
            ("Webflow", ("webflow.js", "webflow.css", "webflow")),
            ("Next.js", ("/_next/", "__next_data__", "next.js")),
        )
        for name, markers in checks:
            hits = sum(marker in joined for marker in markers)
            if hits >= 2 or (hits == 1 and generator_value):
                return name, "high"
            if hits == 1:
                return name, "medium"

        if await page.locator("#root, #app").count() > 0 and await page.locator("script[src]").count() > 2:
            return "Modern JavaScript Stack", "low"
        return "Not confidently identified", "low"

    def _classify_business(self, data: Dict[str, Any], requested_hint: str = "auto") -> Dict[str, Any]:
        """Backward-compatible wrapper around the journey + context architecture model."""
        return infer_architecture_profile(data, requested_hint)

    @staticmethod
    def _conversion_model(vertical: str, cta_types: set[str]) -> Tuple[str, List[str]]:
        # Legacy helper retained for import/runtime compatibility. New scoring uses architecture_profile.
        profile = infer_architecture_profile({"mobile_cta_types": list(cta_types or [])}, vertical)
        return str(profile.get("primary_conversion") or "primary_site_action"), list(profile.get("secondary_conversions") or ["contact"])

    @staticmethod
    def _assess_h1_relevance(data: Dict[str, Any], profile: Dict[str, Any]) -> str:
        """Conservative topic-alignment check independent of industry taxonomy.

        The H1 only receives PASS when it shares meaningful terms with the title/meta or with the
        inferred journey signals. Lack of overlap stays UNKNOWN rather than becoming a penalty.
        """
        if data.get("h1_status") != "present":
            return "UNKNOWN"
        h1 = " ".join(data.get("h1_tags") or []).lower().strip()
        if not h1 or (HybridScanner._to_float(profile.get("confidence")) or 0.0) < 0.60:
            return "UNKNOWN"
        supporting = " ".join([
            str(data.get("title") or ""), str(data.get("meta_description") or ""),
            " ".join(str(x) for x in (profile.get("journey_signals") or []) if x),
        ]).lower()
        stop = {"the","and","for","with","your","our","from","that","this","you","are","to","of","in","a","an","on","at","by","is"}
        h1_tokens = {x for x in re.findall(r"[a-z0-9]+", h1) if len(x) >= 4 and x not in stop}
        support_tokens = {x for x in re.findall(r"[a-z0-9]+", supporting) if len(x) >= 4 and x not in stop}
        if h1_tokens and len(h1_tokens & support_tokens) >= 1:
            return "PASS"
        return "UNKNOWN"

    def _build_scan_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        browser_loaded = bool(data.get("browser_loaded"))
        dom_complete = bool(data.get("dom_complete"))
        response_ok = bool(data.get("response_ok"))
        challenge = bool(data.get("bot_challenge_suspected") or data.get("http_bot_challenge_suspected"))
        pagespeed_available = data.get("pagespeed_api_status") == "success"
        crux_available = bool(data.get("crux_available"))
        browser_blocked_request_count = int(data.get("browser_blocked_request_count") or 0)
        browser_network_restricted = browser_blocked_request_count > 0

        if browser_loaded and not challenge and (dom_complete or response_ok):
            confidence = "high" if response_ok and dom_complete else "medium"
        elif browser_loaded and not challenge:
            confidence = "medium"
        else:
            confidence = "low"
        if browser_network_restricted and confidence == "high":
            confidence = "medium"

        return {
            "http_ok": response_ok,
            "browser_loaded": browser_loaded,
            "dom_complete": dom_complete,
            "bot_challenge_suspected": challenge,
            "pagespeed_available": pagespeed_available,
            "crux_available": crux_available,
            "browser_network_restricted": browser_network_restricted,
            "browser_blocked_request_count": browser_blocked_request_count,
            "confidence": confidence,
        }

    @staticmethod
    def _evidence_coverage(data: Dict[str, Any]) -> Dict[str, Any]:
        document_verified = bool(data.get("browser_loaded") or data.get("static_html_verified"))
        evidence_fields = {
            "http": data.get("status_code") not in (None, 0),
            "document": document_verified,
            "h1": data.get("h1_status") in {"present", "missing"},
            "cta": data.get("mobile_cta_status") == "verified",
            "phone": data.get("phone_visibility_status") == "verified",
            "technical": str(data.get("technical_evidence_status") or "").lower() == "verified",
            "content": str(data.get("content_signal_status") or "").lower() == "verified",
            "tracking": str(data.get("tracking_evidence_status") or "").lower() == "verified",
            "images": str(data.get("image_evidence_status") or "").lower() == "verified",
            "forms": str(data.get("form_evidence_status") or "").lower() == "verified",
            "journey": str(data.get("journey_evidence_status") or "").lower() == "verified",
            "pagespeed": data.get("pagespeed_api_status") == "success",
            "crux": bool(data.get("crux_available")),
        }
        verified = sum(bool(v) for v in evidence_fields.values())
        return {
            "verified_groups": verified,
            "total_groups": len(evidence_fields),
            "ratio": round(verified / len(evidence_fields), 2),
            "groups": evidence_fields,
        }


def collect_scan_data(domain: str, business_type: str = "auto") -> Dict[str, Any]:
    """Backward-compatible synchronous helper."""
    import asyncio

    return asyncio.run(HybridScanner().execute_hybrid_scan(domain, business_type=business_type))
