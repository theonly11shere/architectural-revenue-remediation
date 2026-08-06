import os
import urllib.parse
import requests
from typing import Dict, Any, List
from playwright.async_api import async_playwright


class HybridScanner:
    """
    Ultimate Hybrid Scanning Engine:
    - Phase 1: Fast HTTP Pre-flight (SSL, Status Codes, Server Headers)
    - Phase 2: Google PageSpeed Insights API (Mobile Core Web Vitals)
    - Phase 3: Mobile Playwright Headless Browser (DOM + AI Pattern Detection + CRO Diagnostics)
    """

    def __init__(self, google_api_key: str = None):
        self.google_api_key = google_api_key or os.environ.get("PAGESPEED_API_KEY", "")

    async def execute_hybrid_scan(self, target_domain: str) -> Dict[str, Any]:
        """Runs the complete 3-phase hybrid telemetry sequence."""
        url = target_domain if target_domain.startswith(("http://", "https://")) else f"https://{target_domain}"

        # 1. Fast HTTP Pre-flight Check
        http_meta = self._fast_http_preflight(url)

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
                "tap_targets_flagged": [],
                "pagespeed_api_status": "unreachable",
                "psi_raw": {},
                "ai_spectrum_pct": 0.0,
                "ai_flags": {},
                "cms_platform": ""
            }

        # 2. Fetch Google PageSpeed Insights (PSI) API Data
        pagespeed_meta = self._fetch_google_pagespeed(url)
        psi_raw = pagespeed_meta.get("psi_raw", {})

        # 3. Targeted Mobile Playwright Execution
        try:
            dom_meta = await self._run_targeted_playwright(url, psi_raw)
        except Exception as e:
            print(f"[Hybrid Scanner] Playwright skipped: {e}")
            dom_meta = {
                "title": "",
                "meta_description": "",
                "h1_tags": [],
                "image_count": 0,
                "missing_alt_images": 0,
                "page_content_len": 0,
                "click_to_call_present": False,
                "mobile_cta_visible": False,
                "form_payload_fired": False,
                "tap_targets_flagged": [],
                "ai_spectrum_pct": 0.0,
                "ai_flags": {},
                "cms_platform": ""
            }

        return {
            "domain": target_domain,
            "url": url,
            **http_meta,
            **pagespeed_meta,
            **dom_meta
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
            print(f"[Hybrid Scanner] HTTP Preflight failed for {url}: {e}")
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
            print(f"[Hybrid Scanner] Google PageSpeed API error: {e}")

        return {
            "performance_score": 65.0,
            "google_seo_score": 65.0,
            "pagespeed_api_status": "fallback",
            "psi_raw": {}
        }

    async def _run_targeted_playwright(self, url: str, psi_data: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 3: Renders mobile DOM and executes behavioral CRO, AI detection, & conversion testing."""
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
            "tap_targets_flagged": [],
            "ai_spectrum_pct": 0.0,
            "ai_flags": {},
            "cms_platform": ""
        }

        # Extract flagged tap targets from Lighthouse audit if available
        audits = psi_data.get("lighthouseResult", {}).get("audits", {})
        tap_target_items = audits.get("tap-targets", {}).get("details", {}).get("items", [])
        results["tap_targets_flagged"] = [
            item["node"]["selector"] for item in tap_target_items 
            if "node" in item and "selector" in item["node"]
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()

            network_posts = []
            page.on("request", lambda req: network_posts.append(req.url) if req.method == "POST" else None)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)

                # Standard DOM & SEO Metadata
                results["title"] = await page.title()

                meta_desc = await page.query_selector('meta[name="description"]')
                results["meta_description"] = await meta_desc.get_attribute("content") if meta_desc else ""

                h1_nodes = await page.query_selector_all("h1")
                results["h1_tags"] = [await h.inner_text() for h in h1_nodes if await h.inner_text()]

                images = await page.query_selector_all("img")
                results["image_count"] = len(images)
                missing_alt = 0
                for img in images:
                    alt = await img.get_attribute("alt")
                    if not alt:
                        missing_alt += 1
                results["missing_alt_images"] = missing_alt

                content_html = await page.content()
                results["page_content_len"] = len(content_html)

                # AI Spectrum Detection (Real DOM Analysis)
                ai_flags = await page.evaluate("""() => {
                    const flags = {
                        tailwind_classes: 0,
                        shadcn_markers: false,
                        lucide_icons: 0,
                        generic_headline: false,
                        unlinked_forms: 0,
                        has_custom_photos: false,
                        has_retargeting_pixel: false
                    };

                    const allElements = document.querySelectorAll("*");
                    let twCount = 0;
                    allElements.forEach(el => {
                        const cls = el.className || "";
                        if (/\\b(flex|grid|bg-\\w+|text-\\w+|p-\\d+|m-\\d+|rounded|shadow|border|hover:|md:|lg:)\\b/.test(cls)) {
                            twCount++;
                        }
                    });
                    flags.tailwind_classes = twCount;

                    const shadcnEls = document.querySelectorAll('[class*="shadcn"], [data-slot], [class*="cn("]');
                    flags.shadcn_markers = shadcnEls.length > 0;

                    const svgs = document.querySelectorAll("svg");
                    let lucideCount = 0;
                    svgs.forEach(svg => {
                        const html = svg.outerHTML || "";
                        if (html.includes("lucide") || html.includes("stroke-linecap") || html.includes("stroke-width")) {
                            lucideCount++;
                        }
                    });
                    flags.lucide_icons = lucideCount;

                    const headings = Array.from(document.querySelectorAll("h1, h2, h3"));
                    const genericPatterns = [
                        /empowering.*business/i, /next-gen/i, /unlock.*potential/i,
                        /transform.*digital/i, /innovative solutions/i,
                        /streamline.*workflow/i, /leverage.*power/i,
                        /cutting-edge/i, /seamless.*experience/i
                    ];
                    flags.generic_headline = headings.some(h => 
                        genericPatterns.some(pat => pat.test(h.innerText))
                    );

                    const forms = document.querySelectorAll("form");
                    let unlinked = 0;
                    forms.forEach(f => {
                        const action = f.getAttribute("action") || "";
                        if (!action || action === "#" || action === "") {
                            unlinked++;
                        }
                    });
                    flags.unlinked_forms = unlinked;

                    const imgSrcs = Array.from(document.querySelectorAll("img")).map(i => i.src || "");
                    const stockDomains = ["unsplash", "pexels", "shutterstock", "gettyimages", "istock", "adobe.stock"];
                    flags.has_custom_photos = imgSrcs.some(src => 
                        !stockDomains.some(d => src.includes(d))
                    );

                    const scripts = Array.from(document.querySelectorAll("script")).map(s => s.src || s.innerText || "");
                    flags.has_retargeting_pixel = scripts.some(s => 
                        /facebook|fbq|gtag|googletagmanager|analytics|hotjar|clarity/i.test(s)
                    );

                    return flags;
                }""")

                results["ai_flags"] = ai_flags

                # Calculate AI Spectrum % (0 = fully custom, 100 = raw AI template)
                ai_score = 0.0
                if ai_flags.get("tailwind_classes", 0) > 20:
                    ai_score += 25.0
                if ai_flags.get("shadcn_markers"):
                    ai_score += 20.0
                if ai_flags.get("lucide_icons", 0) > 5:
                    ai_score += 15.0
                if ai_flags.get("generic_headline"):
                    ai_score += 15.0
                if ai_flags.get("unlinked_forms", 0) > 0:
                    ai_score += 10.0
                if ai_flags.get("has_custom_photos"):
                    ai_score -= 15.0
                if ai_flags.get("has_retargeting_pixel"):
                    ai_score -= 10.0

                results["ai_spectrum_pct"] = max(0.0, min(100.0, round(ai_score, 1)))

                # CMS detection
                cms = ""
                if "wp-content" in content_html:
                    cms = "WordPress"
                elif "shopify" in content_html.lower() or "myshopify" in content_html.lower():
                    cms = "Shopify"
                elif "wix" in content_html.lower():
                    cms = "Wix"
                elif "squarespace" in content_html.lower():
                    cms = "Squarespace"
                elif "webflow" in content_html.lower():
                    cms = "Webflow"
                elif ai_flags.get("tailwind_classes", 0) > 10:
                    cms = "Modern Stack"
                results["cms_platform"] = cms

                # Behavioral & Conversion Diagnostics
                tel_links = await page.locator('a[href^="tel:"], a[href*="wa.me"]').count()
                results["click_to_call_present"] = tel_links > 0

                await page.evaluate("window.scrollBy(0, 500)")
                results["mobile_cta_visible"] = await page.evaluate("""() => {
                    const elements = Array.from(document.querySelectorAll('button, a.cta, .sticky-cta, [class*="cta"]'));
                    return elements.some(el => {
                        const style = window.getComputedStyle(el);
                        return style.position === 'fixed' || style.position === 'sticky';
                    });
                }""")

                target_button = page.locator('form button[type="submit"], form input[type="submit"]').first
                if await target_button.count() > 0:
                    initial_count = len(network_posts)
                    try:
                        await target_button.click(timeout=1500)
                        await page.wait_for_timeout(500)
                        if len(network_posts) > initial_count:
                            results["form_payload_fired"] = True
                    except Exception:
                        pass

            except Exception as e:
                print(f"[Hybrid Scanner] Playwright note for {url}: {e}")
            finally:
                await browser.close()

        return results


def collect_scan_data(domain: str) -> Dict[str, Any]:
    """Synchronous function entry point."""
    scanner = HybridScanner()
    import asyncio
    return asyncio.run(scanner.execute_hybrid_scan(domain))
