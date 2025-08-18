"""URL 排程器

此模組提供以資料庫儲存為基礎的待抓取佇列管理，
可依需求替換成 Redis 等分散式儲存，以支援多進程或多機環境。
"""

from typing import Iterable, List
from database.models import DiscoveredURLModel, CrawlStatus
from spider.utils.database_manager import EnhancedDatabaseManager


class URLScheduler:
    """以資料庫為儲存後端的 URL 排程器"""

    def __init__(self, db_manager: EnhancedDatabaseManager) -> None:
        # 資料庫管理器
        self.db_manager = db_manager

    async def enqueue_urls(self, urls: Iterable[str], priority: float | None = None) -> int:
        """將多個 URL 加入佇列

        Args:
            urls: 要加入的 URL 迭代器
            priority: 可選的優先級
        Returns:
            成功加入的 URL 數量
        """
        models: List[DiscoveredURLModel] = []
        for url in urls:
            model = DiscoveredURLModel(url=url, priority=priority)
            models.append(model)
        if not models:
            return 0
        return await self.db_manager.bulk_create_discovered_urls(models)

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
