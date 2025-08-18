"""
速率限制器
控制爬取速度，避免對目標服務器造成過大壓力
"""

import time
import asyncio
import random
import logging
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """速率限制配置"""
    requests_per_second: float = 1.0
    burst_size: int = 5
    adaptive: bool = True
    min_delay: float = 0.5
    max_delay: float = 10.0

class RateLimiter:
    """速率限制器，使用令牌桶算法"""
    
    def __init__(self, config: RateLimitConfig = None):
        """
        初始化速率限制器
        
        Args:
            config: 速率限制配置
        """
        self.config = config or RateLimitConfig()
        self.tokens = self.config.burst_size
        self.last_update = time.time()
        self.request_times = []
        self.domain_limits: Dict[str, Dict] = {}
        
    def acquire(self, domain: str = None) -> float:
        """
        獲取請求許可
        
        Args:
            domain: 域名（用於分域名限制）
            
        Returns:
            float: 需要等待的時間（秒）
        """
        now = time.time()
        
        # 更新令牌桶
        time_passed = now - self.last_update
        self.tokens = min(
            self.config.burst_size,
            self.tokens + time_passed * self.config.requests_per_second
        )
        self.last_update = now
        
        # 如果沒有令牌，計算等待時間
        if self.tokens < 1:
            wait_time = (1 - self.tokens) / self.config.requests_per_second
            wait_time = max(wait_time, self.config.min_delay)
            wait_time = min(wait_time, self.config.max_delay)
            
            # 添加隨機抖動
            jitter = random.uniform(0, wait_time * 0.1)
            wait_time += jitter
            
            return wait_time
        
        # 消耗令牌
        self.tokens -= 1
        
        # 記錄請求時間（用於自適應調整）
        self.request_times.append(now)
        # 只保留最近100個請求時間
        if len(self.request_times) > 100:
            self.request_times = self.request_times[-100:]
        
        # 域名特定限制
        if domain:
            domain_wait = self._check_domain_limit(domain)
            if domain_wait > 0:
                return domain_wait
        
        return 0
    
    async def acquire_async(self, domain: str = None) -> None:
        """
        異步獲取請求許可
        
        Args:
            domain: 域名
        """
        wait_time = self.acquire(domain)
        if wait_time > 0:
            logger.debug(f"速率限制: 等待 {wait_time:.2f} 秒")
            await asyncio.sleep(wait_time)
    
    def _check_domain_limit(self, domain: str) -> float:
        """
        檢查域名特定的限制
        
        Args:
            domain: 域名
            
        Returns:
            float: 需要等待的時間
        """
        now = time.time()
        
        if domain not in self.domain_limits:
            self.domain_limits[domain] = {
                "last_request": 0,
                "request_count": 0,
                "penalty_until": 0,
                "failure_count": 0
            }
        
        domain_info = self.domain_limits[domain]
        
        # 檢查是否在懲罰期
        if now < domain_info["penalty_until"]:
            return domain_info["penalty_until"] - now
        
        # 計算域名特定的延遲
        time_since_last = now - domain_info["last_request"]
        min_interval = self._calculate_domain_interval(domain)
        
        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            return wait_time
        
        # 更新域名信息
        domain_info["last_request"] = now
        domain_info["request_count"] += 1
        
        return 0
    
    def _calculate_domain_interval(self, domain: str) -> float:
        """
        計算域名特定的請求間隔
        
        Args:
            domain: 域名
            
        Returns:
            float: 請求間隔（秒）
        """
        if domain not in self.domain_limits:
            return 1.0 / self.config.requests_per_second
        
        domain_info = self.domain_limits[domain]
        base_interval = 1.0 / self.config.requests_per_second
        
        # 根據失敗次數調整間隔
        failure_multiplier = 1 + (domain_info["failure_count"] * 0.5)
        
        # 一些知名網站的特殊處理
        if any(pattern in domain.lower() for pattern in ['google', 'amazon', 'microsoft']):
            base_interval *= 2  # 大型網站更保守
        elif any(pattern in domain.lower() for pattern in ['news', 'blog', 'wiki']):
            base_interval *= 1.5  # 內容網站適中
        
        return base_interval * failure_multiplier
    
    def report_success(self, domain: str = None):
        """
        報告請求成功
        
        Args:
            domain: 域名
        """
        if domain and domain in self.domain_limits:
            # 成功時減少失敗計數
            self.domain_limits[domain]["failure_count"] = max(
                0, self.domain_limits[domain]["failure_count"] - 1
            )
    
    def report_failure(self, domain: str = None, severe: bool = False):
        """
        報告請求失敗
        
        Args:
            domain: 域名
            severe: 是否為嚴重失敗（如被封IP）
        """
        if domain:
            if domain not in self.domain_limits:
                self.domain_limits[domain] = {
                    "last_request": 0,
                    "request_count": 0,
                    "penalty_until": 0,
                    "failure_count": 0
                }
            
            domain_info = self.domain_limits[domain]
            domain_info["failure_count"] += 1
            
            # 嚴重失敗時設置懲罰期
            if severe:
                penalty_duration = min(300, 30 * (2 ** domain_info["failure_count"]))  # 最多5分鐘
                domain_info["penalty_until"] = time.time() + penalty_duration
                logger.warning(f"域名 {domain} 進入懲罰期 {penalty_duration} 秒")
    
    def get_current_rate(self) -> float:
        """
        獲取當前實際請求速率
        
        Returns:
            float: 每秒請求數
        """
        now = time.time()
        # 計算最近60秒的請求數
        recent_requests = [t for t in self.request_times if now - t < 60]
        return len(recent_requests) / 60
    
    def adjust_rate(self, target_rate: float):
        """
        調整請求速率
        
        Args:
            target_rate: 目標速率（每秒請求數）
        """
        if self.config.adaptive:
            current_rate = self.get_current_rate()
            
            # 平滑調整
            if target_rate > current_rate:
                self.config.requests_per_second = min(
                    target_rate,
                    self.config.requests_per_second * 1.1
                )
            else:
                self.config.requests_per_second = max(
                    target_rate,
                    self.config.requests_per_second * 0.9
                )
            
            logger.debug(f"調整請求速率到 {self.config.requests_per_second:.2f} req/s")
    
    def get_domain_stats(self) -> Dict[str, Dict]:
        """
        獲取域名統計信息
        
        Returns:
            Dict[str, Dict]: 域名統計信息
        """
        stats = {}
        now = time.time()
        
        for domain, info in self.domain_limits.items():
            stats[domain] = {
                "request_count": info["request_count"],
                "failure_count": info["failure_count"],
                "last_request_ago": now - info["last_request"],
                "in_penalty": now < info["penalty_until"],
                "penalty_remaining": max(0, info["penalty_until"] - now)
            }
        
        return stats
    
    def reset_domain(self, domain: str):
        """
        重置域名限制信息
        
        Args:
            domain: 要重置的域名
        """
        if domain in self.domain_limits:
            del self.domain_limits[domain]
            logger.info(f"已重置域名 {domain} 的限制信息")

