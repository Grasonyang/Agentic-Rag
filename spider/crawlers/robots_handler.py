"""robots.txt 非同步解析與快取處理"""

from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional
import types

from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.enhanced_logger import get_spider_logger

# 建立模組專用的記錄器
logger = get_spider_logger("robots_handler")

# 全域快取，避免重複下載 robots.txt
_robots_cache: Dict[str, Dict[str, List[str]]] = {}
_crawl_delay_cache: Dict[str, float] = {}
_sitemaps_cache: Dict[str, List[str]] = {}

# 預設使用的 User-Agent
USER_AGENT = "*"

def _normalize_domain(domain: str) -> tuple[str, str]:
    """標準化網域並回傳 (netloc, base_url)"""
    parsed = urlparse(domain if domain.startswith("http") else f"https://{domain}")
    base_url = f"{parsed.scheme}://{parsed.netloc}/"
    return parsed.netloc, base_url

async def fetch_and_parse(domain: str, connection_manager: Optional[EnhancedConnectionManager] = None) -> List[str]:
    """非同步下載並解析指定網域的 robots.txt"""
    netloc, base_url = _normalize_domain(domain)
    if netloc in _robots_cache:
        return _sitemaps_cache.get(netloc, [])

    robots_url = urljoin(base_url, "robots.txt")

    close_manager = False
    cm = connection_manager
    if cm is None:
        cm = EnhancedConnectionManager()
        close_manager = True

    text = ""
    try:
        if close_manager:
            async with cm:
                response = await cm.get(robots_url)
                if response.status == 200:
                    text = await response.text()
                    logger.debug(f"成功取得 {robots_url}")
                else:
                    logger.warning(f"無法取得 {robots_url}，狀態碼 {response.status}")
        else:
            response = await cm.get(robots_url)
            if response.status == 200:
                text = await response.text()
                logger.debug(f"成功取得 {robots_url}")
            else:
                logger.warning(f"無法取得 {robots_url}，狀態碼 {response.status}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"下載 {robots_url} 時發生例外: {e}")
    finally:
        if close_manager:
            await cm.close()

    allows: List[str] = []
    disallows: List[str] = []
    crawl_delay: Optional[float] = None
    sitemaps: List[str] = []
    current_agent: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = [x.strip() for x in line.split(":", 1)]
        key_lower = key.lower()
        if key_lower == "user-agent":
            current_agent = value
        elif key_lower == "disallow" and (current_agent in (USER_AGENT, "*")):
            if value:
                disallows.append(value)
        elif key_lower == "allow" and (current_agent in (USER_AGENT, "*")):
            if value:
                allows.append(value)
        elif key_lower == "crawl-delay" and (current_agent in (USER_AGENT, "*")):
            try:
                crawl_delay = float(value)
            except ValueError:
                pass
        elif key_lower == "sitemap":
            sitemaps.append(value)

    _robots_cache[netloc] = {"allows": allows, "disallows": disallows}
    if crawl_delay is not None:
        _crawl_delay_cache[netloc] = crawl_delay
    _sitemaps_cache[netloc] = sitemaps

    return sitemaps

async def is_allowed(url: str, connection_manager: Optional[EnhancedConnectionManager] = None) -> bool:
    """檢查 URL 是否允許被爬取"""
    parsed = urlparse(url)
    netloc = parsed.netloc
    if netloc not in _robots_cache:
        await fetch_and_parse(netloc, connection_manager)
    rules = _robots_cache.get(netloc)
    if not rules:
        return True

    path = parsed.path or "/"
    matched = ""
    allowed = True

    for rule in rules.get("disallows", []):
        if path.startswith(rule) and len(rule) > len(matched):
            matched = rule
            allowed = False
    for rule in rules.get("allows", []):
        if path.startswith(rule) and len(rule) >= len(matched):
            matched = rule
            allowed = True

    if not allowed:
        logger.info(f"URL 被 robots.txt 禁止: {url}")
    return allowed

async def get_crawl_delay(domain: str, connection_manager: Optional[EnhancedConnectionManager] = None) -> Optional[float]:
    """取得指定網域的 crawl-delay 秒數"""
    netloc, _ = _normalize_domain(domain)
    if netloc not in _robots_cache:
        await fetch_and_parse(domain, connection_manager)
    return _crawl_delay_cache.get(netloc)

async def get_sitemaps(domain: str, connection_manager: Optional[EnhancedConnectionManager] = None) -> List[str]:
    """取得指定網域在 robots.txt 中宣告的 sitemap"""
    netloc, _ = _normalize_domain(domain)
    if netloc not in _robots_cache:
        return await fetch_and_parse(domain, connection_manager)
    return _sitemaps_cache.get(netloc, [])

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
            get_sitemaps=lambda domain: get_sitemaps(domain, connection_manager),
        )

    return session
