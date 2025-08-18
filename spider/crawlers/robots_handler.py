"""robots.txt 非同步解析與快取處理"""

import urllib.robotparser
from urllib.parse import urljoin, urlparse
from typing import Dict, Optional
import types

from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.enhanced_logger import get_spider_logger

# 建立模組專用的記錄器
logger = get_spider_logger("robots_handler")

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

async def fetch_and_parse(domain: str, connection_manager: Optional[EnhancedConnectionManager] = None) -> None:
    """非同步下載並解析指定網域的 robots.txt"""
    netloc, base_url = _normalize_domain(domain)
    if netloc in _robots_cache:
        return

    robots_url = urljoin(base_url, "robots.txt")
    rp = urllib.robotparser.RobotFileParser()

    close_manager = False
    cm = connection_manager
    if cm is None:
        cm = EnhancedConnectionManager()
        close_manager = True

    try:
        if close_manager:
            async with cm:
                response = await cm.get(robots_url)
                if response.status == 200:
                    text = await response.text()
                    rp.parse(text.splitlines())
                    delay = rp.crawl_delay(USER_AGENT)
                    if delay is not None:
                        _crawl_delay_cache[netloc] = delay
                    # 成功取得 robots.txt 時輸出除錯訊息
                    logger.debug(f"成功取得 {robots_url}")
                else:
                    # 取得 robots.txt 失敗時紀錄錯誤
                    logger.error(
                        f"無法取得 {robots_url}，狀態碼 {response.status}"
                    )
                    rp.parse([])
        else:
            response = await cm.get(robots_url)
            if response.status == 200:
                text = await response.text()
                rp.parse(text.splitlines())
                delay = rp.crawl_delay(USER_AGENT)
                if delay is not None:
                    _crawl_delay_cache[netloc] = delay
                logger.debug(f"成功取得 {robots_url}")
            else:
                logger.error(
                    f"無法取得 {robots_url}，狀態碼 {response.status}"
                )
                rp.parse([])
    except Exception as e:  # noqa: BLE001
        # 捕捉未知例外並記錄
        logger.error(f"下載 {robots_url} 時發生例外: {e}")
        rp.parse([])
    finally:
        if close_manager:
            await cm.close()

    _robots_cache[netloc] = rp

async def is_allowed(url: str, connection_manager: Optional[EnhancedConnectionManager] = None) -> bool:
    """檢查 URL 是否允許被爬取"""
    parsed = urlparse(url)
    netloc = parsed.netloc
    if netloc not in _robots_cache:
        await fetch_and_parse(netloc, connection_manager)
    rp = _robots_cache.get(netloc)
    if not rp:
        return True
    allowed = rp.can_fetch(USER_AGENT, url)
    if not allowed:
        # 不允許時記錄資訊
        logger.info(f"URL 被 robots.txt 禁止: {url}")
    return allowed

async def get_crawl_delay(domain: str, connection_manager: Optional[EnhancedConnectionManager] = None) -> Optional[float]:
    """取得指定網域的 crawl-delay 秒數"""
    netloc, _ = _normalize_domain(domain)
    if netloc not in _robots_cache:
        await fetch_and_parse(netloc, connection_manager)
    return _crawl_delay_cache.get(netloc)

def apply_to_crawl4ai(session, connection_manager: Optional[EnhancedConnectionManager] = None):
    """將 robots.txt 檢查整合至 crawl4ai 的 hook"""

    async def _before_request(url: str, request_kwargs: dict):
        cm = connection_manager or getattr(session, "connection_manager", None)
        if not await is_allowed(url, cm):
            raise PermissionError(f"被 robots.txt 禁止: {url}")

    if hasattr(session, "crawler_strategy") and hasattr(session.crawler_strategy, "set_hook"):
        session.crawler_strategy.set_hook("before_request", _before_request)
        session.robots_handler = types.SimpleNamespace(
            get_crawl_delay=lambda domain: get_crawl_delay(domain, connection_manager),
            is_allowed=lambda url: is_allowed(url, connection_manager),
        )

    return session
