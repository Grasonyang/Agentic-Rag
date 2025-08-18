"""`robots_handler` 的單元測試"""

# 註解使用繁體中文

import pytest

from spider.crawlers import robots_handler


class FakeResponse:
    """簡單的非同步回應物件"""

    def __init__(self, text: str, status: int = 200) -> None:
        self._text = text
        self.status = status

    async def text(self) -> str:  # noqa: D401
        """回傳預設文字"""
        return self._text


class FakeConnectionManager:
    """模擬 `EnhancedConnectionManager` 的簡易版本"""

    def __init__(self) -> None:
        self.requested: list[str] = []

    async def get(self, url: str) -> FakeResponse:
        self.requested.append(url)
        content = "\n".join([
            "User-agent: *",
            "Disallow: /private",
            "Crawl-delay: 3",
        ])
        return FakeResponse(content)


@pytest.mark.asyncio
async def test_fetch_and_parse_caches() -> None:
    """驗證 `fetch_and_parse` 能寫入快取"""

    robots_handler._robots_cache.clear()
    robots_handler._crawl_delay_cache.clear()

    cm = FakeConnectionManager()
    await robots_handler.fetch_and_parse("https://example.com", cm)

    assert "example.com" in robots_handler._robots_cache
    assert robots_handler._crawl_delay_cache["example.com"] == 3
    assert cm.requested[0].endswith("/robots.txt")


@pytest.mark.asyncio
async def test_is_allowed_and_get_crawl_delay() -> None:
    """測試 `is_allowed` 與 `get_crawl_delay`"""

    robots_handler._robots_cache.clear()
    robots_handler._crawl_delay_cache.clear()

    cm = FakeConnectionManager()

    assert await robots_handler.is_allowed("https://example.com/public", cm) is True
    assert await robots_handler.is_allowed("https://example.com/private/data", cm) is False
    assert await robots_handler.get_crawl_delay("https://example.com", cm) == 3
