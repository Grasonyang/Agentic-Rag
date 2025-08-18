import time
import pytest
from pathlib import Path
import sys
import importlib

sys.path.append(str(Path(__file__).resolve().parent.parent))

# 確保載入真正的 URLScheduler 而非測試替身
sys.modules.pop("spider.crawlers.url_scheduler", None)
URLScheduler = importlib.import_module("spider.crawlers.url_scheduler").URLScheduler


class FakeDBManager:
    """簡化的資料庫管理器，用於測試批次插入"""

    def __init__(self) -> None:
        self.saved = []

    async def bulk_insert_discovered_urls(self, url_models):
        # 直接記錄寫入的模型數量
        self.saved.extend(url_models)
        return len(url_models)


@pytest.mark.asyncio
async def test_bulk_enqueue_performance() -> None:
    """模擬大量 URL，確認批次插入效能與筆數"""

    db = FakeDBManager()
    scheduler = URLScheduler(db, batch_size=1000)

    urls = [f"https://example.com/{i}" for i in range(10000)]

    start = time.perf_counter()
    count = await scheduler.enqueue_urls(urls, batch_size=1000)
    duration = time.perf_counter() - start

    assert count == 10000
    assert len(db.saved) == 10000
    # 寫入應在合理時間內完成
    assert duration < 5.0
