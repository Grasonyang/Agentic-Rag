"""
增強的連接管理器
提供連接池、自動重連、健康檢查等功能
"""

import asyncio
import aiohttp
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urlparse
import logging
from contextlib import asynccontextmanager

from spider.utils.enhanced_logger import get_spider_logger
from spider.utils.rate_limiter import RateLimiter, AdaptiveRateLimiter, RateLimitConfig


@dataclass
class ConnectionConfig:
    """連接配置"""
    # 基本設置
    timeout: float = 30.0
    read_timeout: float = 60.0
    connect_timeout: float = 10.0
    
    # 連接池設置
    connector_limit: int = 100
    connector_limit_per_host: int = 10
    
    # 重試設置
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    
    # User-Agent 和標頭
    user_agent: str = "RAG-Spider/2.0 (Enhanced; Python-aiohttp)"
    headers: Optional[Dict[str, str]] = None
    
    # 速率限制
    requests_per_second: float = 2.0
    burst_requests: int = 5
    
    # 健康檢查
    health_check_interval: float = 300.0  # 5分鐘
    max_failed_health_checks: int = 3


class ConnectionHealthMonitor:
    """連接健康監控器"""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.logger = get_spider_logger("connection_health")
        self.failed_checks = 0
        self.last_check = 0.0
        self.is_healthy = True
        
    async def check_health(self, session: aiohttp.ClientSession) -> bool:
        """檢查連接健康狀態"""
        now = time.time()
        
        # 檢查是否需要進行健康檢查
        if now - self.last_check < self.config.health_check_interval:
            return self.is_healthy
        
        self.last_check = now
        
        try:
            # 使用一個輕量級的HTTP請求測試連接
            async with session.get('https://httpbin.org/status/200', timeout=5) as response:
                if response.status == 200:
                    self.failed_checks = 0
                    self.is_healthy = True
                    self.logger.debug("健康檢查通過")
                    return True
                else:
                    self.failed_checks += 1
                    self.logger.warning(f"健康檢查失敗，狀態碼: {response.status}")
        except Exception as e:
            self.failed_checks += 1
            self.logger.warning(f"健康檢查異常: {e}")
        
        # 判斷是否標記為不健康
        if self.failed_checks >= self.config.max_failed_health_checks:
            self.is_healthy = False
            self.logger.error(f"連接被標記為不健康，失敗次數: {self.failed_checks}")
        
        return self.is_healthy


