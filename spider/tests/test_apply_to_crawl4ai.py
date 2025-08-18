# 註解使用繁體中文
import aiohttp
import pytest

crawl4ai = pytest.importorskip("crawl4ai")

from spider.crawlers.robots_handler import apply_to_crawl4ai
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.rate_limiter import AdaptiveRateLimiter, RateLimitConfig


class DummyStrategy:
    """簡化的策略物件，用於記錄掛載的 hooks"""

    def __init__(self) -> None:
        self.hooks: dict[str, object] = {}

    def set_hook(self, name: str, func: object) -> None:
        """儲存 hook"""
        self.hooks[name] = func


class DummySession:
    """僅具備 `crawler_strategy` 屬性的假工作階段"""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, D401
        """忽略所有參數並建立基本屬性"""
        self.crawler_strategy = DummyStrategy()
        self.closed = False

    async def close(self) -> None:  # noqa: D401
        """標記為已關閉"""
        self.closed = True


def test_apply_to_crawl4ai_registers_hook() -> None:
    """確認 `apply_to_crawl4ai` 會掛載 `before_request`"""

    session = DummySession()
    apply_to_crawl4ai(session)

    assert "before_request" in session.crawler_strategy.hooks
    assert hasattr(session, "robots_handler")


@pytest.mark.asyncio
async def test_rate_limiter_hook_registered(monkeypatch) -> None:
    """確認限速器會掛載 `before_request`"""

    monkeypatch.setattr(aiohttp, "ClientSession", DummySession)

    rl = AdaptiveRateLimiter(RateLimitConfig())
    cm = EnhancedConnectionManager(rate_limiter=rl)
    await cm._create_session()

    assert "before_request" in cm._session.crawler_strategy.hooks
