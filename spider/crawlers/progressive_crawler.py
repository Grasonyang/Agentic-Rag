"""漸進式爬蟲

此模組提供可調整並行數的爬蟲工作者，
透過 URLScheduler 取得待抓取佇列，並以 asyncio.gather 同步處理多筆 URL。
"""

import asyncio
from typing import Optional

from database.models import CrawlStatus
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.retry_manager import RetryManager
from spider.utils.enhanced_logger import get_spider_logger
from spider.utils.rate_limiter import AdaptiveRateLimiter
from .url_scheduler import URLScheduler


class ProgressiveCrawler:
    """漸進式輪詢爬蟲"""

    def __init__(
        self,
        scheduler: URLScheduler,
        retry_manager: RetryManager,
        connection_manager: Optional[EnhancedConnectionManager] = None,
        batch_size: int = 10,
        concurrency: int = 5,
    ) -> None:
        """初始化爬蟲

        Args:
            scheduler: URL 排程器
            retry_manager: 重試管理器
            connection_manager: 連線管理器
            batch_size: 每次抓取的 URL 數量
            concurrency: 同時處理的工作數
        """
        cm = connection_manager or EnhancedConnectionManager(
            rate_limiter=AdaptiveRateLimiter()
        )
        self.scheduler = scheduler
        self.connection_manager = cm
        self.retry_manager = retry_manager
        self.batch_size = batch_size
        self.concurrency = concurrency
        self.logger = get_spider_logger("progressive_crawler")

    async def _fetch_with_retry(self, url: str) -> None:
        """使用 RetryManager 進行帶退避的抓取"""
        attempt = 0
        while True:
            try:
                response = await self.connection_manager.get(url)
                # 讀取內容以確保請求完成
                await response.text()
                return
            except Exception as e:  # noqa: BLE001
                if self.retry_manager.should_retry(e, attempt):
                    delay = self.retry_manager.calculate_delay(attempt)
                    self.logger.warning(
                        f"抓取失敗，{delay:.2f} 秒後重試: {url}",
                        extra={"url": url, "retry_count": attempt + 1},
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise

    async def _process_url(self, url_model) -> None:
        """處理單一 URL"""
        await self.scheduler.update_status(url_model.id, CrawlStatus.CRAWLING)
        try:
            await self._fetch_with_retry(url_model.url)
            await self.scheduler.update_status(url_model.id, CrawlStatus.COMPLETED)
        except Exception as e:  # noqa: BLE001
            # 更新為錯誤狀態
            await self.scheduler.update_status(
                url_model.id, CrawlStatus.ERROR, str(e)
            )
            # 計算延遲後重新排回待處理
            delay = self.retry_manager.calculate_delay(url_model.crawl_attempts + 1)
            self.logger.error(
                f"抓取最終失敗，{delay:.2f} 秒後重試: {url_model.url}",
                extra={"url": url_model.url},
            )
            await asyncio.sleep(delay)
            await self.scheduler.update_status(url_model.id, CrawlStatus.PENDING)

    async def crawl_batch(self) -> int:
        """抓取一批待處理 URL"""
        urls = await self.scheduler.dequeue_batch(self.batch_size)
        if not urls:
            return 0

        sem = asyncio.Semaphore(self.concurrency)

        async def worker(u):
            async with sem:
                await self._process_url(u)

        await asyncio.gather(*(worker(u) for u in urls))

        return len(urls)

    async def run(self, interval: float = 5.0) -> None:
        """連續執行爬蟲，沒有 URL 時等待一段時間"""
        while True:
            processed = await self.crawl_batch()
            if processed == 0:
                await asyncio.sleep(interval)
