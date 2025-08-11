import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import urllib.robotparser

class SitemapParser:
    def __init__(self, user_agent="*"):
        self.user_agent = user_agent

    def get_sitemaps_from_robots(self, domain: str) -> list[str]:
        """
        Parses robots.txt to find sitemap URLs.
        """
        robots_url = urljoin(domain, "robots.txt")
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

    def parse_sitemap(self, sitemap_url: str) -> tuple[list[str], list[str]]:
        """
        Parses a sitemap and returns a list of URLs and a list of nested sitemaps.
        """
        urls = []
        nested_sitemaps = []
        try:
            response = requests.get(sitemap_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "xml")

            for loc in soup.find_all("loc"):
                url = loc.get_text()
                if url.endswith(".xml"):
                    nested_sitemaps.append(url)
                else:
                    urls.append(url)
        except requests.RequestException as e:
            print(f"Error fetching sitemap {sitemap_url}: {e}")

        return urls, nested_sitemaps

    def discover_urls_from_sitemaps(self, domain: str) -> list[str]:
        """
        Discovers all URLs from the sitemaps of a domain.
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

            urls, nested_sitemaps = self.parse_sitemap(sitemap_url)
            all_urls.extend(urls)
            sitemaps_to_parse.extend(nested_sitemaps)
            parsed_sitemaps.add(sitemap_url)

        return all_urls
