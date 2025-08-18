# 註解使用繁體中文
import pytest

crawl4ai = pytest.importorskip("crawl4ai")

from spider.crawlers.robots_handler import apply_to_crawl4ai


class DummyStrategy:
    """簡化的策略物件，用於記錄掛載的 hooks"""

    def __init__(self) -> None:
        self.hooks: dict[str, object] = {}

    def set_hook(self, name: str, func: object) -> None:
        """儲存 hook"""
        self.hooks[name] = func


class DummySession:
    """僅具備 `crawler_strategy` 屬性的假工作階段"""

    def __init__(self) -> None:
        self.crawler_strategy = DummyStrategy()


def test_apply_to_crawl4ai_registers_hook() -> None:
    """確認 `apply_to_crawl4ai` 會掛載 `before_request`"""

    session = DummySession()
    apply_to_crawl4ai(session)

    assert "before_request" in session.crawler_strategy.hooks
    assert hasattr(session, "robots_handler")
