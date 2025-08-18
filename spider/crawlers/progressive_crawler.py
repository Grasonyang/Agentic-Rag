"""漸進式爬蟲

此模組提供一個簡單的輪詢式爬蟲，
會依據資料庫中的 `last_crawl_at` 排序來逐步抓取 URL。
"""

import asyncio
from datetime import datetime

from database.models import CrawlStatus
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.database_manager import EnhancedDatabaseManager
from spider.utils.retry_manager import RetryManager
from spider.utils.enhanced_logger import get_spider_logger


class ProgressiveCrawler:
    """漸進式輪詢爬蟲"""

    def __init__(
        self,
        db_manager: EnhancedDatabaseManager,
        connection_manager: EnhancedConnectionManager,
        retry_manager: RetryManager,
        batch_size: int = 10,
    ) -> None:
        """初始化爬蟲

        Args:
            db_manager: 資料庫管理器
            connection_manager: 連線管理器
            retry_manager: 重試管理器
            batch_size: 每次抓取的 URL 數量
        """
        self.db_manager = db_manager
        self.connection_manager = connection_manager
        self.retry_manager = retry_manager
        self.batch_size = batch_size
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
        await self.db_manager.update_crawl_status(url_model.id, CrawlStatus.CRAWLING)
        try:
            await self._fetch_with_retry(url_model.url)
            await self.db_manager.update_crawl_status(url_model.id, CrawlStatus.COMPLETED)
        except Exception as e:  # noqa: BLE001
            # 更新為錯誤狀態
            await self.db_manager.update_crawl_status(
                url_model.id, CrawlStatus.ERROR, str(e)
            )
            # 計算延遲後重新排回待處理
            delay = self.retry_manager.calculate_delay(url_model.crawl_attempts + 1)
            self.logger.error(
                f"抓取最終失敗，{delay:.2f} 秒後重試: {url_model.url}",
                extra={"url": url_model.url},
            )
            await asyncio.sleep(delay)
            await self.db_manager.update_crawl_status(url_model.id, CrawlStatus.PENDING)

    async def crawl_batch(self) -> int:
        """抓取一批待處理 URL"""
        urls = await self.db_manager.get_pending_urls(self.batch_size)
        if not urls:
            return 0

        # 依 last_crawl_at 排序，確保輪詢式抓取
        urls.sort(key=lambda u: u.last_crawl_at or datetime.min)

        for url_model in urls:
            await self._process_url(url_model)

        return len(urls)

    async def run(self, interval: float = 5.0) -> None:
        """連續執行爬蟲，沒有 URL 時等待一段時間"""
        while True:
            processed = await self.crawl_batch()
            if processed == 0:
                await asyncio.sleep(interval)
