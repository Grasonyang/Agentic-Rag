"""WebCrawler - 簡化版的網頁爬蟲

範例使用:
    import asyncio
    from spider.crawlers.web_crawler import WebCrawler
    from spider.utils.enhanced_logger import get_spider_logger

    async def demo():
        logger = get_spider_logger("demo")
        crawler = WebCrawler(headless=True, wait_time=3000, timeout=30000)
        crawler = WebCrawler()
        result = await crawler.crawl("https://example.com")
        if result["success"]:
            logger.info(result["title"])

    asyncio.run(demo())

參數說明:
    connection_manager (EnhancedConnectionManager | None): HTTP 連線管理器
"""

from typing import Dict, Optional
from lxml import html as lxml_html

from .base_crawler import BaseCrawler
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.rate_limiter import AdaptiveRateLimiter
from spider.utils.enhanced_logger import get_spider_logger

logger = get_spider_logger("web_crawler")  # 取得爬蟲日誌記錄器


class WebCrawler(BaseCrawler):
    """簡化版爬蟲，透過 HTTP 取得內容"""

    def __init__(
        self,
        connection_manager: Optional[EnhancedConnectionManager] = None,
    ) -> None:
        cm = connection_manager or EnhancedConnectionManager(
            rate_limiter=AdaptiveRateLimiter()
        )
        super().__init__(cm)

    async def crawl(self, url: str) -> Dict[str, str]:
        """爬取指定 URL 並回傳內容與標題"""
        result = await self.fetch_html(url)
        if not result["success"]:
            return result

        html = result["html"]
        tree = lxml_html.fromstring(html)
        title = (tree.findtext(".//title") or "").strip()

        return {"success": True, "title": title, "content": html}
