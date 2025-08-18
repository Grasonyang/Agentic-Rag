"""WebCrawler - 基於 crawl4ai 的高性能爬蟲

範例使用:
    import asyncio
    from spider.crawlers.web_crawler import WebCrawler

    async def demo():
        crawler = WebCrawler(headless=True, wait_time=3000, timeout=30000)
        result = await crawler.crawl("https://example.com")
        if result["success"]:
            print(result["title"])

    asyncio.run(demo())

參數說明:
    headless (bool): 是否使用無頭瀏覽器模式
    wait_time (int): 等待 JavaScript 執行的時間 (毫秒)
    timeout (int): 單頁面載入的最大等待時間 (毫秒)
"""

from typing import Dict
from crawl4ai import AsyncWebCrawler
from .base_crawler import BaseCrawler


class WebCrawler(BaseCrawler):
    """基於 crawl4ai 的高性能爬蟲"""

    def __init__(self, headless: bool = True, wait_time: int = 0, timeout: int = 10000) -> None:
        super().__init__()
        self.headless = headless
        self.wait_time = wait_time
        self.timeout = timeout

    async def crawl(self, url: str) -> Dict[str, str]:
        """爬取指定 URL 並回傳內容與標題"""
        async with AsyncWebCrawler(headless=self.headless) as crawler:
            self.apply_robots(crawler)
            try:
                result = await crawler.arun(url, wait_for=self.wait_time, timeout=self.timeout)
                if result.success:
                    return {
                        "success": True,
                        "title": getattr(result, "title", ""),
                        "content": result.html,
                    }
                return {"success": False, "error": result.error_message}
            except Exception as e:  # noqa: BLE001
                return self._error(e)
