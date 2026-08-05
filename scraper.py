import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebScraper:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def _build_error_response(self, target_url: str, error_msg: str) -> dict:
        """
        Builds a safe, standard fallback payload on scraping failures.
        """
        return {
            "url": target_url,
            "status_code": 0,
            "title": None,
            "meta_description": None,
            "h1": [],
            "error": error_msg
        }

    async def scrape(self, target_url: str) -> dict:
        """
        Scrapes basic SEO metadata from the given URL with automatic HTTPS to HTTP fallback.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            try:
                response = await client.get(target_url)
            except Exception as first_err:
                # Fallback to HTTP if HTTPS fails
                if target_url.startswith("https://"):
                    fallback_url = target_url.replace("https://", "http://", 1)
                    try:
                        response = await client.get(fallback_url)
                    except Exception as second_err:
                        return self._build_error_response(target_url, f"Both HTTPS and HTTP attempts failed: {str(second_err)}")
                else:
                    return self._build_error_response(target_url, f"Scrape failed: {str(first_err)}")

            if response.status_code >= 400:
                return self._build_error_response(target_url, f"Received HTTP error status {response.status_code}")

            try:
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else None
                
                meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
                meta_description = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else None

                h1_headers = [h1.get_text(strip=True) for h1 in soup.find_all("h1") if h1.get_text(strip=True)]

                return {
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "title": title,
                    "meta_description": meta_description,
                    "h1": h1_headers,
                    "error": None
                }
            except Exception as parse_err:
                logger.error(f"Parsing error for {target_url}: {str(parse_err)}")
                return self._build_error_response(target_url, f"Failed to parse HTML response: {str(parse_err)}")