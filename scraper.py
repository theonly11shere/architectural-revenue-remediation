"""Backward-compatible scraper wrapper.

The production scanner now lives only in hybrid_scanner.py. This module remains
for any legacy imports so fixes cannot diverge between two HybridScanner copies.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from hybrid_scanner import HybridScanner, collect_scan_data


class WebsiteScraper:
    def __init__(self, google_api_key: Optional[str] = None):
        self.scanner = HybridScanner(google_api_key=google_api_key)

    def scrape_site(self, target_domain: str, business_name: str = "") -> Any:
        """Preserve legacy behavior in sync and async contexts."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.scanner.execute_hybrid_scan(target_domain, business_name))
        return self.scanner.execute_hybrid_scan(target_domain, business_name)

    def scrape(self, target_domain: str, business_name: str = "") -> Any:
        return self.scrape_site(target_domain, business_name)

    def run(self, target_domain: str, business_name: str = "") -> Any:
        return self.scrape_site(target_domain, business_name)


async def scrape_website_async(
    target_domain: str,
    google_api_key: Optional[str] = None,
    business_name: str = "",
) -> Dict[str, Any]:
    return await HybridScanner(google_api_key=google_api_key).execute_hybrid_scan(
        target_domain, business_name
    )


def scrape_website(
    target_domain: str,
    google_api_key: Optional[str] = None,
    business_name: str = "",
) -> Any:
    return WebsiteScraper(google_api_key=google_api_key).scrape_site(target_domain, business_name)


__all__ = [
    "HybridScanner",
    "WebsiteScraper",
    "collect_scan_data",
    "scrape_website",
    "scrape_website_async",
]
