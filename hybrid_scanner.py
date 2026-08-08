import os
import urllib.parse
import requests
import re
from typing import Dict, Any, List
from playwright.async_api import async_playwright


class HybridScanner:
    """
    Ultimate Hybrid Scanning Engine:
    - Phase 1: Fast HTTP Pre-flight (SSL, Status Codes, Server Headers)
    - Phase 2: Google PageSpeed Insights, CrUX Telemetry, Google Places Data
    - Phase 3: Mobile Playwright Headless Browser (DOM + AI Pattern Detection + CRO Diagnostics)
    """

    def __init__(self, google_api_key: str = None):
        # Gracefully supports Railway's PAGESPEED_API_KEY or GOOGLE_API_KEY fallback
        self.google_api_key = (
            google_api_key 
            or os.environ.get("PAGESPEED_API_KEY", "") 
            or os.environ.get("GOOGLE_API_KEY", "")
        )

    async def execute_hybrid_scan(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
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
                "cms_platform": "",
                # New Default Flags to prevent downstream KeyError
                "crux_available": False,
                "places_found": False,
                "has_clarity": False,
                "has_hotjar": False,
                "has_qualitative_analytics": False,
                "has_ga4": False,
                "has_meta_pixel": False
            }

        # 2. Fetch Google Telemetry (PageSpeed, CrUX, Places)
        pagespeed_meta = self._fetch_google_pagespeed(url)
        crux_meta = self._fetch_crux_telemetry(url)
        places_meta = self._fetch_google_places(target_domain, business_name)
        
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
                "cms_platform": "",
                "has_clarity": False,
                "has_hotjar": False,
                "has_qualitative_analytics": False,
                "has_ga4": False,
                "has_meta_pixel": False
            }

        return {
            "domain": target_domain,
            "url": url,
            **http_meta,
            **pagespeed_meta,
            **crux_meta,
            **places_meta,
            **dom_meta
        }

    def _fast_http_preflight(self, url: str) -> Dict[str, Any]:
        preflight = {
            "is_reachable": False,
            "has_ssl": url.startswith("https://"),
            "status_code": 0,
            "headers": {}
        }
        try:
            response = requests.get(url, timeout=10, headers={"User-Agent": "TrillokaBot/1.0 Web Auditor"})
            preflight["is_reachable"] = True
            preflight["status_code"] = response.status_code
            preflight["headers"] = dict(response.headers)
        except Exception as e:
            print(f"[Hybrid Scanner] HTTP Preflight failed for {url}: {e}")
        return preflight

    def _fetch_google_pagespeed(self, url: str) -> Dict[str, Any]:
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

    def _fetch_crux_telemetry(self, url: str) -> Dict[str, Any]:
        """Queries Google CrUX API for 28-day real user field data."""
        if not self.google_api_key:
            return {"crux_available": False, "crux_reason": "No API Key configured"}

        endpoint = f"https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={self.google_api_key}"
        
        # CrUX aggregates best by origin for smaller sites
        try:
            parsed = urllib.parse.urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            origin = url

        try:
            res = requests.post(endpoint, json={"origin": origin}, timeout=10)
            if res.status_code == 200:
                metrics = res.json().get("record", {}).get("metrics", {})
                lcp = metrics.get("largest_contentful_paint", {}).get("percentiles", {}).get("p75")
                cls_val = metrics.get("cumulative_layout_shift", {}).get("percentiles", {}).get("p75")
                inp = metrics.get("interaction_to_next_paint", {}).get("percentiles", {}).get("p75")
                
                return {
                    "crux_available": True,
                    "crux_lcp_ms": lcp,
                    "crux_cls": float(cls_val) if cls_val is not None else None,
                    "crux_inp_ms": inp,
                    "real_user_speed_grade": "POOR" if (lcp and lcp > 4000) else "GOOD"
                }
            elif res.status_code == 404:
                return {"crux_available": False, "crux_reason": "Insufficient traffic for CrUX dataset"}
        except Exception as e:
            print(f"[Hybrid Scanner] CrUX API error: {e}")

        return {"crux_available": False}

    def _fetch_google_places(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
        """Queries Places API (New) for rating and visual review proof."""
        if not self.google_api_key:
            return {"places_found": False}

        search_query = business_name if business_name else target_domain.replace("https://", "").replace("http://", "").split("/")[0]
        endpoint = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.google_api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.reviews"
        }
        
        try:
            res = requests.post(endpoint, json={"textQuery": search_query}, headers=headers, timeout=10)
            if res.status_code == 200:
                places = res.json().get("places", [])
                if places:
                    p = places[0]
                    reviews = p.get("reviews", [])
                    # Defensively check if photo payload exists in any review
                    has_photos = any(isinstance(r.get("photos"), list) and len(r.get("photos")) > 0 for r in reviews)
                    
                    return {
                        "places_found": True,
                        "google_rating": p.get("rating", 0.0),
                        "google_review_count": p.get("userRatingCount", 0),
                        "has_visual_review_proof": has_photos
                    }
        except Exception as e:
            print(f"[Hybrid Scanner] Places API error: {e}")

        return {"places_found": False}

    def _analyze_text_ai_patterns(self, text: str) -> float:
        if not text or len(text.strip()) < 100:
            return 0.0

        score = 0.0
        lower_text = text.lower()
        
        ai_buzzwords = [
            "in today's digital", "landscape", "testament to", "delve into", 
            "seamless integration", "elevate your", "unlock your potential",
            "beacon of", "moreover", "crucial to understand", "cutting-edge",
            "fostering", "paramount", "transformative", "revolutionary"
        ]
        
        buzzword_hits = sum(1 for word in ai_buzzwords if word in lower_text)
        if buzzword_hits >= 3:
            score += (buzzword_hits * 4.0)

        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 5]
        if len(sentences) >= 5:
            lengths = [len(s.split()) for s in sentences]
            avg_length = sum(lengths) / len(lengths)
            variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)
            
            if variance < 20.0:
                score += 15.0
                
        return min(35.0, score)

    async def _run_targeted_playwright(self, url: str, psi_data: Dict[str, Any]) -> Dict[str, Any]:
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
            "cms_platform": "",
            # DOM Tracking Defaults
            "has_clarity": False,
            "has_hotjar": False,
            "has_qualitative_analytics": False,
            "has_ga4": False,
            "has_meta_pixel": False
        }

        audits = psi_data.get("lighthouseResult", {}).get("audits", {})
        tap_target_items = audits.get("tap-targets", {}).get("details", {}).get("items", [])
        results["tap_targets_flagged"] = [
            item["node"]["selector"] for item in tap_target_items 
            if "node" in item and "selector" in item["node"]
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = await browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()

            network_posts = []
            page.on("request", lambda req: network_posts.append(req.url) if req.method == "POST" else None)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                try:
                    await page.wait_for_load_state("load", timeout=5000)
                except Exception:
                    await page.wait_for_timeout(1500)

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
                
                # --- SCRIPT DETECTION ---
                content_lower = content_html.lower()
                results["has_clarity"] = "clarity.ms" in content_lower
                results["has_hotjar"] = "hotjar.com" in content_lower or "static.hotjar.com" in content_lower
                results["has_qualitative_analytics"] = results["has_clarity"] or results["has_hotjar"]
                results["has_ga4"] = "googletagmanager.com/gtag/js" in content_lower or "gtag(" in content_lower
                results["has_meta_pixel"] = "connect.facebook.net" in content_lower or "fbevents.js" in content_lower

                # AI Spectrum Detection
                ai_flags = await page.evaluate("""() => {
                    const flags = {
                        tailwind_classes: 0,
                        shadcn_markers: false,
                        lucide_icons: 0,
                        generic_headline: false,
                        unlinked_forms: 0,
                        has_custom_photos: false
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

                    return flags;
                }""")

                results["ai_flags"] = ai_flags

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
                if results.get("has_meta_pixel"):
                    ai_score -= 10.0

                visible_text = await page.evaluate("document.body.innerText")
                text_ai_penalty = self._analyze_text_ai_patterns(visible_text)
                ai_score += text_ai_penalty

                results["ai_spectrum_pct"] = max(0.0, min(100.0, round(ai_score, 1)))

                cms = ""
                if "wp-content" in content_lower:
                    cms = "WordPress"
                elif "shopify" in content_lower or "myshopify" in content_lower:
                    cms = "Shopify"
                elif "wix" in content_lower:
                    cms = "Wix"
                elif "squarespace" in content_lower:
                    cms = "Squarespace"
                elif "webflow" in content_lower:
                    cms = "Webflow"
                elif ai_flags.get("tailwind_classes", 0) > 10:
                    cms = "Modern Stack"
                results["cms_platform"] = cms

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
    scanner = HybridScanner()
    import asyncio
    return asyncio.run(scanner.execute_hybrid_scan(domain))