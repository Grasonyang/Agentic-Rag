"""URL 排程器

此模組提供以資料庫儲存為基礎的待抓取佇列管理，
可依需求替換成 Redis 等分散式儲存，以支援多進程或多機環境。
"""

from typing import Iterable, List, Any
from datetime import datetime
from database.models import DiscoveredURLModel, CrawlStatus
from spider.utils.database_manager import EnhancedDatabaseManager


class URLScheduler:
    """以資料庫為儲存後端的 URL 排程器"""

    def __init__(self, db_manager: EnhancedDatabaseManager) -> None:
        # 資料庫管理器
        self.db_manager = db_manager

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
                total += await self.db_manager.bulk_create_discovered_urls(batch)
                batch.clear()

        if batch:
            total += await self.db_manager.bulk_create_discovered_urls(batch)

        return total

    async def dequeue_batch(self, batch_size: int) -> List[DiscoveredURLModel]:
        """取出一批待處理的 URL

        Args:
            batch_size: 批次大小
        Returns:
            待處理的 URL 模型列表
        """
        return await self.db_manager.get_pending_urls(batch_size)

    async def update_status(self, url_id: str, status: CrawlStatus, error_message: str | None = None) -> bool:
        """更新指定 URL 的狀態"""
        return await self.db_manager.update_crawl_status(url_id, status, error_message)
