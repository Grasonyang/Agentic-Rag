import requests
from urllib.parse import urljoin, urlparse
import urllib.robotparser
from crawl4ai import AsyncWebCrawler
from spider.utils.connection_manager import EnhancedConnectionManager

class SitemapParser:
    def __init__(self, connection_manager: EnhancedConnectionManager, user_agent="*"):
        self.connection_manager = connection_manager
        self.user_agent = user_agent

    def get_sitemaps_from_robots(self, domain: str) -> list[str]:
        """
        Parses robots.txt to find sitemap URLs.
        """
        robots_url = urljoin(domain, "robots.txt")
        print(f"Processing robots.txt for domain: {domain}")
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            sitemaps = rp.sitemaps
            if sitemaps:
                return sitemaps
        except Exception as e:
            print(f"Error reading robots.txt: {e}")
        return []

    async def parse_sitemap(self, sitemap_url: str) -> tuple[list[str], list[str]]:
        """
        Parses a sitemap and returns a list of URLs and a list of nested sitemaps.
        """
        urls = []
        nested_sitemaps = []
        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(sitemap_url)
                
                if not result.success:
                    print(f"Error fetching sitemap {sitemap_url}: {result.error_message}")
                    return urls, nested_sitemaps
                
                # Parse the XML content to find URLs
                content = result.html
                
                # Simple XML parsing to find <loc> tags
                import re
                loc_pattern = r'<loc>(.*?)</loc>'
                loc_matches = re.findall(loc_pattern, content, re.IGNORECASE)
                
                for url in loc_matches:
                    url = url.strip()
                    parsed_url = urlparse(url)
                    if url.endswith(".xml") or "sitemap" in parsed_url.path.lower():
                        nested_sitemaps.append(url)
                    else:
                        urls.append(url)
        except Exception as e:
            print(f"Error fetching sitemap {sitemap_url}: {e}")

        return urls, nested_sitemaps

    async def _is_sitemap_by_content(self, url: str) -> bool:
        """
        Fetches the URL and checks its content to determine if it's a sitemap.
        """
        try:
            # First do a HEAD request to check content type
            response = requests.head(url, allow_redirects=True, timeout=5)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '')

            # Check Content-Type for XML
            if 'application/xml' in content_type or 'text/xml' in content_type:
                # For more robust check, use crawl4ai to fetch content
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url, timeout=10000)
                    
                    if result.success:
                        # Simple check for XML sitemap structure
                        content = result.html.lower()
                        if '<urlset' in content or '<sitemapindex' in content:
                            print(f"Success checking sitemap content for {url}")
                            return True
                
            # If it's not XML content type, it's unlikely to be a sitemap
            return False
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Error checking sitemap content for {url}: 404 Not Found. Assuming not a sitemap.")
            else:
                print(f"Error checking sitemap content for {url}: {e}")
            return False
        except requests.RequestException as e:
            # Log error but don't fail, just assume it's not a sitemap
            print(f"Error checking sitemap content for {url}: {e}")
            return False
        except Exception as e:
            # Catch parsing errors
            print(f"Error checking content for {url}: {e}")
            return False

    async def discover_urls_from_sitemaps(self, domain: str) -> tuple[list[str], list[str]]:
        """
        Discovers all URLs from the sitemaps of a domain.
        Returns a tuple containing a list of all URLs and a list of parsed sitemap URLs.
        """
        sitemaps_to_parse = self.get_sitemaps_from_robots(domain)
        if not sitemaps_to_parse:
            # If no sitemaps in robots.txt, try the default sitemap.xml
            sitemaps_to_parse.append(urljoin(domain, "sitemap.xml"))

        all_urls = []
        parsed_sitemaps = set()

        while sitemaps_to_parse:
            sitemap_url = sitemaps_to_parse.pop(0)
            if sitemap_url in parsed_sitemaps:
                continue

            urls, nested_sitemaps = await self.parse_sitemap(sitemap_url)
            all_urls.extend(urls)
            sitemaps_to_parse.extend(nested_sitemaps)
            parsed_sitemaps.add(sitemap_url)

        return all_urls, list(parsed_sitemaps)
