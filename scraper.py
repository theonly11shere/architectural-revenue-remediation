"""
scraper.py - Backward Compatibility Layer
Wraps HybridScanner to ensure any legacy imports of WebsiteScraper or scraper functions 
continue to work seamlessly with the new 3-phase hybrid scanning architecture.
"""
from typing import Dict, Any
from hybrid_scanner import HybridScanner


class WebsiteScraper:
    """
    Legacy scraper class wrapper.
    Delegates all execution to the 3-phase HybridScanner engine.
    """
    def __init__(self, google_api_key: str = None):
        self.scanner = HybridScanner(google_api_key=google_api_key)

    def scrape_site(self, target_domain: str) -> Dict[str, Any]:
        """
        Executes the full hybrid scan sequence:
        1. HTTP Pre-flight headers & SSL check
        2. Playwright headless browser DOM audit
        3. Google PageSpeed API query
        """
        return self.scanner.execute_hybrid_scan(target_domain)

    # Alias method in case legacy scripts call scrape() or run()
    def scrape(self, target_domain: str) -> Dict[str, Any]:
        return self.scrape_site(target_domain)

    def run(self, target_domain: str) -> Dict[str, Any]:
        return self.scrape_site(target_domain)


def scrape_website(target_domain: str, google_api_key: str = None) -> Dict[str, Any]:
    """Standalone function wrapper for legacy procedural calls."""
    scraper = WebsiteScraper(google_api_key=google_api_key)
    return scraper.scrape_site(target_domain)