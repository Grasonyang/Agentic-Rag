"""`robots_handler` 的單元測試"""

# 註解使用繁體中文

import pytest

from spider.crawlers import robots_handler


class MockResponse:
    """簡單的回應物件"""

    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


def test_is_allowed_and_crawl_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """模擬 `robots.txt` 內容並測試允許與延遲"""

    # 清除快取避免測試互相干擾
    robots_handler._robots_cache.clear()
    robots_handler._crawl_delay_cache.clear()

    def mock_get(url: str, timeout: int = 10):  # noqa: ANN001
        """回傳自訂的 `robots.txt` 內容"""

        content = "\n".join([
            "User-agent: *",
            "Disallow: /private",
            "Crawl-delay: 3",
        ])
        return MockResponse(content)

    # 取代 `requests.get`
    monkeypatch.setattr(robots_handler.requests, "get", mock_get)

    # `/public` 應允許被爬取
    assert robots_handler.is_allowed("https://example.com/public") is True
    # `/private` 應被禁止
    assert robots_handler.is_allowed("https://example.com/private/data") is False
    # 應回傳設定的 crawl-delay 秒數
    assert robots_handler.get_crawl_delay("https://example.com") == 3
