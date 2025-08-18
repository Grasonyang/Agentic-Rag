# 註解使用繁體中文

import random

import pytest

from spider.utils.rate_limiter import (
    AdaptiveRateLimiter,
    RateLimitConfig,
    RateLimiter,
)


def test_token_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試令牌桶在令牌耗盡時回傳等待時間"""

    config = RateLimitConfig(requests_per_second=1, burst_size=1, min_delay=0.1, max_delay=1.0)
    limiter = RateLimiter(config)

    # 移除抖動以便測試
    monkeypatch.setattr(random, "uniform", lambda a, b: 0)

    # 第一次取得令牌不需等待
    assert limiter.acquire() == 0
    # 第二次因無令牌需等待
    wait = limiter.acquire()
    # 允許微小的浮點誤差
    assert wait >= 0.99


def test_adaptive_rate_adjustment() -> None:
    """測試自適應機制會降低速率"""

    limiter = AdaptiveRateLimiter(RateLimitConfig(requests_per_second=10))

    # 模擬較長的回應時間，觸發速率降低
    limiter.record_response("example.com", response_time=6.0, success=True)

    assert limiter.config.requests_per_second < 10

