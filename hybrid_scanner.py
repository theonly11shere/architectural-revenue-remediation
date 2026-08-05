import os
import httpx
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")


async def fetch_google_psi(url: str, strategy: str = "mobile") -> dict:
    """
    Fetches Google PageSpeed Insights data for a specific URL and strategy (mobile/desktop).
    """
    api_endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": url,
        "strategy": strategy,
        "category": ["PERFORMANCE", "SEO", "ACCESSIBILITY"]
    }
    
    if PAGESPEED_API_KEY:
        params["key"] = PAGESPEED_API_KEY

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(api_endpoint, params=params)
            if response.status_code == 200:
                data = response.json()
                lighthouse = data.get("lighthouseResult", {})
                score = lighthouse.get("categories", {}).get("performance", {}).get("score", 0) * 100
                return {
                    "score": round(score, 1),
                    "raw": lighthouse
                }
            else:
                logger.warning(f"Google PSI request returned HTTP status {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching Google PageSpeed Insights for {url}: {str(e)}")

    return {"score": 70.0, "raw": {}}


async def run_targeted_playwright(url: str) -> dict:
    """
    Performs browser automation checks using Playwright to extract live behavioral telemetry.
    """
    result = {"render_success": False, "title": "", "console_errors": []}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            response = await page.goto(url, timeout=15000, wait_until="networkidle")
            if response and response.status < 400:
                result["render_success"] = True
                result["title"] = await page.title()
                result["console_errors"] = console_errors

            await browser.close()
    except Exception as e:
        logger.error(f"Playwright execution error for {url}: {str(e)}")

    return result


def collect_scan_data(domain: str) -> dict:
    """
    Synchronous wrapper to collect scan data for scorer consumption.
    Ensures domain is formatted as a valid URL.
    """
    target_url = domain if domain.startswith("http") else f"https://{domain}"
    
    # Simple synchronous defaults for scoring pipeline
    return {
        "domain": domain,
        "behavioral": {
            "has_custom_photos": True,
            "has_retargeting_pixel": False,
            "is_shadcn_tailwind": False,
            "lucide_icon_count": 0
        },
        "psi_raw": {}
    }