"""Trilloka production scanning engine.

Single source of truth for HTTP, Google telemetry, mobile DOM evidence,
business classification and confidence-aware scanner facts.

V4 evidence consensus hardening:
- Positive evidence from any reliable source cannot be erased by a weaker negative pass.
- Negative visible-content claims require a complete rendered DOM when static HTML alone is inconclusive.
- Mobile/desktop browser retries are merged by evidence consensus, not last-writer wins.
- Ambiguous HTTP->HTTPS checks remain UNKNOWN instead of becoming false failures.

Backward compatibility:
- Keeps legacy keys used by the existing scorer/frontend.
- Adds evidence/status fields; it does not remove public fields.
- Unknown telemetry is represented explicitly and is never converted into a failure.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from playwright.async_api import async_playwright


PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4}(?!\d)")
H1_SOURCE_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1\s*>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

BOT_CHALLENGE_PATTERNS = (
    "checking your browser",
    "verify you are human",
    "attention required",
    "access denied",
    "captcha",
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
        if tag == "form":
            form = {"action": a.get("action", ""), "has_inputs": False, "has_submit": False}
            self._form_stack.append(form)
            self.forms.append(form)
        if self._form_stack and tag in {"input", "textarea", "select"}:
            self._form_stack[-1]["has_inputs"] = True
            if tag == "input" and a.get("type", "").lower() == "submit":
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
    ENGINE_VERSION = "v5"
    """Three-phase scanner with evidence confidence and business context."""

    def __init__(self, google_api_key: Optional[str] = None):
        self.google_api_key = (
            google_api_key
            or os.environ.get("PAGESPEED_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TrillokaBot/2.0 Revenue Architecture Auditor"})

    async def execute_hybrid_scan(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
        """Run HTTP, Google and mobile-browser evidence collection."""
        url = self._normalize_url(target_domain)

        http_meta = self._fast_http_preflight(url)
        raw_html = str(http_meta.pop("_http_html", "") or "")
        static_meta = self._extract_static_html_evidence(
            raw_html,
            http_meta.get("final_url") or url,
            verified=bool(http_meta.get("response_ok")),
        )
        site_files = self._fetch_site_files(http_meta.get("final_url") or url)
        pagespeed_meta = self._fetch_google_pagespeed(http_meta.get("final_url") or url)
        crux_meta = self._fetch_crux_telemetry(http_meta.get("final_url") or url)
        places_meta = self._fetch_google_places(target_domain, business_name)

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

        business_profile = self._classify_business(combined)
        combined["business_profile"] = business_profile
        combined["h1_relevance_status"] = self._assess_h1_relevance(combined, business_profile)

        combined["scan_quality"] = self._build_scan_quality(combined)
        combined["evidence_coverage"] = self._evidence_coverage(combined)
        combined["scanner_engine_version"] = self.ENGINE_VERSION
        return combined

    @staticmethod
    def _normalize_url(target_domain: str) -> str:
        value = (target_domain or "").strip()
        if not value:
            raise ValueError("Target domain is required")
        if value.startswith(("http://", "https://")):
            return value
        return f"https://{value}"

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
            response = self.session.get(url, timeout=(5, 12), allow_redirects=True)
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
            response = self.session.get(http_url, timeout=(4, 8), allow_redirects=True)
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
            robots = self.session.get(f"{origin}/robots.txt", timeout=(4, 8), allow_redirects=True)
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
                sitemap = self.session.get(candidate, timeout=(4, 8), allow_redirects=True)
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
            response = self.session.get(endpoint, timeout=(5, 20))
            if response.status_code != 200:
                unavailable["pagespeed_error"] = f"HTTP {response.status_code}"
                return unavailable

            data = response.json()
            lighthouse = data.get("lighthouseResult") or {}
            categories = lighthouse.get("categories") or {}
            audits = lighthouse.get("audits") or {}

            def category_score(name: str) -> Optional[float]:
                raw = (categories.get(name) or {}).get("score")
                return round(float(raw) * 100, 1) if raw is not None else None

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
        return float(audit.get("score")) >= 0.9

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
                cls_float = float(cls_value) if cls_value is not None else None
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
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

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

    def _fetch_google_places(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
        if not self.google_api_key:
            return {"places_found": False, "places_confidence": "unknown"}

        query = business_name.strip() if business_name else target_domain.replace("https://", "").replace("http://", "").split("/")[0]
        endpoint = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.google_api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount",
        }
        try:
            response = self.session.post(endpoint, json={"textQuery": query}, headers=headers, timeout=(4, 12))
            if response.status_code == 200:
                places = response.json().get("places") or []
                if places:
                    place = places[0]
                    return {
                        "places_found": True,
                        "places_confidence": "medium",
                        "place_id": place.get("id"),
                        "place_display_name": (place.get("displayName") or {}).get("text", ""),
                        "google_rating": place.get("rating"),
                        "google_review_count": place.get("userRatingCount"),
                        # Do not manufacture review-photo evidence from a field we did not request.
                        "has_visual_review_proof": None,
                    }
        except Exception as exc:
            print(f"[Hybrid Scanner] Places API error: {exc}")
        return {"places_found": False, "places_confidence": "unknown"}

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
        for action in probe.actions:
            href = urllib.parse.urljoin(url, str(action.get("href") or ""))
            links.append({"href": href.lower(), "text": str(action.get("text") or "").lower()})
        for link in probe.links:
            href = urllib.parse.urljoin(url, str(link.get("href") or ""))
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
        for form in probe.forms:
            structurally_valid = bool(str(form.get("action") or "").strip()) or bool(
                form.get("has_inputs") and form.get("has_submit")
            )
            form_valid_flags.append(structurally_valid)
            if not structurally_valid:
                unlinked_forms += 1

        action_types = sorted(
            {
                self._classify_action_text(str(item.get("text") or ""), str(item.get("href") or ""))
                for item in probe.actions
            }
            - {"other"}
        )

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

        has_ga4 = any(marker in html_lower for marker in ("googletagmanager.com/gtag/js", "gtag(", "gtm.js", "gtm-"))
        has_meta_pixel = any(marker in html_lower for marker in ("connect.facebook.net", "fbevents.js", "fbq("))
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
                "has_clarity": "clarity.ms" in html_lower,
                "has_hotjar": "hotjar.com" in html_lower or "static.hotjar.com" in html_lower,
                "has_ga4": has_ga4,
                "has_meta_pixel": has_meta_pixel,
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
                "reservation_present": "reserve" in action_types or "book" in action_types,
                "directions_present": "directions" in action_types,
                "ai_flags": ai_flags,
                "ai_spectrum_pct": ai_score,
                "ai_spectrum_status": ai_status,
                "cms_platform": cms,
                "cms_confidence": cms_confidence,
                **content_signals,
            }
        )
        results["has_qualitative_analytics"] = bool(results["has_clarity"] or results["has_hotjar"])
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
        value = f"{text} {href}".lower()
        patterns = (
            (r"add\s*to\s*(?:cart|bag)", "add_to_cart"),
            (r"buy\s*now|checkout|purchase", "buy"),
            (r"order\s*(?:online|now)?|pickup|delivery", "order"),
            (r"reserve|reservation", "reserve"),
            (r"book\s*(?:now|appointment|consultation)?", "book"),
            (r"tel:|call\s*(?:now|us|restaurant)?", "call"),
            (r"directions|maps\.google|google\.com/maps", "directions"),
            (r"get\s*a?\s*quote|request\s*quote|estimate", "quote"),
            (r"start\s*(?:free\s*)?trial|free\s*trial", "trial"),
            (r"book\s*demo|request\s*demo|demo", "demo"),
            (r"contact\s*(?:us)?|get\s*in\s*touch", "contact"),
            (r"chat|whatsapp|wa\.me", "chat"),
        )
        for pattern, action_type in patterns:
            if re.search(pattern, value, re.I):
                return action_type
        return "other"

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
        trust_badges = bool(re.search(r"\b(verified|secure checkout|bbb accredited|trustpilot|licensed|insured|certified)\b", text_lower))
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
        bylines = bool(
            probe.has_author_markup
            or re.search(r"(?:^|\n|\s)by\s+[A-Z][A-Za-z.'’\-]+(?:\s+[A-Z][A-Za-z.'’\-]+)+", visible_text)
        )
        return {
            "address_location_visible": address_visible,
            "trust_badges_present": trust_badges,
            "reviews_visible": reviews_visible,
            "guarantee_refund_present": guarantee_refund,
            "about_team_linked": about_team,
            "social_proof_present": reviews_visible or trust_badges,
            "faq_present": faq,
            "case_studies_portfolio_present": case_studies,
            "blog_present": blog,
            "social_links_present": social,
            "privacy_policy_linked": privacy,
            "terms_linked": terms,
            "privacy_terms_linked": privacy and terms,
            "cookie_banner_present": cookie_banner,
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
            merged["h1_dom_count"] = max(int(first.get("h1_dom_count") or 0), int(second.get("h1_dom_count") or 0))
            merged["h1_source_count"] = max(int(first.get("h1_source_count") or 0), int(second.get("h1_source_count") or 0))
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
            "has_ga4", "has_meta_pixel", "retargeting_pixel_installed", "forms_present",
            "address_location_visible", "trust_badges_present", "reviews_visible",
            "guarantee_refund_present", "about_team_linked", "social_proof_present",
            "faq_present", "case_studies_portfolio_present", "blog_present", "social_links_present",
            "privacy_policy_linked", "terms_linked", "privacy_terms_linked", "cookie_banner_present",
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
        if str(mobile_attempt.get("mobile_cta_status") or "unknown") == "verified":
            for key in (
                "mobile_cta_visible", "mobile_primary_cta_present", "mobile_sticky_cta_present",
                "mobile_cta_status", "mobile_cta_type", "mobile_cta_types", "mobile_cta_evidence",
                "add_to_cart_visible", "order_online_present", "reservation_present", "directions_present",
            ):
                merged[key] = mobile_attempt.get(key)
        else:
            merged["mobile_cta_status"] = "unknown"
            merged["mobile_sticky_cta_present"] = False
            merged["mobile_cta_visible"] = False

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
            merged["h1_source_count"] = max(int(static.get("h1_source_count") or 0), int(dom.get("h1_source_count") or 0))
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
            merged["page_html_length"] = max(int(static.get("page_html_length") or 0), int(dom.get("page_html_length") or 0))
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
        if merged["schema_types"]:
            merged["schema_present"] = True

        # Visible/trust/contact signals: any positive source wins. A raw-HTML miss by itself is not
        # enough to fail because client-rendered/lazy content may not exist in the initial source.
        visible_presence_keys = (
            "address_location_visible", "trust_badges_present", "reviews_visible",
            "guarantee_refund_present", "about_team_linked", "social_proof_present",
            "faq_present", "case_studies_portfolio_present", "blog_present", "social_links_present",
            "privacy_policy_linked", "terms_linked", "privacy_terms_linked", "cookie_banner_present",
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
            "has_clarity", "has_hotjar", "has_qualitative_analytics", "has_ga4",
            "has_meta_pixel", "retargeting_pixel_installed",
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

        # Mobile CTA evidence remains browser/mobile-only; raw HTML cannot prove visibility/stickiness.
        if str(dom.get("mobile_cta_status") or "unknown") == "verified":
            for key in (
                "mobile_cta_visible", "mobile_primary_cta_present", "mobile_sticky_cta_present",
                "mobile_cta_status", "mobile_cta_type", "mobile_cta_types", "mobile_cta_evidence",
                "add_to_cart_visible", "order_online_present", "reservation_present", "directions_present",
            ):
                merged[key] = dom.get(key)

        # Images: rendered DOM is preferred when available; otherwise keep complete static evidence.
        if int(dom.get("total_images") or 0) > 0 or (dom_complete and dom.get("missing_alt_images") is not None):
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
            "directions_present": False,
            "whatsapp_present": False,
            "live_chat_present": False,
            "form_payload_fired": False,
            "forms_present": False,
            "form_action_valid": None,
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
            "author_bylines_present": None,
            "publication_dates_visible": None,
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
            height = int((metrics or {}).get("height") or 0)
            viewport = max(1, int((metrics or {}).get("viewport") or 800))
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

    async def _run_targeted_playwright(self, url: str, psi_data: Dict[str, Any], mode: str = "mobile") -> Dict[str, Any]:
        results = self._empty_dom_meta()
        audits = (psi_data.get("lighthouseResult") or {}).get("audits") or {}
        tap_items = ((audits.get("tap-targets") or {}).get("details") or {}).get("items")
        if isinstance(tap_items, list):
            results["tap_targets_flagged"] = [
                ((item.get("node") or {}).get("selector"))
                for item in tap_items
                if ((item.get("node") or {}).get("selector"))
            ]

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
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
            context = await browser.new_context(viewport=viewport, user_agent=user_agent)
            results["browser_mode"] = mode
            page = await context.new_page()

            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
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

                # Analytics and tracking evidence.
                results["has_clarity"] = "clarity.ms" in content_lower
                results["has_hotjar"] = "hotjar.com" in content_lower or "static.hotjar.com" in content_lower
                results["has_qualitative_analytics"] = results["has_clarity"] or results["has_hotjar"]
                results["has_ga4"] = any(
                    marker in content_lower
                    for marker in ("googletagmanager.com/gtag/js", "gtag(", "gtm.js", "gtm-")
                )
                results["has_meta_pixel"] = any(
                    marker in content_lower for marker in ("connect.facebook.net", "fbevents.js", "fbq(")
                )
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
                unlinked_forms = 0
                for idx in range(form_count):
                    form = forms.nth(idx)
                    action = (await form.get_attribute("action") or "").strip()
                    has_inputs = await form.locator("input, textarea, select").count() > 0
                    has_submit = await form.locator(
                        'button[type="submit"], input[type="submit"], button:not([type])'
                    ).count() > 0
                    # SPA forms often intentionally omit action; interactive inputs + submit is a valid architecture signal.
                    structurally_valid = bool(action) or (has_inputs and has_submit)
                    form_valid_flags.append(structurally_valid)
                    if not structurally_valid:
                        unlinked_forms += 1
                results["forms_present"] = form_count > 0
                results["form_action_valid"] = (
                    all(form_valid_flags) if form_valid_flags else None
                )
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
                results["reservation_present"] = "reserve" in cta_types or "book" in cta_types
                results["directions_present"] = "directions" in cta_types

                # Content / trust / navigation signals used only when observed.
                results.update(await self._collect_content_signals(page, visible_text, schema_types))

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
            """() => {
                const classify = (text, href) => {
                    const value = `${text || ''} ${href || ''}`.toLowerCase();
                    if (/add\\s*to\\s*cart|add\\s*to\\s*bag/.test(value)) return 'add_to_cart';
                    if (/buy\\s*now|checkout|purchase/.test(value)) return 'buy';
                    if (/order\\s*(online|now)?|pickup|delivery/.test(value)) return 'order';
                    if (/reserve|reservation/.test(value)) return 'reserve';
                    if (/book\\s*(now|appointment|consultation)?/.test(value)) return 'book';
                    if (/tel:|call\\s*(now|us|restaurant)?/.test(value)) return 'call';
                    if (/directions|maps\\.google|google\\.com\\/maps/.test(value)) return 'directions';
                    if (/get\\s*a?\\s*quote|request\\s*quote|estimate/.test(value)) return 'quote';
                    if (/start\\s*(free\\s*)?trial|free\\s*trial/.test(value)) return 'trial';
                    if (/book\\s*demo|request\\s*demo|demo/.test(value)) return 'demo';
                    if (/contact\\s*(us)?|get\\s*in\\s*touch/.test(value)) return 'contact';
                    if (/chat|whatsapp|wa\\.me/.test(value)) return 'chat';
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
        trust_badges = bool(
            re.search(r"\b(verified|secure checkout|bbb accredited|trustpilot|licensed|insured|certified)\b", text_lower)
        )
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
            "reviews_visible": reviews_visible,
            "guarantee_refund_present": guarantee_refund,
            "about_team_linked": about_team,
            "social_proof_present": reviews_visible or trust_badges,
            "faq_present": faq,
            "case_studies_portfolio_present": case_studies,
            "blog_present": blog,
            "social_links_present": social,
            "privacy_policy_linked": privacy,
            "terms_linked": terms,
            "privacy_terms_linked": privacy and terms,
            "cookie_banner_present": cookie_banner,
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

    def _classify_business(self, data: Dict[str, Any]) -> Dict[str, Any]:
        text = " ".join(
            [
                str(data.get("title") or ""),
                str(data.get("meta_description") or ""),
                " ".join(data.get("h1_tags") or []),
                str(data.get("page_text") or "")[:20000],
                " ".join(data.get("schema_types") or []),
                " ".join(data.get("mobile_cta_types") or []),
            ]
        ).lower()

        rules: Dict[str, Tuple[str, ...]] = {
            "restaurant": (
                "restaurant", "cafe", "café", "menu", "order online", "pickup", "delivery",
                "reservation", "cuisine", "dine", "breakfast", "lunch", "dinner", "food",
            ),
            "legal": ("law firm", "lawyer", "attorney", "legal services", "practice area", "litigation"),
            "medspa": ("med spa", "medspa", "aesthetic", "injectable", "botox", "filler", "laser treatment"),
            "ecommerce": ("add to cart", "checkout", "shop now", "product", "shipping", "shopify", "shopping cart"),
            "saas": ("saas", "software", "platform", "start free trial", "free trial", "book demo", "api"),
            "local_service": (
                "service area", "free estimate", "get a quote", "plumbing", "electrician", "cleaning service",
                "roofing", "moving", "contractor", "landscaping", "hvac", "repair service",
            ),
            "professional_service": (
                "consulting", "consultant", "accounting", "bookkeeping", "marketing agency", "design agency",
                "architecture firm", "engineering firm", "professional services",
            ),
        }

        score_map: Dict[str, int] = {name: 0 for name in rules}
        signal_map: Dict[str, List[str]] = {name: [] for name in rules}
        for vertical, phrases in rules.items():
            for phrase in phrases:
                if phrase in text:
                    score_map[vertical] += 1
                    signal_map[vertical].append(phrase)

        # Strong structured/action evidence gets extra weight.
        schema_text = " ".join(data.get("schema_types") or []).lower()
        if "restaurant" in schema_text:
            score_map["restaurant"] += 4
            signal_map["restaurant"].append("schema:Restaurant")
        if any(t in (data.get("mobile_cta_types") or []) for t in ("add_to_cart", "buy")):
            score_map["ecommerce"] += 3
            signal_map["ecommerce"].append("commerce CTA")
        if data.get("order_online_present"):
            score_map["restaurant"] += 2
            signal_map["restaurant"].append("order action")

        best_vertical = max(score_map, key=score_map.get) if score_map else "general"
        best_score = score_map.get(best_vertical, 0)
        if best_score < 2:
            best_vertical = "general"
            confidence = 0.4
            signals: List[str] = []
        else:
            confidence = min(0.96, 0.48 + best_score * 0.07)
            signals = signal_map.get(best_vertical, [])[:8]

        cta_types = set(data.get("mobile_cta_types") or [])
        primary, secondary = self._conversion_model(best_vertical, cta_types)
        return {
            "vertical": best_vertical,
            "confidence": round(confidence, 2),
            "primary_conversion": primary,
            "secondary_conversions": secondary,
            "signals": signals,
        }

    @staticmethod
    def _conversion_model(vertical: str, cta_types: set[str]) -> Tuple[str, List[str]]:
        if vertical == "restaurant":
            if "order" in cta_types:
                return "order_online", ["reservation", "directions", "call", "view_menu"]
            if "reserve" in cta_types or "book" in cta_types:
                return "reservation", ["order_online", "directions", "call", "view_menu"]
            return "visit_or_order", ["call", "view_menu", "directions"]
        if vertical == "legal":
            return "consultation", ["call", "contact_form"]
        if vertical == "medspa":
            return "booking", ["consultation", "call"]
        if vertical == "ecommerce":
            return "add_to_cart_checkout", ["product_question", "chat"]
        if vertical == "saas":
            return "signup_trial_demo", ["contact", "chat"]
        if vertical == "local_service":
            return "quote_or_call", ["contact_form", "booking"]
        if vertical == "professional_service":
            return "consultation_or_lead", ["contact_form", "call"]
        return "primary_site_action", ["contact"]

    @staticmethod
    def _assess_h1_relevance(data: Dict[str, Any], profile: Dict[str, Any]) -> str:
        if data.get("h1_status") != "present":
            return "UNKNOWN"
        h1 = " ".join(data.get("h1_tags") or []).lower()
        if not h1.strip() or float(profile.get("confidence") or 0) < 0.55:
            return "UNKNOWN"
        vertical = profile.get("vertical")
        keywords = {
            "restaurant": ("restaurant", "cafe", "café", "cuisine", "food", "dining", "kitchen"),
            "legal": ("law", "legal", "lawyer", "attorney", "litigation"),
            "medspa": ("medspa", "med spa", "aesthetic", "treatment", "skin", "laser"),
            "ecommerce": ("shop", "store", "product", "collection"),
            "saas": ("software", "platform", "automation", "api"),
            "local_service": ("service", "repair", "cleaning", "contractor", "plumbing", "moving"),
            "professional_service": ("consulting", "services", "agency", "architecture", "engineering", "accounting"),
        }.get(vertical, ())
        if any(keyword in h1 for keyword in keywords):
            return "PASS"
        # Lack of a simple keyword overlap is not enough evidence to call it wrong.
        return "UNKNOWN"

    def _build_scan_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        browser_loaded = bool(data.get("browser_loaded"))
        dom_complete = bool(data.get("dom_complete"))
        response_ok = bool(data.get("response_ok"))
        challenge = bool(data.get("bot_challenge_suspected") or data.get("http_bot_challenge_suspected"))
        pagespeed_available = data.get("pagespeed_api_status") == "success"
        crux_available = bool(data.get("crux_available"))

        if browser_loaded and not challenge and (dom_complete or response_ok):
            confidence = "high" if response_ok and dom_complete else "medium"
        elif browser_loaded and not challenge:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "http_ok": response_ok,
            "browser_loaded": browser_loaded,
            "dom_complete": dom_complete,
            "bot_challenge_suspected": challenge,
            "pagespeed_available": pagespeed_available,
            "crux_available": crux_available,
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


def collect_scan_data(domain: str) -> Dict[str, Any]:
    """Backward-compatible synchronous helper."""
    import asyncio

    return asyncio.run(HybridScanner().execute_hybrid_scan(domain))
