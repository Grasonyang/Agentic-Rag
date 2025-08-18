"""`progressive_crawler` 的單元測試"""

# 註解使用繁體中文

import sys
import types
from dataclasses import dataclass
from datetime import datetime

import pytest

# 建立假的模組以避免匯入實際依賴
connection_module = types.ModuleType("spider.utils.connection_manager")
database_module = types.ModuleType("spider.utils.database_manager")


class EnhancedConnectionManager:  # noqa: D401 - 測試替身
    """假的連線管理器占位"""


class EnhancedDatabaseManager:  # noqa: D401 - 測試替身
    """假的資料庫管理器占位"""


connection_module.EnhancedConnectionManager = EnhancedConnectionManager
database_module.EnhancedDatabaseManager = EnhancedDatabaseManager

sys.modules["spider.utils.connection_manager"] = connection_module
sys.modules["spider.utils.database_manager"] = database_module

from spider.crawlers.progressive_crawler import ProgressiveCrawler  # noqa: E402
from database.models import CrawlStatus  # noqa: E402


@dataclass
class FakeURL:
    """簡化的 URL 模型"""

    id: str
    url: str
    last_crawl_at: datetime | None = None
    crawl_attempts: int = 0


class FakeDBManager:
    """記錄狀態的簡易資料庫管理器"""

    def __init__(self, urls):
        self.urls = urls
        self.statuses = {u.id: CrawlStatus.PENDING for u in urls}

    async def get_pending_urls(self, batch_size):
        return [u for u in self.urls if self.statuses[u.id] == CrawlStatus.PENDING][:batch_size]

    async def update_crawl_status(self, uid, status, error_message=None):  # noqa: ANN001, D401
        """更新狀態"""

        self.statuses[uid] = status


class FakeResponse:
    """回傳空字串的假回應"""

    async def text(self):  # noqa: D401
        """回傳空字串"""

        return ""


class FakeConnectionManager:
    """記錄請求順序的假連線管理器"""

    def __init__(self):
        self.requested: list[str] = []

    async def get(self, url: str) -> FakeResponse:
        self.requested.append(url)
        if "fail" in url:
            raise Exception("fail")
        return FakeResponse()


class FakeRetryManager:
    """簡化的重試管理器"""

    def should_retry(self, exc: Exception, attempt: int) -> bool:  # noqa: ANN001, D401
        """不重試"""

        return False

    def calculate_delay(self, attempt: int) -> float:  # noqa: D401
        """回傳零延遲"""

        return 0.0


@pytest.mark.asyncio
async def test_crawl_batch_order_and_status() -> None:
    """確認依 `last_crawl_at` 順序處理並更新狀態"""

    urls = [
        FakeURL("1", "http://example.com/1", datetime(2020, 1, 2)),
        FakeURL("2", "http://example.com/2", datetime(2020, 1, 1)),
    ]
    db = FakeDBManager(urls)
    conn = FakeConnectionManager()
    crawler = ProgressiveCrawler(db, conn, FakeRetryManager(), batch_size=10)

    processed = await crawler.crawl_batch()

    assert processed == 2
    assert conn.requested == ["http://example.com/2", "http://example.com/1"]
    assert db.statuses["1"] == CrawlStatus.COMPLETED
    assert db.statuses["2"] == CrawlStatus.COMPLETED


@pytest.mark.asyncio
async def test_crawl_batch_error_resets_pending() -> None:
    """確認錯誤後會重設為待處理"""

    urls = [FakeURL("1", "http://example.com/fail")]
    db = FakeDBManager(urls)
    conn = FakeConnectionManager()
    crawler = ProgressiveCrawler(db, conn, FakeRetryManager(), batch_size=10)

    await crawler.crawl_batch()

    assert db.statuses["1"] == CrawlStatus.PENDING

