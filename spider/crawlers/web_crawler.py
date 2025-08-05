"""
強化版網頁爬蟲
集成重試、速率限制、錯誤處理和資料庫記錄功能
"""

import asyncio
import logging
import time
import hashlib
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime

from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode, AsyncWebCrawler
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher

from ..utils.retry_manager import RetryManager, RetryConfig
from ..utils.rate_limiter import AdaptiveRateLimiter, RateLimitConfig

# 修復相對導入問題
import sys
import os

# 從環境變數讀取配置
RATE_LIMIT_MAX_RETRIES = int(os.getenv('RATE_LIMIT_MAX_RETRIES', '2'))
RATE_LIMIT_BASE_DELAY_MIN = float(os.getenv('RATE_LIMIT_BASE_DELAY_MIN', '1.0'))
RATE_LIMIT_MAX_DELAY = float(os.getenv('RATE_LIMIT_MAX_DELAY', '30.0'))
CRAWLER_DELAY = float(os.getenv('CRAWLER_DELAY', '2.5'))
CRAWLER_VERBOSE = os.getenv('CRAWLER_VERBOSE', 'true').lower() == 'true'
CRAWLER_HEADLESS = os.getenv('CRAWLER_HEADLESS', 'true').lower() == 'true'
BROWSER_VIEWPORT_WIDTH = int(os.getenv('BROWSER_VIEWPORT_WIDTH', '1920'))
BROWSER_VIEWPORT_HEIGHT = int(os.getenv('BROWSER_VIEWPORT_HEIGHT', '1080'))
CRAWLER_TIMEOUT = int(os.getenv('CRAWLER_TIMEOUT', '60000'))
CRAWLER_MAX_CONCURRENT = int(os.getenv('CRAWLER_MAX_CONCURRENT', '10'))

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from database import SupabaseClient, DatabaseOperations
from database.models import CrawlStatus

logger = logging.getLogger(__name__)

