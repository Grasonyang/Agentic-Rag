"""負載測試腳本

此腳本會產生大量 URL 並寫入 `URLScheduler`，
再透過 `ProgressiveCrawler` 及 `EnhancedConnectionManager` 模擬抓取流程。

功能：
- 產生指定數量的 URL（預設 300,000）
- 模擬 200 OK 回應的抓取
- 記錄處理時間、記憶體峰值與錯誤率
- 可調整 batch_size、concurrency 與速率限制
- 若吞吐量不足，提供 Redis 佇列或分散式 worker 建議
"""

import argparse
import asyncio
import os
import sys
import time
import tracemalloc
from typing import Dict, List

# 調整匯入路徑，確保能匯入專案模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import CrawlStatus, DiscoveredURLModel
from spider.crawlers.url_scheduler import URLScheduler
from spider.crawlers.progressive_crawler import ProgressiveCrawler
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.retry_manager import RetryManager
from spider.utils.rate_limiter import RateLimiter, RateLimitConfig


class InMemoryDBManager:
    """簡易的記憶體資料庫管理器"""

    def __init__(self) -> None:
        self.urls: Dict[str, DiscoveredURLModel] = {}
        self.error_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401, ANN001
        """不需特別清理資源"""
        return False

    async def bulk_create_discovered_urls(
        self, models: List[DiscoveredURLModel]
    ) -> int:
        for m in models:
            self.urls[m.id] = m
        return len(models)

    async def get_pending_urls(self, batch_size: int) -> List[DiscoveredURLModel]:
        pending = [
            u for u in self.urls.values() if u.crawl_status == CrawlStatus.PENDING
        ]
        pending.sort(key=lambda u: u.last_crawl_at or 0)
        return pending[:batch_size]

    async def update_crawl_status(
        self, url_id: str, status: CrawlStatus, error_message: str | None = None
    ) -> bool:
        url = self.urls.get(url_id)
        if not url:
            return False
        url.crawl_status = status
        url.error_message = error_message
        if status == CrawlStatus.CRAWLING:
            url.crawl_attempts += 1
        elif status == CrawlStatus.ERROR:
            self.error_count += 1
        return True


class DummyResponse:
    """回傳空字串的假回應"""

    status = 200

    async def text(self) -> str:  # noqa: D401
        """回傳空字串"""
        return ""


class MockConnectionManager(EnhancedConnectionManager):
    """覆寫 `get` 方法以回傳假資料"""

    async def __aenter__(self):  # noqa: D401
        """略過建立真實連線"""
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401, ANN001
        """略過關閉連線"""
        return False

    async def get(self, url: str) -> DummyResponse:  # noqa: D401
        """回傳固定 200 OK"""
        return DummyResponse()


def generate_urls(total: int) -> List[str]:
    """產生模擬 URL 清單"""
    return [f"http://example.com/page/{i}" for i in range(total)]


def parse_args() -> argparse.Namespace:
    """解析命令列參數"""
    parser = argparse.ArgumentParser(description="URLScheduler 負載測試")
    parser.add_argument("--total", type=int, default=300_000, help="產生的 URL 數量")
    parser.add_argument("--batch_size", type=int, default=100, help="單批處理數量")
    parser.add_argument("--concurrency", type=int, default=20, help="同時並發數")
    parser.add_argument(
        "--rps", type=float, default=50.0, help="RateLimiter 的每秒請求數"
    )
    parser.add_argument(
        "--min_throughput",
        type=float,
        default=1000.0,
        help="吞吐量門檻，低於此值則建議使用 Redis 或分散式 worker",
    )
    return parser.parse_args()


async def main() -> None:
    """主程式"""
    args = parse_args()

    # 初始化速率限制器與連線管理器
    rate_limiter = RateLimiter(
        RateLimitConfig(requests_per_second=args.rps, burst_size=int(args.rps))
    )
    connection_manager = MockConnectionManager(rate_limiter=rate_limiter)
    retry_manager = RetryManager()

    tracemalloc.start()
    start_time = time.perf_counter()

    async with InMemoryDBManager() as db_manager:
        scheduler = URLScheduler(db_manager)

        # 批次寫入 URL，避免一次建立過多物件佔用記憶體
        urls = generate_urls(args.total)
        CHUNK = 1000
        for i in range(0, len(urls), CHUNK):
            chunk = urls[i : i + CHUNK]
            await scheduler.enqueue_urls(chunk)

        crawler = ProgressiveCrawler(
            scheduler,
            connection_manager,
            retry_manager,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
        )

        processed = 0
        async with connection_manager:
            while True:
                count = await crawler.crawl_batch()
                if count == 0:
                    break
                processed += count

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - start_time

    error_rate = db_manager.error_count / processed if processed else 0.0
    throughput = processed / elapsed if elapsed else 0.0

    print(f"總處理數量: {processed}")
    print(f"總耗時: {elapsed:.2f} 秒")
    print(f"記憶體峰值: {peak / 1024 / 1024:.2f} MB")
    print(f"錯誤率: {error_rate:.4f}")
    print(f"吞吐量: {throughput:.2f} URLs/秒")

    if throughput < args.min_throughput:
        print("吞吐量不足，建議評估改採 Redis 佇列或分散式 worker")
    else:
        print("吞吐量良好")


if __name__ == "__main__":
    asyncio.run(main())