class EnhancedConnectionManager:
    """增強的連接管理器"""

    def __init__(
        self,
        config: Optional[ConnectionConfig] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.config = config or ConnectionConfig()
        self.logger = get_spider_logger("connection_manager")

        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

        # 如果外部未提供速率限制器，依設定建立預設實例
        if rate_limiter is None:
            rl_config = RateLimitConfig(
                requests_per_second=self.config.requests_per_second,
                burst_size=self.config.burst_requests,
                adaptive=False,
            )
            rate_limiter = RateLimiter(rl_config)

        self._rate_limiter: RateLimiter = rate_limiter
        self._health_monitor = ConnectionHealthMonitor(self.config)
        self._stats = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "retries_total": 0,
            "rate_limited": 0,
            "health_checks": 0,
            "session_recreated": 0,
        }
        
    async def __aenter__(self):
        """異步上下文管理器入口"""
        await self._create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口"""
        await self.close()
    
    async def _create_session(self):
        """創建HTTP會話"""
        if self._session and not self._session.closed:
            return self._session
        
        # 創建連接器
        self._connector = aiohttp.TCPConnector(
            limit=self.config.connector_limit,
            limit_per_host=self.config.connector_limit_per_host,
            ttl_dns_cache=300,  # DNS緩存5分鐘
            use_dns_cache=True,
            enable_cleanup_closed=True
        )
        
        # 準備默認標頭
        headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        if self.config.headers:
            headers.update(self.config.headers)
        
        # 創建超時配置
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=self.config.connect_timeout,
            sock_read=self.config.read_timeout
        )
        
        # 創建會話
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            headers=headers,
            auto_decompress=True,
            raise_for_status=False
        )

        # 若限速器提供 crawl4ai 套用方法，則在此註冊 hook
        if hasattr(self._rate_limiter, "apply_to_crawl4ai"):
            self._rate_limiter.apply_to_crawl4ai(self._session)

        self._stats["session_recreated"] += 1
        self.logger.info("HTTP 會話已創建")
        return self._session
    
    async def _recreate_session_if_needed(self):
        """如有需要重新創建會話"""
        if not self._session or self._session.closed:
            self.logger.warning("檢測到會話已關閉，正在重新創建...")
            await self._create_session()
            return True
        
        # 檢查健康狀態
        if not await self._health_monitor.check_health(self._session):
            self.logger.warning("健康檢查失敗，正在重新創建會話...")
            await self.close()
            await self._create_session()
            return True
        
        return False
    
    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """執行HTTP請求"""
        self._stats["requests_total"] += 1
        
        # 確保會話可用
        await self._recreate_session_if_needed()
        
        # 速率限制：以域名為單位等待
        domain = urlparse(url).netloc
        await self._rate_limiter.acquire_async(domain)
        
        # 重試邏輯
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # 記錄請求開始
                context = self.logger.log_request_start(url, method)
                
                # 執行請求
                response = await self._session.request(method, url, **kwargs)
                
                # 檢查響應狀態
                if response.status < 400:
                    self._stats["requests_success"] += 1
                    content_length = int(response.headers.get('content-length', 0))
                    self.logger.log_request_success(context, response.status, content_length)
                    self._rate_limiter.report_success(domain)
                    return response
                elif response.status == 429:  # 速率限制
                    self._stats["rate_limited"] += 1
                    retry_after = response.headers.get('Retry-After')
                    self._rate_limiter.report_failure(domain, severe=True)
                    if retry_after:
                        try:
                            retry_after = float(retry_after)
                        except ValueError:
                            retry_after = self.config.retry_delay
                    else:
                        retry_after = self.config.retry_delay
                    
                    self.logger.log_rate_limit(url, retry_after)
                    
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise aiohttp.ClientError(f"Rate limited: {response.status}")
                else:
                    # 其他HTTP錯誤
                    error_msg = f"HTTP {response.status}"
                    last_exception = aiohttp.ClientError(error_msg)
                    self._rate_limiter.report_failure(domain)
                    
                    if attempt < self.config.max_retries:
                        delay = self.config.retry_delay * (self.config.retry_backoff ** attempt)
                        self.logger.log_retry_attempt(
                            url, attempt + 1, self.config.max_retries, 
                            error_msg, delay
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise last_exception
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                self._stats["retries_total"] += 1
                self._rate_limiter.report_failure(domain)
                
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (self.config.retry_backoff ** attempt)
                    self.logger.log_retry_attempt(
                        url, attempt + 1, self.config.max_retries, 
                        str(e), delay
                    )
                    await asyncio.sleep(delay)
                    
                    # 在連接錯誤時嘗試重建會話
                    if isinstance(e, (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError)):
                        await self._recreate_session_if_needed()
                else:
                    self._stats["requests_failed"] += 1
                    self.logger.log_request_error(context, e, None, attempt)
                    raise
            except Exception as e:
                self._stats["requests_failed"] += 1
                self.logger.log_request_error(context, e, None, attempt)
                self._rate_limiter.report_failure(domain, severe=True)
                raise
        
        # 如果所有重試都失敗了
        if last_exception:
            raise last_exception
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """GET 請求"""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """POST 請求"""
        return await self.request("POST", url, **kwargs)

    def create_crawler(self, *args, **kwargs):
        """建立 AsyncWebCrawler 並自動掛載限速 hook"""
        try:
            from crawl4ai import AsyncWebCrawler
        except Exception as e:  # noqa: BLE001
            raise ImportError("未安裝 crawl4ai，無法建立 AsyncWebCrawler") from e

        crawler = AsyncWebCrawler(*args, **kwargs)

        # 若限速器支援 crawl4ai，建立後立即掛載
        if hasattr(self._rate_limiter, "apply_to_crawl4ai"):
            self._rate_limiter.apply_to_crawl4ai(crawler)

        return crawler

    async def close(self):
        """關閉連接管理器"""
        if self._session:
            await self._session.close()
            self._session = None
        
        if self._connector:
            await self._connector.close()
            self._connector = None
        
        self.logger.info("連接管理器已關閉")
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取連接統計信息"""
        return {
            **self._stats,
            "is_healthy": self._health_monitor.is_healthy,
            "failed_health_checks": self._health_monitor.failed_checks,
            "rate_limiter_tokens": self._rate_limiter.tokens
        }
    
    @asynccontextmanager
    async def session_context(self):
        """會話上下文管理器"""
        try:
            yield self._session
        finally:
            pass  # 不在這裡關閉會話，由主管理器負責


# 便捷函數
async def create_connection_manager(
    config: Optional[ConnectionConfig] = None,
    rate_limiter: Optional[RateLimiter] = None,
) -> EnhancedConnectionManager:
    """創建連接管理器"""
    manager = EnhancedConnectionManager(config, rate_limiter=rate_limiter)
    await manager._create_session()
    return manager