@dataclass
class CrawlResult:
    """爬取結果"""
    url: str
    url_hash: str
    success: bool
    title: Optional[str] = None
    content: Optional[str] = None
    markdown: Optional[str] = None
    raw_html: Optional[str] = None
    links: Optional[List[Dict]] = None
    images: Optional[List[Dict]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    response_time: Optional[float] = None
    content_length: Optional[int] = None

class WebCrawler:
    """強化版網頁爬蟲"""
    
    def __init__(self, 
                 retry_config: RetryConfig = None,
                 rate_config: RateLimitConfig = None):
        """
        初始化網頁爬蟲
        
        Args:
            retry_config: 重試配置
            rate_config: 速率限制配置
        """
        self.retry_manager = RetryManager(retry_config or RetryConfig(
            max_retries=RATE_LIMIT_MAX_RETRIES,
            base_delay=RATE_LIMIT_BASE_DELAY_MIN,
            max_delay=RATE_LIMIT_MAX_DELAY
        ))
        self.rate_limiter = AdaptiveRateLimiter(rate_config or RateLimitConfig(
            requests_per_second=1.0 / CRAWLER_DELAY,
            adaptive=True
        ))
        
        # 初始化數據庫連接（可選）
        self.db = None
        try:
            db_client = SupabaseClient()
            client = db_client.get_client()
            if client:
                self.db = DatabaseOperations(client)
        except Exception as e:
            logger.warning(f"無法初始化數據庫連接: {e}")
        
        # 統計信息
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None
        }
        
    def _create_browser_config(self) -> BrowserConfig:
        """創建簡化的瀏覽器配置"""
        return BrowserConfig(
            verbose=CRAWLER_VERBOSE,
            headless=CRAWLER_HEADLESS,
            viewport_width=BROWSER_VIEWPORT_WIDTH,
            viewport_height=BROWSER_VIEWPORT_HEIGHT,
            extra_args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ],
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-TW,en-US;q=0.9,en;q=0.8",
                "User-Agent": "Mozilla/5.0 (compatible; Spider/1.0)"
            }
        )
    
    def _create_run_config(self) -> CrawlerRunConfig:
        """創建簡化的運行配置"""
        return CrawlerRunConfig(
            verbose=CRAWLER_VERBOSE,
            word_count_threshold=10,
            excluded_tags=['form', 'header', 'footer', 'nav'],
            cache_mode=CacheMode.ENABLED,
            page_timeout=CRAWLER_TIMEOUT,
        )
    
    async def crawl_url(self, url: str, force: bool = False) -> CrawlResult:
        """
        爬取單個 URL
        
        Args:
            url: 要爬取的 URL
            force: 是否強制重新爬取
            
        Returns:
            CrawlResult: 爬取結果
        """
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        domain = urlparse(url).netloc
        start_time = time.time()
        
        # 檢查是否已處理
        if self.db and not force:
            is_processed, status = self.db.is_url_processed(url)
            if is_processed and status == CrawlStatus.SUCCESS:
                logger.info(f"URL 已成功處理，跳過: {url}")
                self.stats["skipped"] += 1
                return CrawlResult(
                    url=url, 
                    url_hash=url_hash, 
                    success=True,
                    metadata={"skipped": True, "reason": "already_processed"}
                )
        
        # 更新狀態為處理中
        if self.db:
            self.db.update_crawl_status(url_hash, CrawlStatus.IN_PROGRESS)
        
        try:
            # 應用速率限制
            await self.rate_limiter.acquire_async(domain)
            
            # 執行爬取
            result = await self._perform_crawl(url)
            
            # 記錄響應時間
            response_time = time.time() - start_time
            result.response_time = response_time
            
            # 記錄響應信息到速率限制器
            self.rate_limiter.record_response(domain, response_time, result.success)
            
            # 更新資料庫
            if self.db:
                if result.success:
                    self.db.update_crawl_status(
                        url_hash, CrawlStatus.SUCCESS,
                        content_length=result.content_length,
                        response_time=response_time
                    )
                    self.db.save_content(
                        url_hash=url_hash,
                        title=result.title,
                        content=result.content,
                        markdown_content=result.markdown,
                        raw_html=result.raw_html,
                        links=result.links,
                        images=result.images,
                        metadata=result.metadata
                    )
                    self.stats["successful"] += 1
                else:
                    self.db.update_crawl_status(
                        url_hash, CrawlStatus.FAILED,
                        error_msg=result.error,
                        response_time=response_time
                    )
                    self.stats["failed"] += 1
            
            self.stats["total_processed"] += 1
            return result
            
        except Exception as e:
            logger.error(f"爬取 URL 時發生未預期錯誤 {url}: {e}")
            
            # 記錄失敗
            if self.db:
                self.db.update_crawl_status(url_hash, CrawlStatus.FAILED, error_msg=str(e))
            
            self.rate_limiter.report_failure(domain, severe=True)
            self.stats["failed"] += 1
            self.stats["total_processed"] += 1
            
            return CrawlResult(
                url=url,
                url_hash=url_hash,
                success=False,
                error=str(e),
                response_time=time.time() - start_time
            )
    
    async def _perform_crawl(self, url: str) -> CrawlResult:
        """執行實際的爬取操作"""
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        
        browser_config = self._create_browser_config()
        run_config = self._create_run_config()
        
        try:
            # 簡化的爬取邏輯
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if not result.success:
                    raise Exception(f"爬取失敗: {result.error_message}")
                
                # 提取基本數據
                title = getattr(result, 'metadata', {}).get('title', '') or ''
                content = getattr(result, 'cleaned_html', '') or ''
                raw_html = getattr(result, 'html', '') or ''
                
                # 簡化的鏈接和圖片提取
                links = []
                images = []
                
                if hasattr(result, 'links') and result.links:
                    internal_links = result.links.get('internal', [])
                    external_links = result.links.get('external', [])
                    links = [{'url': link, 'type': 'internal'} for link in internal_links]
                    links.extend([{'url': link, 'type': 'external'} for link in external_links])
                
                content_length = len(content)
                
                return CrawlResult(
                    url=url,
                    url_hash=url_hash,
                    success=True,
                    title=title,
                    content=content,
                    raw_html=raw_html,
                    links=links,
                    images=images,
                    content_length=content_length,
                    metadata={
                        "crawl_timestamp": datetime.now().isoformat(),
                        "links_count": len(links),
                        "content_length": content_length
                    }
                )
                
        except Exception as e:
            logger.error(f"執行爬取失敗 {url}: {e}")
            return CrawlResult(
                url=url,
                url_hash=url_hash,
                success=False,
                error=str(e)
            )
    
    async def crawl_urls_batch(self, urls: List[str], 
                              max_concurrent: int = None,
                              force: bool = False) -> List[CrawlResult]:
        """
        批量爬取 URLs
        
        Args:
            urls: URL 列表
            max_concurrent: 最大並發數
            force: 是否強制重新爬取
            
        Returns:
            List[CrawlResult]: 爬取結果列表
        """
        if not urls:
            return []
        
        max_concurrent = max_concurrent or CRAWLER_MAX_CONCURRENT
        self.stats["start_time"] = time.time()
        
        logger.info(f"開始批量爬取 {len(urls)} 個 URLs，最大並發: {max_concurrent}")
        
        # 添加 URLs 到資料庫
        if self.db:
            self.db.add_urls_batch(urls)
        
        # 使用信號量控制並發
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def crawl_with_semaphore(url):
            async with semaphore:
                return await self.crawl_url(url, force)
        
        # 執行批量爬取
        tasks = [crawl_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 處理異常結果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"URL {urls[i]} 爬取時發生異常: {result}")
                url_hash = hashlib.sha256(urls[i].encode('utf-8')).hexdigest()
                final_results.append(CrawlResult(
                    url=urls[i],
                    url_hash=url_hash,
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        self._log_batch_stats()
        return final_results
    
    def _log_batch_stats(self):
        """記錄批量處理統計信息"""
        if self.stats["start_time"]:
            duration = time.time() - self.stats["start_time"]
            total = self.stats["total_processed"]
            successful = self.stats["successful"]
            failed = self.stats["failed"]
            skipped = self.stats["skipped"]
            
            success_rate = (successful / max(total, 1)) * 100
            avg_time = duration / max(total, 1)
            
            logger.info(f"""
=== 爬取統計 ===
總處理數: {total}
成功: {successful} ({success_rate:.1f}%)
失敗: {failed}
跳過: {skipped}
總耗時: {duration:.2f} 秒
平均耗時: {avg_time:.2f} 秒/URL
""")
    
    async def retry_failed_urls(self, max_retries: int = 3) -> List[CrawlResult]:
        """
        重試失敗的 URLs
        
        Args:
            max_retries: 最大重試次數
            
        Returns:
            List[CrawlResult]: 重試結果
        """
        if not self.db:
            logger.warning("無資料庫連接，無法重試失敗的 URLs")
            return []
        
        failed_urls = self.db.get_failed_urls(max_retries)
        if not failed_urls:
            logger.info("沒有需要重試的失敗 URLs")
            return []
        
        logger.info(f"重試 {len(failed_urls)} 個失敗的 URLs")
        urls_to_retry = [url for url, _, _ in failed_urls]
        
        return await self.crawl_urls_batch(urls_to_retry, force=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取爬蟲統計信息
        
        Returns:
            Dict[str, Any]: 統計信息
        """
        stats = self.stats.copy()
        stats.update({
            "retry_stats": self.retry_manager.get_retry_stats(),
            "rate_limiter_stats": self.rate_limiter.get_domain_stats()
        })
        
        if self.db:
            stats["db_stats"] = self.db.get_crawl_statistics()
        
        return stats
    
    def reset_stats(self):
        """重置統計信息"""
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None
        }
        self.retry_manager.reset_stats()

# 便捷函數
async def crawl_single_url(url: str, **kwargs) -> CrawlResult:
    """
    便捷函數：爬取單個 URL
    
    Args:
        url: 要爬取的 URL
        **kwargs: 其他參數
        
    Returns:
        CrawlResult: 爬取結果
    """
    crawler = WebCrawler(**kwargs)
    return await crawler.crawl_url(url)

async def crawl_multiple_urls(urls: List[str], **kwargs) -> List[CrawlResult]:
    """
    便捷函數：爬取多個 URLs
    
    Args:
        urls: URL 列表
        **kwargs: 其他參數
        
    Returns:
        List[CrawlResult]: 爬取結果列表
    """
    crawler = WebCrawler(**kwargs)
    return await crawler.crawl_urls_batch(urls)
