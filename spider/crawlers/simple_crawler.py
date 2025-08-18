"""SimpleWebCrawler - 與資料庫整合的簡化爬蟲

範例使用:
    import asyncio
    from spider.crawlers.simple_crawler import SimpleWebCrawler

    async def demo():
        crawler = SimpleWebCrawler()
        result = await crawler.crawl_single("https://example.com")
        if result["success"]:
            print(result["title"], result.get("article_id"))

    asyncio.run(demo())

參數說明:
    connection_manager (EnhancedConnectionManager): HTTP 連線管理器
    db_manager (EnhancedDatabaseManager | None): 資料庫管理器，若提供則自動儲存文章
"""

from typing import Dict, List, Optional
import re
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.database_manager import EnhancedDatabaseManager
from spider.utils.rate_limiter import RateLimiter
from database.models import ArticleModel


class SimpleWebCrawler:
    """簡化版爬蟲，提供基本下載與儲存功能"""

    def __init__(
        self,
        connection_manager: Optional[EnhancedConnectionManager] = None,
        db_manager: Optional[EnhancedDatabaseManager] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        # 若外部未提供連線管理器，則使用傳入的速率限制器建立
        self.connection_manager = connection_manager or EnhancedConnectionManager(
            rate_limiter=rate_limiter
        )
        self.db_manager = db_manager
        self.cookies: Dict[str, str] = {}

    def set_cookies(self, cookies: Dict[str, str]) -> None:
        """設定請求使用的 Cookies"""
        self.cookies = cookies

    async def crawl_single(self, url: str) -> Dict[str, str]:
        """爬取單一 URL 並回傳結果"""
        response = await self.connection_manager.get(url, cookies=self.cookies)
        html = await response.text()
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

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
            except Exception as e:
                results.append({"success": False, "error": str(e), "url": u})
        return results
