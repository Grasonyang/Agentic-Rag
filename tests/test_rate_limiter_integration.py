"""`crawl-delay` 整合測試"""

import asyncio
import time
import types
from urllib.parse import urlparse
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from spider.crawlers.progressive_crawler import ProgressiveCrawler  # noqa: E402
from spider.utils.retry_manager import RetryManager  # noqa: E402
from spider.crawlers import progressive_crawler as pc  # noqa: E402


class DummyURL:
    """簡易 URL 物件"""

    def __init__(self, url: str, uid: str) -> None:
        self.url = url
        self.id = uid
        self.crawl_attempts = 0
        self.domain = urlparse(url).netloc


class DummyScheduler:
    """提供固定 URL 清單的排程器"""

    def __init__(self, urls) -> None:
        self.urls = urls

    async def dequeue_stream(self, batch_size):  # noqa: D401 - 符合 ProgressiveCrawler 需求
        for u in self.urls:
            yield u

    async def update_status(self, url_id, status, error_message=None):  # noqa: D401
        return True


@pytest.mark.asyncio
async def test_requests_respect_crawl_delay(monkeypatch) -> None:
    """確認連續請求間隔不小於 robots 指定的 `crawl-delay`"""

    crawl_delay = 0.1

    async def fake_fetch_and_parse(domain, cm=None):  # noqa: D401
        return []

    async def fake_get_crawl_delay(domain, cm=None):  # noqa: D401
        return crawl_delay

    monkeypatch.setattr(pc, "fetch_and_parse", fake_fetch_and_parse)
    monkeypatch.setattr(pc, "get_crawl_delay", fake_get_crawl_delay)

    scheduler = DummyScheduler(
        [
            DummyURL("https://example.com/a", "1"),
            DummyURL("https://example.com/b", "2"),
        ]
    )
    crawler = ProgressiveCrawler(scheduler, RetryManager())

    # 讓限速器初始延遲為 0，以便由 `crawl-delay` 控制
    crawler.rate_limiter.config.min_delay = 0.0

    timestamps: list[float] = []

    async def fake_get(self, url, **kwargs):
        domain = urlparse(url).netloc
        await self._rate_limiter.acquire_async(domain)
        timestamps.append(time.perf_counter())

        class _Resp:
            status = 200

            async def text(self):  # noqa: D401
                return ""

        return _Resp()

    crawler.connection_manager.get = types.MethodType(fake_get, crawler.connection_manager)

    lock = asyncio.Lock()

    async def fake_acquire_async(self, domain=None):  # noqa: D401
        async with lock:
            await asyncio.sleep(self.config.min_delay)

    crawler.rate_limiter.acquire_async = types.MethodType(
        fake_acquire_async, crawler.rate_limiter
    )

    await crawler.crawl_batch()

    assert len(timestamps) == 2
    interval = timestamps[1] - timestamps[0]
    assert interval >= crawl_delay

