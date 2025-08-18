"""robots.txt 解析與快取處理"""

import requests
import urllib.robotparser
from urllib.parse import urljoin, urlparse
from typing import Dict, Optional

# 全域快取，避免重複下載 robots.txt
_robots_cache: Dict[str, urllib.robotparser.RobotFileParser] = {}
_crawl_delay_cache: Dict[str, float] = {}

# 預設使用的 User-Agent
USER_AGENT = "*"

def _normalize_domain(domain: str) -> tuple[str, str]:
    """標準化網域並回傳 (netloc, base_url)"""
    parsed = urlparse(domain if domain.startswith("http") else f"https://{domain}")
    base_url = f"{parsed.scheme}://{parsed.netloc}/"
    return parsed.netloc, base_url

def fetch_and_parse(domain: str) -> None:
    """下載並解析指定網域的 robots.txt"""
    netloc, base_url = _normalize_domain(domain)
    if netloc in _robots_cache:
        return

    robots_url = urljoin(base_url, "robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    try:
        response = requests.get(robots_url, timeout=10)
        if response.status_code == 200:
            rp.parse(response.text.splitlines())
            delay = rp.crawl_delay(USER_AGENT)
            if delay is not None:
                _crawl_delay_cache[netloc] = delay
        else:
            rp.parse([])
    except Exception:
        rp.parse([])
    _robots_cache[netloc] = rp

def is_allowed(url: str) -> bool:
    """檢查 URL 是否允許被爬取"""
    parsed = urlparse(url)
    netloc = parsed.netloc
    if netloc not in _robots_cache:
        fetch_and_parse(netloc)
    rp = _robots_cache.get(netloc)
    if not rp:
        return True
    return rp.can_fetch(USER_AGENT, url)

def get_crawl_delay(domain: str) -> Optional[float]:
    """取得指定網域的 crawl-delay 秒數"""
    netloc, _ = _normalize_domain(domain)
    if netloc not in _robots_cache:
        fetch_and_parse(netloc)
    return _crawl_delay_cache.get(netloc)
