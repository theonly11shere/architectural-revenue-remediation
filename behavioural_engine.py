# hybrid_scanner.py
import os
import requests
import asyncio
from playwright.async_api import async_playwright

def fetch_google_psi(url: str) -> dict:
    api_key = os.getenv("GOOGLE_PAGESPEED_API_KEY", "")
    psi_endpoint = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile&key={api_key}"
    
    try:
        response = requests.get(psi_endpoint, timeout=15)
        return response.json()
    except Exception as e:
        print(f"Google PSI Fetch Error: {e}")
        return {}

async def run_targeted_playwright(url: str, psi_data: dict) -> dict:
    results = {
        "mobile_cta_visible": False,
        "form_payload_fired": False,
        "click_to_call_present": False
    }
    
    audits = psi_data.get("lighthouseResult", {}).get("audits", {})
    tap_target_items = audits.get("tap-targets", {}).get("details", {}).get("items", [])
    flagged_selectors = [item["node"]["selector"] for item in tap_target_items if "node" in item]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(viewport={"width": 390, "height": 844}) # iPhone 12
        page = await context.new_page()

        network_posts = []
        page.on("request", lambda req: network_posts.append(req.url) if req.method == "POST" else None)

        try:
            await page.goto(url, timeout=10000, wait_until="domcontentloaded")

            # A. Click-To-Call Handlers
            tel_links = await page.locator('a[href^="tel:"], a[href*="wa.me"]').count()
            results["click_to_call_present"] = tel_links > 0

            # B. Mobile Scroll & Sticky CTA
            await page.evaluate("window.scrollBy(0, 500)")
            results["mobile_cta_visible"] = await page.evaluate('''() => {
                const elements = Array.from(document.querySelectorAll('button, a.cta, .sticky-cta'));
                return elements.some(el => window.getComputedStyle(el).position === 'fixed');
            }''')

            # C. Targeted Form Submit Execution
            target_button = page.locator('form button[type="submit"]').first
            if await target_button.count() > 0:
                initial_count = len(network_posts)
                try:
                    await target_button.click(timeout=1000)
                    await page.wait_for_timeout(500)
                    if len(network_posts) > initial_count:
                        results["form_payload_fired"] = True
                except Exception:
                    pass

        except Exception as e:
            print(f"Playwright execution note for {url}: {e}")
        finally:
            await browser.close()

    return results

def collect_scan_data(domain: str) -> dict:
    """Synchronous entry point called directly by scorer.py"""
    url = domain if domain.startswith("http") else f"https://{domain}"
    
    # 1. Fetch PSI
    psi_data = fetch_google_psi(url)
    
    # 2. Run Playwright using PSI findings
    try:
        behavioral_data = asyncio.run(run_targeted_playwright(url, psi_data))
    except Exception as e:
        print(f"Async Playwright execution fallback: {e}")
        behavioral_data = {}

    # Return merged dataset
    return {
        "psi_raw": psi_data,
        "behavioral": behavioral_data
    }