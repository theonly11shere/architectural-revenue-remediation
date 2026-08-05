import os
import urllib.parse
import requests
from typing import Dict, Any
from playwright.sync_api import sync_playwright


class HybridScanner:
    """
    Ultimate Hybrid Scanning Engine:
    - Phase 1: Fast HTTP Pre-flight (SSL, Status Codes, Server Headers)
    - Phase 2: Google PageSpeed Insights API (Mobile Core Web Vitals + Tap Targets)
    - Phase 3: Mobile Playwright Headless Browser (DOM Structure + Deep CRO & Behavioral Diagnostics)
    """

    def __init__(self, google_api_key: str = None):
        self.google_api_key = google_api_key or os.environ.get("PAGESPEED_API_KEY", "")

    def execute_hybrid_scan(self, target_domain: str) -> Dict[str, Any]:
        """Runs the complete 3-phase hybrid telemetry sequence."""
        url = target_domain if target_domain.startswith(("http://", "https://")) else f"https://{target_domain}"

        # 1. Fast HTTP Pre-flight Check
        http_meta = self._fast_http_preflight(url)
        
        # If domain is down/unreachable, exit early to save server resources
        if not http_meta["is_reachable"]:
            return {
                "domain": target_domain,
                "url": url,
                "is_reachable": False,
                "has_ssl": False,
                "status_code": 0,
                "title": "",
                "meta_description": "",
                "h1_tags": [],
                "image_count": 0,
                "missing_alt_images": 0,
                "page_content_len": 0,
                "performance_score": 0.0,
                "google_seo_score": 0.0,
                "click_to_call_present": False,
                "mobile_cta_visible": False,
                "form_payload_fired": False,
                "pagespeed_api_status": "unreachable",
                "psi_raw": {}
            }

        # 2. Fetch Google PageSpeed Insights (PSI) API Data
        pagespeed_meta = self._fetch_google_pagespeed(url)
        psi_raw = pagespeed_meta.get("psi_raw", {})

        # 3. Targeted Mobile Playwright Execution (DOM + Behavioral & CRO Checks)
        dom_and_behavioral_meta = self._run_targeted_playwright(url, psi_raw)

        # Merge all telemetry sources into unified dataset
        return {
            "domain": target_domain,
            "url": url,
            **http_meta,
            **pagespeed_meta,
            **dom_and_behavioral_meta
        }

    def _fast_http_preflight(self, url: str) -> Dict[str, Any]:
        """Phase 1: Rapid HTTP status and security header verification."""
        preflight = {
            "is_reachable": False,
            "has_ssl": url.startswith("https://"),
            "status_code": 0,
            "headers": {}
        }
        try:
            response = requests.get(
                url, 
                timeout=10, 
                headers={"User-Agent": "TrillokaBot/1.0 Web Auditor"}
            )
            preflight["is_reachable"] = True
            preflight["status_code"] = response.status_code
            preflight["headers"] = dict(response.headers)
        except Exception as e:
            print(f"[Hybrid Scanner] HTTP Preflight check failed for {url}: {e}")
            
        return preflight

    def _fetch_google_pagespeed(self, url: str) -> Dict[str, Any]:
        """Phase 2: Fetches Core Web Vitals and Lighthouse metrics from Google API."""
        encoded_url = urllib.parse.quote(url, safe="")
        endpoint = (
            f"https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
            f"?url={encoded_url}&category=PERFORMANCE&category=SEO&strategy=mobile"
        )

        if self.google_api_key:
            endpoint += f"&key={self.google_api_key}"

        try:
            response = requests.get(endpoint, timeout=15)
            if response.status_code == 200:
                data = response.json()
                categories = data.get("lighthouseResult", {}).get("categories", {})

                perf_score = categories.get("performance", {}).get("score", 0.65) * 100
                seo_score = categories.get("seo", {}).get("score", 0.65) * 100

                return {
                    "performance_score": round(perf_score, 1),
                    "google_seo_score": round(seo_score, 1),
                    "pagespeed_api_status": "success",
                    "psi_raw": data
                }
        except Exception as e:
            print(f"[Hybrid Scanner] Google PageSpeed API request error: {e}")

        return {
            "performance_score": 65.0,
            "google_seo_score": 65.0,
            "pagespeed_api_status": "fallback",
            "psi_raw": {}
        }

    def _run_targeted_playwright(self, url: str, psi_data: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 3: Renders mobile DOM and executes behavioral CRO & conversion testing."""
        results = {
            "title": "",
            "meta_description": "",
            "h1_tags": [],
            "image_count": 0,
            "missing_alt_images": 0,
            "page_content_len": 0,
            "click_to_call_present": False,
            "mobile_cta_visible": False,
            "form_payload_fired": False,
            "tap_targets_flagged": []
        }

        # Extract flagged tap targets from Lighthouse audit if available
        audits = psi_data.get("lighthouseResult", {}).get("audits", {})
        tap_target_items = audits.get("tap-targets", {}).get("details", {}).get("items", [])
        results["tap_targets_flagged"] = [
            item["node"]["selector"] for item in tap_target_items if "node" in item and "selector" in item["node"]
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            # Mobile Viewport (iPhone 12 / 13 / 14 dimension)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            )
            page = context.new_page()

            network_posts = []
            page.on("request", lambda req: network_posts.append(req.url) if req.method == "POST" else None)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)

                # --- Standard DOM & SEO Metadata ---
                results["title"] = page.title()

                meta_desc = page.query_selector('meta[name="description"]')
                results["meta_description"] = meta_desc.get_attribute("content") if meta_desc else ""

                h1_nodes = page.query_selector_all("h1")
                results["h1_tags"] = [h.inner_text().strip() for h in h1_nodes if h.inner_text()]

                images = page.query_selector_all("img")
                results["image_count"] = len(images)
                results["missing_alt_images"] = sum(
                    1 for img in images if not img.get_attribute("alt")
                )

                results["page_content_len"] = len(page.content())

                # --- Behavioral & Conversion Diagnostics ---
                # A. Click-To-Call Handlers
                tel_links = page.locator('a[href^="tel:"], a[href*="wa.me"]').count()
                results["click_to_call_present"] = tel_links > 0

                # B. Mobile Scroll & Sticky CTA Detection
                page.evaluate("window.scrollBy(0, 500)")
                results["mobile_cta_visible"] = page.evaluate('''() => {
                    const elements = Array.from(document.querySelectorAll('button, a.cta, .sticky-cta, [class*="cta"]'));
                    return elements.some(el => {
                        const style = window.getComputedStyle(el);
                        return style.position === 'fixed' || style.position === 'sticky';
                    });
                }''')

                # C. Targeted Form Submit Execution Check
                target_button = page.locator('form button[type="submit"], form input[type="submit"]').first
                if target_button.count() > 0:
                    initial_count = len(network_posts)
                    try:
                        target_button.click(timeout=1500)
                        page.wait_for_timeout(500)
                        if len(network_posts) > initial_count:
                            results["form_payload_fired"] = True
                    except Exception:
                        pass

            except Exception as e:
                print(f"[Hybrid Scanner] Playwright execution note for {url}: {e}")
            finally:
                context.close()
                browser.close()

        return results


# Global procedural entry point for module calls
def collect_scan_data(domain: str) -> Dict[str, Any]:
    """Synchronous function entry point."""
    scanner = HybridScanner()
    return scanner.execute_hybrid_scan(domain)