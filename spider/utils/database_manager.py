"""
增強的數據庫操作管理器
提供連接池、事務管理、重試機制、健康檢查等功能
"""

import asyncio
import time
from typing import Optional, Dict, Any, List, Callable, TypeVar, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging

from database.operations import DatabaseOperations
from database.client import PostgresClient
from database.models import CrawlStatus
from spider.utils.enhanced_logger import get_spider_logger
from spider.utils.retry_manager import RetryManager, RetryConfig


T = TypeVar('T')


@dataclass
class DatabaseConfig:
    """數據庫配置"""
    # 重試設置
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    
    # 連接設置
    connection_timeout: float = 30.0
    query_timeout: float = 60.0
    
    # 健康檢查
    health_check_interval: float = 300.0  # 5分鐘
    max_failed_health_checks: int = 3
    
    # 批量操作
    batch_size: int = 100
    batch_timeout: float = 30.0


class DatabaseHealthMonitor:
    """數據庫健康監控器"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = get_spider_logger("database_health")
        self.failed_checks = 0
        self.last_check = 0.0
        self.is_healthy = True
        
    async def check_health(self, db_ops: DatabaseOperations) -> bool:
        """檢查數據庫健康狀態"""
        now = time.time()
        
        # 檢查是否需要進行健康檢查
        if now - self.last_check < self.config.health_check_interval:
            return self.is_healthy
        
        self.last_check = now
        
        try:
            # 執行簡單的查詢測試連接
            count = db_ops.get_table_count("discovered_urls")
            if count >= 0:  # 包括0，表示表存在但為空
                self.failed_checks = 0
                self.is_healthy = True
                self.logger.debug("數據庫健康檢查通過")
                return True
            else:
                self.failed_checks += 1
                self.logger.warning("數據庫健康檢查失敗：無法獲取表數量")
        except Exception as e:
            self.failed_checks += 1
            self.logger.warning(f"數據庫健康檢查異常: {e}")
        
        # 判斷是否標記為不健康
        if self.failed_checks >= self.config.max_failed_health_checks:
            self.is_healthy = False
            self.logger.error(f"數據庫被標記為不健康，失敗次數: {self.failed_checks}")
        
        return self.is_healthy


class EnhancedDatabaseManager:
    """增強的數據庫管理器"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self.logger = get_spider_logger("database_manager")
        
        self._client: Optional[PostgresClient] = None
        self._db_ops: Optional[DatabaseOperations] = None
        self._health_monitor = DatabaseHealthMonitor(self.config)
        self._retry_manager = RetryManager(RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_delay,
            exponential_base=self.config.retry_backoff
        ))
        
        self._stats = {
            "operations_total": 0,
            "operations_success": 0,
            "operations_failed": 0,
            "retries_total": 0,
            "health_checks": 0,
            "connection_recreated": 0,
            "batch_operations": 0
        }
    
    async def __aenter__(self):
        """異步上下文管理器入口"""
        await self._ensure_connection()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口"""
        await self.close()
    
    async def _ensure_connection(self):
        """確保數據庫連接可用"""
        if not self._client or not self._db_ops:
            await self._create_connection()
        
        # 檢查健康狀態
        if not await self._health_monitor.check_health(self._db_ops):
            self.logger.warning("數據庫健康檢查失敗，正在重新創建連接...")
            await self._create_connection()
    
    async def _create_connection(self):
        """創建數據庫連接"""
        try:
            self._client = PostgresClient()
            if self._client.connect():
                self._db_ops = DatabaseOperations(self._client)
                self._stats["connection_recreated"] += 1
                self.logger.info("數據庫連接已創建")
            else:
                raise Exception("數據庫連接失敗")
                
        except Exception as e:
            self.logger.error(f"創建數據庫連接失敗: {e}")
            raise
    
    def _execute_with_retry(self, operation: Callable[[], T], operation_name: str) -> T:
        """使用重試機制執行操作"""
        self._stats["operations_total"] += 1
        
        try:
            result = self._retry_manager.retry_with_backoff(
                operation
            )
            self._stats["operations_success"] += 1
            return result
        except Exception as e:
            self._stats["operations_failed"] += 1
            self.logger.log_database_operation(
                operation_name, "unknown", False, error=e
            )
            raise
    
    async def _execute_async_with_retry(self, operation: Callable[[], T], operation_name: str) -> T:
        """使用重試機制執行異步操作"""
        self._stats["operations_total"] += 1
        
        try:
            # 確保連接可用
            await self._ensure_connection()
            
            result = operation()
            self._stats["operations_success"] += 1
            return result
        except Exception as e:
            self._stats["operations_failed"] += 1
            self.logger.log_database_operation(
                operation_name, "unknown", False, error=e
            )
            
            # 如果是連接錯誤，嘗試重新連接
            if "connection" in str(e).lower() or "network" in str(e).lower():
                self.logger.warning("檢測到連接錯誤，嘗試重新連接...")
                await self._create_connection()
            
            raise
    
    # ==================== URL 管理 ====================
    
    async def create_discovered_url(self, url_model) -> bool:
        """創建發現的URL記錄"""
        return await self._execute_async_with_retry(
            lambda: self._db_ops.create_discovered_url(url_model),
            f"create_discovered_url"
        )
    
    async def bulk_create_discovered_urls(self, url_models: List) -> int:
        """批量創建發現的URL記錄"""
        self.logger.info(f"Bulk creating {len(url_models)} URL models: {url_models}")
        self._stats["batch_operations"] += 1
        
        # 分批處理大量數據
        total_created = 0
        batch_size = self.config.batch_size
        
        for i in range(0, len(url_models), batch_size):
            batch = url_models[i:i + batch_size]
            
            try:
                count = await self._execute_async_with_retry(
                    lambda: self._db_ops.bulk_create_discovered_urls(batch),
                    f"bulk_create_discovered_urls_batch_{i//batch_size + 1}"
                )
                total_created += count
                
                self.logger.info(f"批量創建URL完成：批次 {i//batch_size + 1}, 創建 {count} 條記錄")
                
            except Exception as e:
                self.logger.error(f"批量創建URL失敗：批次 {i//batch_size + 1}, 錯誤: {e}")
                # 繼續處理下一批次
                continue
        
        self.logger.log_database_operation(
            "bulk_create_discovered_urls", "discovered_urls",
            True, total_created
        )

        return total_created

    async def bulk_insert_discovered_urls(self, url_models: List) -> int:
        """使用 execute_values 批次插入 URL"""
        return await self._execute_async_with_retry(
            lambda: self._db_ops.bulk_insert_discovered_urls(url_models),
            "bulk_insert_discovered_urls",
        )
    
    async def get_pending_urls(self, limit: int = 100) -> List:
        """獲取待處理的URL"""
        return await self._execute_async_with_retry(
            lambda: self._db_ops.get_pending_urls(limit),
            "get_pending_urls"
        )
    
    async def update_crawl_status(self, url_id: str, status: CrawlStatus, error_message: str = None) -> bool:
        """更新爬取狀態"""
        return await self._execute_async_with_retry(
            lambda: self._db_ops.update_crawl_status(url_id, status, error_message),
            f"update_crawl_status_{status.value}"
        )
    
    # ==================== 文章管理 ====================
    
    async def create_article(self, article_model) -> bool:
        """創建文章記錄"""
        return await self._execute_async_with_retry(
            lambda: self._db_ops.create_article(article_model),
            "create_article"
        )
    
    async def create_chunks(self, chunks: List) -> int:
        """創建文章塊"""
        if not chunks:
            return 0
        
        self._stats["batch_operations"] += 1
        
        # 分批處理
        total_created = 0
        batch_size = self.config.batch_size
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            try:
                count = await self._execute_async_with_retry(
                    lambda: self._db_ops.create_chunks(batch),
                    f"create_chunks_batch_{i//batch_size + 1}"
                )
                total_created += count
                
                self.logger.info(f"批量創建文章塊完成：批次 {i//batch_size + 1}, 創建 {count} 條記錄")
                
            except Exception as e:
                self.logger.error(f"批量創建文章塊失敗：批次 {i//batch_size + 1}, 錯誤: {e}")
                continue
        
        self.logger.log_database_operation(
            "create_chunks", "article_chunks", True, total_created
        )
        
        return total_created
    
    # ==================== 統計和監控 ====================
    
    async def get_table_count(self, table_name: str) -> int:
        """獲取表記錄數量"""
        return await self._execute_async_with_retry(
            lambda: self._db_ops.get_table_count(table_name),
            f"get_table_count_{table_name}"
        )
    
    async def get_crawl_progress(self) -> Dict[str, Any]:
        """獲取爬取進度"""
        return await self._execute_async_with_retry(
            lambda: self._db_ops.get_crawl_progress(),
            "get_crawl_progress"
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """獲取數據庫管理器統計信息"""
        db_stats = {}
        
        try:
            # 獲取表統計
            tables = ["sitemaps", "discovered_urls", "articles", "article_chunks"]
            for table in tables:
                try:
                    count = await self.get_table_count(table)
                    db_stats[f"{table}_count"] = count
                except Exception as e:
                    self.logger.warning(f"無法獲取表 {table} 的統計信息: {e}")
                    db_stats[f"{table}_count"] = -1
            
            # 獲取爬取進度
            try:
                progress = await self.get_crawl_progress()
                db_stats["crawl_progress"] = progress
            except Exception as e:
                self.logger.warning(f"無法獲取爬取進度: {e}")
        
        except Exception as e:
            self.logger.error(f"獲取數據庫統計信息失敗: {e}")
        
        return {
            **self._stats,
            "is_healthy": self._health_monitor.is_healthy,
            "failed_health_checks": self._health_monitor.failed_checks,
            "retry_stats": self._retry_manager.get_retry_stats(),
            "database_stats": db_stats
        }
    
    async def close(self):
        """關閉數據庫管理器"""
        if self._client:
            self._client.disconnect()
            self._client = None
            self._db_ops = None
        
        self.logger.info("數據庫管理器已關閉")
    
    @asynccontextmanager
    async def transaction_context(self):
        """事務上下文管理器（簡化版）"""
        await self._ensure_connection()
        try:
            yield self._db_ops
        except Exception as e:
            self.logger.error(f"事務執行失敗: {e}")
            raise
    
    # ==================== 便捷方法 ====================
    
    async def safe_update_crawl_status(self, url_id: str, status: CrawlStatus, 
                                      error_message: str = None) -> bool:
        """安全地更新爬取狀態（忽略錯誤）"""
        try:
            return await self.update_crawl_status(url_id, status, error_message)
        except Exception as e:
            self.logger.warning(f"更新爬取狀態失敗，但將繼續執行: {e}")
            return False
    
    async def batch_update_crawl_status(self, updates: List[Dict[str, Any]]) -> int:
        """批量更新爬取狀態"""
        success_count = 0
        
        for update in updates:
            try:
                url_id = update["url_id"]
                status = update["status"]
                error_message = update.get("error_message")
                
                if await self.update_crawl_status(url_id, status, error_message):
                    success_count += 1
            except Exception as e:
                self.logger.warning(f"批量更新中的單項失敗: {e}")
                continue
        
        self.logger.info(f"批量更新完成：{success_count}/{len(updates)} 成功")
        return success_count


# 便捷函數
async def create_database_manager(config: Optional[DatabaseConfig] = None) -> EnhancedDatabaseManager:
    """創建數據庫管理器"""
    manager = EnhancedDatabaseManager(config)
    await manager._ensure_connection()
    return manager


# 全局數據庫管理器實例（單例模式）
_global_db_manager: Optional[EnhancedDatabaseManager] = None

async def get_global_database_manager() -> EnhancedDatabaseManager:
    """獲取全局數據庫管理器實例"""
    global _global_db_manager
    
    if _global_db_manager is None:
        _global_db_manager = await create_database_manager()
    
    return _global_db_manager

async def close_global_database_manager():
    """關閉全局數據庫管理器"""
    global _global_db_manager
    
    if _global_db_manager:
        await _global_db_manager.close()
        _global_db_manager = None
