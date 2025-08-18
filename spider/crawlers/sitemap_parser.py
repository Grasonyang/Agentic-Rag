from urllib.parse import urljoin, urlparse
import urllib.robotparser
from defusedxml import ElementTree as ET
from crawl4ai import AsyncWebCrawler
from spider.utils.connection_manager import EnhancedConnectionManager
from lxml import etree
from .url_scheduler import URLScheduler

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
        """解析 sitemap 並回傳 URL 與巢狀 sitemap"""
        urls = []
        nested_sitemaps = []
        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(sitemap_url)

                if not result.success:
                    print(f"Error fetching sitemap {sitemap_url}: {result.error_message}")
                    return urls, nested_sitemaps

                # 使用 lxml 解析 XML 內容
                content = result.html
                root = etree.fromstring(content.encode())

                for loc in root.xpath('//loc'):
                    url = (loc.text or '').strip()
                    parsed_url = urlparse(url)
                    if url.endswith('.xml') or 'sitemap' in parsed_url.path.lower():
                        nested_sitemaps.append(url)
                    else:
                        urls.append(url)
        except Exception as e:
            print(f"Error fetching sitemap {sitemap_url}: {e}")

        return urls, nested_sitemaps

    async def _is_sitemap_by_content(self, url: str) -> bool:
        """抓取 URL 判斷是否為 sitemap"""
        try:
            # 先發送非同步 HEAD 請求檢查內容類型
            response = await self.connection_manager.request("HEAD", url, allow_redirects=True)
            content_type = response.headers.get('Content-Type', '')

            # 檢查 Content-Type 是否為 XML
            if 'application/xml' in content_type or 'text/xml' in content_type:
                # 使用 crawl4ai 取得內容進一步確認
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url, timeout=10000)

                    if result.success:
                        content = result.html.lower()
                        if '<urlset' in content or '<sitemapindex' in content:
                            print(f"Success checking sitemap content for {url}")
                            return True

            return False
        except Exception as e:
            print(f"Error checking content for {url}: {e}")
            return False

    async def discover_urls_from_sitemaps(self, domain: str):
        """透過 sitemap 發掘所有 URL"""

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

    async def stream_discover(self, domain: str, scheduler: URLScheduler, batch_size: int = 100) -> None:
        """串流解析 sitemap 並將 URL 直接寫入排程器

        Args:
            domain: 目標網域
            scheduler: URL 排程器
            batch_size: 每批寫入的 URL 數量
        """
        sitemaps_to_parse = self.get_sitemaps_from_robots(domain)
        if not sitemaps_to_parse:
            sitemaps_to_parse.append(urljoin(domain, "sitemap.xml"))

        parsed_sitemaps = set()

        while sitemaps_to_parse:
            sitemap_url = sitemaps_to_parse.pop(0)
            if sitemap_url in parsed_sitemaps:
                continue

            urls, nested_sitemaps = await self.parse_sitemap(sitemap_url)
            parsed_sitemaps.add(sitemap_url)

            # 將解析出的 URL 以批次寫入排程器，避免一次載入全部
            for i in range(0, len(urls), batch_size):
                batch = urls[i : i + batch_size]
                await scheduler.enqueue_urls(batch)

            sitemaps_to_parse.extend(nested_sitemaps)
