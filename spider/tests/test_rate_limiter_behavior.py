import time
from types import SimpleNamespace

import pytest

from spider.utils.rate_limiter import RateLimiter, AdaptiveRateLimiter, RateLimitConfig


class DummyStrategy:
    """簡化策略物件，記錄掛載的 hooks"""

    def __init__(self) -> None:
        self.hooks: dict[str, object] = {}

    def set_hook(self, name: str, func: object) -> None:
        self.hooks[name] = func


class DummySession:
    """提供 `crawler_strategy` 的假 session"""

    def __init__(self) -> None:
        self.crawler_strategy = DummyStrategy()


@pytest.mark.asyncio
async def test_rps_limit_enforced(monkeypatch) -> None:
    """確認 `requests_per_second` 限制會生效"""

    # 固定抖動為 0 以穩定測試時間
    from spider.utils import rate_limiter as rl_module

    monkeypatch.setattr(rl_module.random, "uniform", lambda a, b: 0.0)

    session = DummySession()
    rl = RateLimiter(
        RateLimitConfig(requests_per_second=2, burst_size=1, adaptive=False, min_delay=0.0)
    )
    rl.apply_to_crawl4ai(session)

    hook = session.crawler_strategy.hooks["before_request"]
    start = time.perf_counter()
    for _ in range(4):
        await hook("https://example.com", {})
    elapsed = time.perf_counter() - start

    assert elapsed >= 1.0  # 需等待兩次，每次 0.5 秒


@pytest.mark.asyncio
async def test_crawl_delay_respected(monkeypatch) -> None:
    """確認 robots 的 `crawl-delay` 會被套用"""

    from spider.utils import rate_limiter as rl_module

    monkeypatch.setattr(rl_module.random, "uniform", lambda a, b: 0.0)

    session = DummySession()
    session.robots_handler = SimpleNamespace(get_crawl_delay=lambda domain: 0.2)

    rl = AdaptiveRateLimiter(
        RateLimitConfig(requests_per_second=100, burst_size=1, adaptive=False, min_delay=0.0)
    )
    rl.apply_to_crawl4ai(session)

    hook = session.crawler_strategy.hooks["before_request"]
    start = time.perf_counter()
    await hook("https://example.com", {})
    await hook("https://example.com", {})
    elapsed = time.perf_counter() - start

    assert elapsed >= 0.2
