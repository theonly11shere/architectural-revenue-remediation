"""
scraper.py - Backward Compatibility Layer
Wraps HybridScanner to ensure any legacy imports of WebsiteScraper or scraper functions 
continue to work seamlessly with the new 3-phase hybrid scanning architecture.
"""
import asyncio
from typing import Dict, Any
from hybrid_scanner import HybridScanner


class WebsiteScraper:
    def __init__(self, google_api_key: str = None):
        self.scanner = HybridScanner(google_api_key=google_api_key)

    def scrape_site(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
        """
        Executes the full hybrid scan sequence securely, ensuring any procedural
        legacy code doesn't crash from missing asyncio event loops.
        """
        try:
            loop = asyncio.get_running_loop()
            # If already in an async event loop context, return the coroutine directly
            return self.scanner.execute_hybrid_scan(target_domain, business_name)
        except RuntimeError:
            # If called procedurally (synchronously), safely boot an event loop
            return asyncio.run(self.scanner.execute_hybrid_scan(target_domain, business_name))

    def scrape(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
        return self.scrape_site(target_domain, business_name)

    def run(self, target_domain: str, business_name: str = "") -> Dict[str, Any]:
        return self.scrape_site(target_domain, business_name)


def scrape_website(target_domain: str, google_api_key: str = None, business_name: str = "") -> Dict[str, Any]:
    """Standalone function wrapper for legacy procedural calls."""
    scraper = WebsiteScraper(google_api_key=google_api_key)
    return scraper.scrape_site(target_domain, business_name)