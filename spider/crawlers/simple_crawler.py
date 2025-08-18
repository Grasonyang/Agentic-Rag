"""SimpleWebCrawler - 與資料庫整合的簡化爬蟲

範例使用:
    import asyncio
    from spider.crawlers.simple_crawler import SimpleWebCrawler
    from spider.utils.enhanced_logger import get_spider_logger

    async def demo():
        logger = get_spider_logger("demo")
        crawler = SimpleWebCrawler()
        result = await crawler.crawl_single("https://example.com")
        if result["success"]:
            logger.info(f"{result['title']} {result.get('article_id')}")

    asyncio.run(demo())

參數說明:
    connection_manager (EnhancedConnectionManager | None): HTTP 連線管理器
    db_manager (EnhancedDatabaseManager | None): 資料庫管理器，若提供則自動儲存文章
"""

from typing import Dict, List, Optional
from lxml import html as lxml_html
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.database_manager import EnhancedDatabaseManager
from spider.utils.rate_limiter import AdaptiveRateLimiter
from spider.crawlers.robots_handler import apply_to_crawl4ai
from database.models import ArticleModel
from .base_crawler import BaseCrawler
from spider.utils.enhanced_logger import get_spider_logger

logger = get_spider_logger("simple_crawler")  # 取得爬蟲日誌記錄器


class SimpleWebCrawler(BaseCrawler):
    """簡化版爬蟲，提供基本下載與儲存功能"""

    def __init__(
        self,
        connection_manager: Optional[EnhancedConnectionManager] = None,
        db_manager: Optional[EnhancedDatabaseManager] = None,
    ) -> None:
        cm = connection_manager or EnhancedConnectionManager(
            rate_limiter=AdaptiveRateLimiter()
        )
        apply_to_crawl4ai(cm)  # 先行取得 robots 設定
        super().__init__(cm)
        self.db_manager = db_manager
        self.cookies: Dict[str, str] = {}

    def set_cookies(self, cookies: Dict[str, str]) -> None:
        """設定請求使用的 Cookies"""
        self.cookies = cookies

    async def crawl_single(self, url: str) -> Dict[str, str]:
        """爬取單一 URL 並回傳結果"""
        result = await self.fetch_html(url, cookies=self.cookies)
        if not result["success"]:
            return result

        html = result["html"]
        tree = lxml_html.fromstring(html)
        title = (tree.findtext(".//title") or "").strip()

        result = {"success": True, "title": title, "content": html}

        if self.db_manager:
            article = ArticleModel(url=url, title=title, content=html)
            await self.db_manager.create_article(article)
            result["article_id"] = article.id

        return result

    async def crawl_batch(self, urls: List[str]) -> List[Dict[str, str]]:
        """批次爬取多個 URL"""
        results: List[Dict[str, str]] = []
        for u in urls:
            try:
                results.append(await self.crawl_single(u))
            except Exception as e:  # noqa: BLE001
                err = self._error(e)
                err["url"] = u
                results.append(err)
        return results
