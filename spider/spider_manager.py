"""
爬蟲管理器
整合爬蟲、分塊、資料庫等功能的主控制器
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .crawlers.web_crawler import WebCrawler, CrawlResult
from .crawlers.sitemap_parser import SitemapParser, SitemapEntry
from .db.crawler_db import CrawlerDB, CrawlStatus
from .chunking.chunker_factory import ChunkerFactory
from .utils.retry_manager import RetryConfig
from .utils.rate_limiter import RateLimitConfig

# 修復相對導入問題
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import Config

logger = logging.getLogger(__name__)

class SpiderManager:
    """
    爬蟲管理器
    
    提供完整的爬蟲工作流程：
    1. 解析 sitemap
    2. 爬取網頁內容
    3. 文本分塊
    4. 資料庫存儲
    5. 錯誤處理和重試
    """
    
    def __init__(self, 
                 db_config: Dict[str, str] = None,
                 crawler_config: Dict[str, Any] = None,
                 chunker_type: str = "sliding_window",
                 chunker_config: Dict[str, Any] = None):
        """
        初始化爬蟲管理器
        
        Args:
            db_config: 資料庫配置
            crawler_config: 爬蟲配置
            chunker_type: 分塊器類型
            chunker_config: 分塊器配置
        """
        # 初始化資料庫
        if db_config:
            self.db = CrawlerDB(**db_config)
        else:
            self.db = CrawlerDB()
        
        # 初始化爬蟲
        retry_config = RetryConfig(
            max_retries=Config.RATE_LIMIT_MAX_RETRIES,
            base_delay=Config.RATE_LIMIT_BASE_DELAY_MIN,
            max_delay=Config.RATE_LIMIT_MAX_DELAY
        )
        
        rate_config = RateLimitConfig(
            requests_per_second=1.0 / Config.CRAWLER_DELAY
        )
        
        self.crawler = WebCrawler(
            db=self.db,
            retry_config=retry_config,
            rate_config=rate_config
        )
        
        # 初始化 sitemap 解析器
        self.sitemap_parser = SitemapParser(
            retry_config=retry_config,
            rate_config=rate_config
        )
        
        # 初始化分塊器
        self.chunker = ChunkerFactory.create_chunker(
            chunker_type, 
            chunker_config or {}
        )
        
        # 統計信息
        self.stats = {
            "session_start": datetime.now(),
            "total_urls_discovered": 0,
            "total_urls_crawled": 0,
            "total_chunks_created": 0,
            "errors": []
        }
        
        logger.info("SpiderManager 初始化完成")
    
    async def initialize(self) -> bool:
        """
        初始化管理器，建立資料庫連接等
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 連接資料庫
            if not self.db.connect():
                logger.error("資料庫連接失敗")
                return False
            
            # 創建必要的表
            if not self.db.create_tables():
                logger.error("創建資料表失敗")
                return False
            
            logger.info("SpiderManager 初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"SpiderManager 初始化失敗: {e}")
            return False
    
    async def crawl_from_sitemap(self, sitemap_url: str,
                               url_filters: Dict[str, Any] = None,
                               max_urls: int = None,
                               force_recrawl: bool = False) -> Dict[str, Any]:
        """
        從 sitemap 開始完整的爬取流程
        
        Args:
            sitemap_url: sitemap URL
            url_filters: URL 過濾條件
            max_urls: 最大爬取 URL 數量
            force_recrawl: 是否強制重新爬取
            
        Returns:
            Dict[str, Any]: 爬取結果統計
        """
        logger.info(f"開始從 sitemap 爬取: {sitemap_url}")
        
        try:
            # 1. 解析 sitemap
            sitemap_entries = await self.sitemap_parser.parse_sitemaps([sitemap_url])
            
            if not sitemap_entries:
                logger.warning(f"未從 sitemap 獲取到任何 URLs: {sitemap_url}")
                return {"error": "未獲取到 URLs"}
            
            logger.info(f"從 sitemap 獲取到 {len(sitemap_entries)} 個 URLs")
            self.stats["total_urls_discovered"] += len(sitemap_entries)
            
            # 2. 過濾 URLs
            filtered_entries = self._filter_sitemap_entries(sitemap_entries, url_filters)
            
            # 3. 限制數量
            if max_urls and len(filtered_entries) > max_urls:
                filtered_entries = filtered_entries[:max_urls]
                logger.info(f"限制爬取數量為 {max_urls}")
            
            # 4. 提取 URLs
            urls_to_crawl = [entry.url for entry in filtered_entries]
            
            # 5. 執行爬取
            crawl_results = await self.crawl_urls(urls_to_crawl, force_recrawl)
            
            # 6. 處理爬取結果
            processing_results = await self._process_crawl_results(crawl_results)
            
            return {
                "sitemap_url": sitemap_url,
                "urls_discovered": len(sitemap_entries),
                "urls_filtered": len(filtered_entries),
                "urls_crawled": len(crawl_results),
                "successful_crawls": len([r for r in crawl_results if r.success]),
                "failed_crawls": len([r for r in crawl_results if not r.success]),
                "chunks_created": processing_results.get("total_chunks", 0),
                "processing_errors": processing_results.get("errors", [])
            }
            
        except Exception as e:
            error_msg = f"sitemap 爬取過程中發生錯誤: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return {"error": error_msg}
    
    async def crawl_urls(self, urls: List[str], 
                        force_recrawl: bool = False,
                        max_concurrent: int = None) -> List[CrawlResult]:
        """
        爬取指定的 URLs
        
        Args:
            urls: 要爬取的 URL 列表
            force_recrawl: 是否強制重新爬取
            max_concurrent: 最大並發數
            
        Returns:
            List[CrawlResult]: 爬取結果列表
        """
        if not urls:
            return []
        
        logger.info(f"開始爬取 {len(urls)} 個 URLs")
        
        # 添加 URLs 到資料庫
        added_count = self.db.add_urls_batch(urls)
        logger.info(f"添加了 {added_count} 個新 URLs 到資料庫")
        
        # 執行爬取
        results = await self.crawler.crawl_urls_batch(
            urls, 
            max_concurrent or Config.CRAWLER_MAX_CONCURRENT,
            force_recrawl
        )
        
        self.stats["total_urls_crawled"] += len(results)
        return results
    
    async def _process_crawl_results(self, crawl_results: List[CrawlResult]) -> Dict[str, Any]:
        """
        處理爬取結果，包括分塊等
        
        Args:
            crawl_results: 爬取結果列表
            
        Returns:
            Dict[str, Any]: 處理結果統計
        """
        total_chunks = 0
        processing_errors = []
        
        for result in crawl_results:
            if not result.success or not result.content:
                continue
            
            try:
                # 執行文本分塊
                chunks = self.chunker.chunk(
                    result.content,
                    metadata={
                        "source_url": result.url,
                        "crawl_timestamp": datetime.now().isoformat(),
                        "title": result.title
                    }
                )
                
                total_chunks += len(chunks)
                
                # 這裡可以將分塊結果存儲到向量資料庫等
                # await self._store_chunks(chunks)
                
            except Exception as e:
                error_msg = f"處理爬取結果失敗 {result.url}: {e}"
                logger.error(error_msg)
                processing_errors.append(error_msg)
        
        self.stats["total_chunks_created"] += total_chunks
        
        return {
            "total_chunks": total_chunks,
            "errors": processing_errors
        }
    
    def _filter_sitemap_entries(self, entries: List[SitemapEntry],
                              filters: Dict[str, Any] = None) -> List[SitemapEntry]:
        """
        過濾 sitemap 條目
        
        Args:
            entries: sitemap 條目列表
            filters: 過濾條件
            
        Returns:
            List[SitemapEntry]: 過濾後的條目
        """
        if not filters:
            return entries
        
        filtered = entries
        
        # URL 模式過濾
        if "include_patterns" in filters:
            patterns = filters["include_patterns"]
            filtered = [e for e in filtered 
                       if any(pattern in e.url for pattern in patterns)]
        
        if "exclude_patterns" in filters:
            patterns = filters["exclude_patterns"]
            filtered = [e for e in filtered 
                       if not any(pattern in e.url for pattern in patterns)]
        
        # 優先級過濾
        if "min_priority" in filters:
            min_priority = filters["min_priority"]
            filtered = [e for e in filtered 
                       if e.priority is None or e.priority >= min_priority]
        
        # 修改時間過濾
        if "since_date" in filters:
            since_date = filters["since_date"]
            filtered = [e for e in filtered 
                       if e.lastmod is None or e.lastmod >= since_date]
        
        logger.info(f"過濾後剩餘 {len(filtered)}/{len(entries)} 個 URLs")
        return filtered
    
    async def retry_failed_crawls(self, max_retries: int = 3) -> Dict[str, Any]:
        """
        重試失敗的爬取
        
        Args:
            max_retries: 最大重試次數
            
        Returns:
            Dict[str, Any]: 重試結果
        """
        logger.info(f"開始重試失敗的爬取，最大重試次數: {max_retries}")
        
        retry_results = await self.crawler.retry_failed_urls(max_retries)
        
        successful_retries = len([r for r in retry_results if r.success])
        failed_retries = len([r for r in retry_results if not r.success])
        
        logger.info(f"重試完成: 成功 {successful_retries}，失敗 {failed_retries}")
        
        return {
            "total_retried": len(retry_results),
            "successful": successful_retries,
            "failed": failed_retries,
            "results": retry_results
        }
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """
        獲取綜合統計信息
        
        Returns:
            Dict[str, Any]: 統計信息
        """
        stats = self.stats.copy()
        
        # 添加各組件的統計
        stats.update({
            "crawler_stats": self.crawler.get_stats(),
            "db_stats": self.db.get_crawl_statistics() if self.db else {},
            "sitemap_parser_stats": self.sitemap_parser.get_stats(),
            "chunker_stats": self.chunker.get_stats()
        })
        
        # 計算運行時間
        if "session_start" in stats:
            runtime = datetime.now() - stats["session_start"]
            stats["session_runtime_seconds"] = runtime.total_seconds()
        
        return stats
    
    async def cleanup_old_data(self, days: int = 30) -> Dict[str, Any]:
        """
        清理舊資料
        
        Args:
            days: 保留天數
            
        Returns:
            Dict[str, Any]: 清理結果
        """
        if not self.db:
            return {"error": "無資料庫連接"}
        
        deleted_count = self.db.cleanup_old_records(days)
        
        return {
            "deleted_records": deleted_count,
            "retention_days": days
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        Returns:
            Dict[str, Any]: 健康狀態
        """
        health = {
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # 檢查資料庫
        try:
            if self.db and self.db.client:
                self.db.client.table("pg_tables").select("*").limit(1).execute()
                health["components"]["database"] = "healthy"
            else:
                health["components"]["database"] = "disconnected"
        except Exception as e:
            health["components"]["database"] = f"error: {e}"
        
        # 檢查分塊器
        try:
            test_chunks = self.chunker.chunk("測試文本")
            health["components"]["chunker"] = "healthy"
        except Exception as e:
            health["components"]["chunker"] = f"error: {e}"
        
        # 整體狀態
        component_statuses = list(health["components"].values())
        if all(status == "healthy" for status in component_statuses):
            health["overall_status"] = "healthy"
        elif any("error" in status for status in component_statuses):
            health["overall_status"] = "error"
        else:
            health["overall_status"] = "warning"
        
        return health

# 便捷函數
async def quick_crawl(sitemap_url: str, max_urls: int = 10, **kwargs) -> Dict[str, Any]:
    """
    快速爬取便捷函數
    
    Args:
        sitemap_url: sitemap URL
        max_urls: 最大爬取數量
        **kwargs: 其他參數
        
    Returns:
        Dict[str, Any]: 爬取結果
    """
    manager = SpiderManager(**kwargs)
    
    if not await manager.initialize():
        return {"error": "初始化失敗"}
    
    return await manager.crawl_from_sitemap(sitemap_url, max_urls=max_urls)
