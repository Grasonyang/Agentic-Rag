import requests
from urllib.parse import urljoin, urlparse
import urllib.robotparser
from defusedxml import ElementTree as ET
from crawl4ai import AsyncWebCrawler
from spider.utils.connection_manager import EnhancedConnectionManager

class SitemapParser:
    def __init__(self, connection_manager: EnhancedConnectionManager, user_agent="*"):
        self.connection_manager = connection_manager
        self.user_agent = user_agent

    def get_sitemaps_from_robots(self, domain: str) -> list[str]:
        """解析 robots.txt 以取得 sitemap URLs。"""
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
        """解析 sitemap 並回傳網址列表與巢狀 sitemap 列表。"""
        urls = []
        nested_sitemaps = []
        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(sitemap_url)
                
                if not result.success:
                    print(f"Error fetching sitemap {sitemap_url}: {result.error_message}")
                    return urls, nested_sitemaps
                
                # 使用安全的 XML 解析取代正則
                content = result.html
                try:
                    root = ET.fromstring(content)
                    for loc in root.iter():
                        if loc.tag.endswith("loc") and loc.text:
                            url = loc.text.strip()
                            parsed_url = urlparse(url)
                            if url.endswith(".xml") or "sitemap" in parsed_url.path.lower():
                                nested_sitemaps.append(url)
                            else:
                                urls.append(url)
                except ET.ParseError as e:
                    print(f"解析 sitemap 失敗: {e}")
        except Exception as e:
            print(f"Error fetching sitemap {sitemap_url}: {e}")

        return urls, nested_sitemaps

    async def _is_sitemap_by_content(self, url: str) -> bool:
        """抓取 URL 並檢查內容以判斷是否為 sitemap。"""
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
                        # 解析內容並檢查根標籤
                        try:
                            root = ET.fromstring(result.html)
                            tag = root.tag.lower()
                            if tag.endswith("urlset") or tag.endswith("sitemapindex"):
                                print(f"Success checking sitemap content for {url}")
                                return True
                        except ET.ParseError:
                            pass
                
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

    async def discover_urls_from_sitemaps(self, domain: str):
        """從目標網站的 sitemap 中發現所有 URL。\n        依序產出：\n        - ('sitemap', sitemap_url) 每個成功解析的 sitemap URL。\n        - ('urls', list_of_urls) 該 sitemap 中所有找到的網址。"""
        sitemaps_to_parse = self.get_sitemaps_from_robots(domain)
        if not sitemaps_to_parse:
            # If no sitemaps in robots.txt, try the default sitemap.xml
            sitemaps_to_parse.append(urljoin(domain, "sitemap.xml"))

        parsed_sitemaps = set()

        while sitemaps_to_parse:
            sitemap_url = sitemaps_to_parse.pop(0)
            if sitemap_url in parsed_sitemaps:
                continue

            urls, nested_sitemaps = await self.parse_sitemap(sitemap_url)
            parsed_sitemaps.add(sitemap_url)

            # Yield the parsed sitemap URL first
            yield 'sitemap', sitemap_url
            
            # Then yield the urls found inside
            if urls:
                yield 'urls', urls
            
            # Add nested sitemaps to the queue for parsing
            sitemaps_to_parse.extend(nested_sitemaps)
