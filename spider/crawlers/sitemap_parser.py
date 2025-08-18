from urllib.parse import urljoin, urlparse
import urllib.robotparser
import io
from datetime import datetime
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.enhanced_logger import get_spider_logger
from lxml import etree
from .url_scheduler import URLScheduler

# 建立模組專用的記錄器
logger = get_spider_logger("sitemap_parser")

class SitemapParser:
    def __init__(self, connection_manager: EnhancedConnectionManager, user_agent="*"):
        self.connection_manager = connection_manager
        self.user_agent = user_agent

    def get_sitemaps_from_robots(self, domain: str) -> list[str]:
        """解析 robots.txt 以取得 sitemap URLs。"""
        robots_url = urljoin(domain, "robots.txt")
        # 記錄解析 robots.txt 的網域
        logger.info(f"處理 {domain} 的 robots.txt")
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            sitemaps = rp.sitemaps
            if sitemaps:
                return sitemaps
        except Exception as e:  # noqa: BLE001
            # 紀錄讀取 robots.txt 發生的錯誤
            logger.error(f"讀取 robots.txt 發生錯誤: {e}")
        return []

    async def parse_sitemap(self, sitemap_url: str) -> tuple[list[str], list[str]]:
        """解析 sitemap 並回傳 URL 與巢狀 sitemap"""
        urls = []
        nested_sitemaps = []
        try:
            response = await self.connection_manager.get(sitemap_url)
            content = await response.text()
            root = etree.fromstring(content.encode())

            for loc in root.xpath('//loc'):
                url = (loc.text or '').strip()
                parsed_url = urlparse(url)
                if url.endswith('.xml') or 'sitemap' in parsed_url.path.lower():
                    nested_sitemaps.append(url)
                else:
                    urls.append(url)
        except Exception as e:  # noqa: BLE001
            # 抓取 sitemap 時若發生例外，記錄錯誤
            logger.error(f"抓取 sitemap {sitemap_url} 時發生錯誤: {e}")

        return urls, nested_sitemaps

    async def _is_sitemap_by_content(self, url: str) -> bool:
        """抓取 URL 判斷是否為 sitemap"""
        try:
            # 先發送非同步 HEAD 請求檢查內容類型
            response = await self.connection_manager.request("HEAD", url, allow_redirects=True)
            content_type = response.headers.get('Content-Type', '')

            # 檢查 Content-Type 是否為 XML
            if 'application/xml' in content_type or 'text/xml' in content_type:
                result = await self.connection_manager.get(url)
                content = (await result.text()).lower()
                if '<urlset' in content or '<sitemapindex' in content:
                    # 成功確認為 sitemap 時輸出除錯資訊
                    logger.debug(f"成功驗證 {url} 為 sitemap")
                    return True

            return False
        except Exception as e:  # noqa: BLE001
            # 內容檢查發生錯誤時記錄
            logger.error(f"檢查 {url} 內容時發生錯誤: {e}")
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

            parsed_sitemaps.add(sitemap_url)

            try:
                response = await self.connection_manager.get(sitemap_url)
                content = await response.text()
                root = etree.fromstring(content.encode())

                # Find nested sitemaps
                nested_sitemaps = root.xpath("//*[local-name()='sitemap']/*[local-name()='loc']/text()")
                if nested_sitemaps:
                    sitemaps_to_parse.extend(nested_sitemaps)

                # Find urls
                urls = root.xpath("//*[local-name()='url']/*[local-name()='loc']/text()")
                if urls:
                    batch = [{"url": url} for url in urls]
                    await scheduler.enqueue_urls(batch)

            except Exception as e:  # noqa: BLE001
                logger.error(f"解析 sitemap {sitemap_url} 時發生錯誤: {e}")
