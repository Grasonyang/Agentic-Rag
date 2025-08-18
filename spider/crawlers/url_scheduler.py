"""URL 排程器

此模組提供以資料庫儲存為基礎的待抓取佇列管理，
可依需求替換成 Redis 等分散式儲存，以支援多進程或多機環境。
"""

from typing import Iterable, List, Any, Optional
from datetime import datetime
from urllib.parse import urlparse
from asyncio import Queue

from database.models import DiscoveredURLModel, CrawlStatus
from spider.utils.database_manager import EnhancedDatabaseManager


class URLScheduler:
    """以資料庫為儲存後端的 URL 排程器"""

    def __init__(self, db_manager: EnhancedDatabaseManager, batch_size: int = 100) -> None:
        # 資料庫管理器
        self.db_manager = db_manager
        self.batch_size = batch_size
        self.url_queue: Queue[dict] = Queue()

    def get_domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def add_url(self, url: str, last_modified: Optional[datetime] = None, priority: float = 0.5) -> None:
        url_info = {
            "url": url,
            "domain": self.get_domain(url),
            "last_modified": last_modified,
            "priority": priority,
            "crawl_status": CrawlStatus.PENDING.value
        }
        await self.url_queue.put(url_info)
        if self.url_queue.qsize() >= self.batch_size:
            await self.flush_to_db()

    async def flush_to_db(self) -> None:
        batch = []
        while not self.url_queue.empty() and len(batch) < self.batch_size:
            batch.append(self.url_queue.get_nowait())
        
        if batch:
            models = [DiscoveredURLModel(**item) for item in batch]
            # 使用批次插入加速寫入
            await self.db_manager.bulk_insert_discovered_urls(models)

    async def close(self) -> None:
        await self.flush_to_db()

    async def enqueue_urls(self, urls: Iterable[Any], batch_size: int = 1000) -> int:
        """將多個 URL 以批次寫入佇列

        Args:
            urls: URL 字串或包含 `url`、`priority`、`lastmod` 的資料結構
            batch_size: 單次批量寫入的數量
        Returns:
            成功加入的 URL 數量
        """
        batch: List[DiscoveredURLModel] = []
        total = 0

        for item in urls:
            # 允許直接傳入字串或 dict/tuple
            if isinstance(item, str):
                url = item
                priority = None
                lastmod = None
            elif isinstance(item, dict):
                url = item.get("url", "")
                priority = item.get("priority")
                lastmod = item.get("lastmod")
            else:
                url = item[0]
                priority = item[1] if len(item) > 1 else None
                lastmod = item[2] if len(item) > 2 else None

            if isinstance(lastmod, str):
                try:
                    lastmod = datetime.fromisoformat(lastmod.replace('Z', '+00:00'))
                except ValueError:
                    lastmod = None

            model = DiscoveredURLModel(
                url=url, priority=priority, lastmod=lastmod
            )
            batch.append(model)

            # 批量寫入資料庫
            if len(batch) >= batch_size:
                total += await self.db_manager.bulk_insert_discovered_urls(batch)
                batch.clear()

        # 處理剩餘未滿一批的資料
        if batch:
            total += await self.db_manager.bulk_insert_discovered_urls(batch)

        return total

    async def dequeue_stream(self, batch_size: int):
        """以串流方式逐批取出待處理 URL"""

        while True:
            batch = await self.db_manager.get_pending_urls(batch_size)
            if not batch:
                break
            for item in batch:
                # 先將狀態設為 CRAWLING，避免重複讀取
                await self.update_status(item.id, CrawlStatus.CRAWLING)
                yield item

    async def update_status(self, url_id: str, status: CrawlStatus, error_message: str | None = None) -> bool:
        """更新指定 URL 的狀態"""
        return await self.db_manager.update_crawl_status(url_id, status, error_message)