class AdaptiveRateLimiter(RateLimiter):
    """自適應速率限制器，根據服務器響應自動調整速率"""
    
    def __init__(self, config: RateLimitConfig = None):
        super().__init__(config)
        self.response_times = []
        self.error_rates = {}
        
    def record_response(self, domain: str, response_time: float, success: bool):
        """
        記錄響應信息用於自適應調整
        
        Args:
            domain: 域名
            response_time: 響應時間
            success: 是否成功
        """
        now = time.time()
        
        # 記錄響應時間
        self.response_times.append((now, response_time))
        # 只保留最近100個響應時間
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]
        
        # 記錄錯誤率
        if domain not in self.error_rates:
            self.error_rates[domain] = {"total": 0, "errors": 0}
        
        self.error_rates[domain]["total"] += 1
        if not success:
            self.error_rates[domain]["errors"] += 1
        
        # 自適應調整
        self._adaptive_adjust(domain)
    
    def _adaptive_adjust(self, domain: str):
        """
        根據響應情況自適應調整速率
        
        Args:
            domain: 域名
        """
        if not self.config.adaptive:
            return
        
        # 計算平均響應時間
        now = time.time()
        recent_times = [rt for ts, rt in self.response_times if now - ts < 300]  # 5分鐘內
        
        if recent_times:
            avg_response_time = sum(recent_times) / len(recent_times)
            
            # 響應時間過長時降低速率
            if avg_response_time > 5.0:
                self.adjust_rate(self.config.requests_per_second * 0.8)
            elif avg_response_time < 1.0:
                self.adjust_rate(self.config.requests_per_second * 1.1)
        
        # 錯誤率過高時降低速率
        if domain in self.error_rates:
            error_rate = self.error_rates[domain]["errors"] / max(self.error_rates[domain]["total"], 1)
            if error_rate > 0.1:  # 錯誤率超過10%
                self.adjust_rate(self.config.requests_per_second * 0.7)
                self.report_failure(domain, severe=True)

    def apply_to_crawl4ai(self, session):
        """將限速器套用至 crawl4ai session"""

        async def _before_request(url: str, request_kwargs: dict):
            """請求前取得令牌並檢查 robots 延遲"""
            domain = urlparse(url).netloc

            # 若 robots_handler 提供 crawl-delay，調整最小等待時間
            robots_handler = getattr(session, "robots_handler", None)
            if robots_handler:
                try:
                    crawl_delay = None
                    if hasattr(robots_handler, "get_crawl_delay"):
                        crawl_delay = robots_handler.get_crawl_delay(domain)
                        if asyncio.iscoroutine(crawl_delay):
                            crawl_delay = await crawl_delay
                    elif hasattr(robots_handler, "crawl_delay"):
                        crawl_delay = robots_handler.crawl_delay
                    if crawl_delay:
                        self.config.min_delay = max(self.config.min_delay, float(crawl_delay))
                except Exception:
                    pass

            # 記錄開始時間與域名
            self._current_domain = domain
            self._current_start = time.time()

            await self.acquire_async(domain)

        async def _after_request(result):
            """請求成功後記錄響應時間"""
            duration = time.time() - getattr(self, "_current_start", time.time())
            domain = getattr(self, "_current_domain", "")
            self.record_response(domain, duration, True)

        async def _on_error(exc):
            """請求失敗後記錄錯誤"""
            duration = time.time() - getattr(self, "_current_start", time.time())
            domain = getattr(self, "_current_domain", "")
            self.record_response(domain, duration, False)

        # 註冊 crawl4ai 的 hooks
        if hasattr(session, "crawler_strategy") and hasattr(session.crawler_strategy, "set_hook"):
            session.crawler_strategy.set_hook("before_request", _before_request)
            session.crawler_strategy.set_hook("after_request", _after_request)
            session.crawler_strategy.set_hook("on_error", _on_error)

        return self

