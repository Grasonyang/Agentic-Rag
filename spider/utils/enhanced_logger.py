"""
增強的日誌記錄系統
支援結構化日誌、錯誤追蹤和性能監控
"""

import logging
import logging.handlers
import json
import time
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import os


class StructuredFormatter(logging.Formatter):
    """結構化日誌格式器"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加額外的上下文信息
        if hasattr(record, 'url'):
            log_data['url'] = record.url
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration
        if hasattr(record, 'error_type'):
            log_data['error_type'] = record.error_type
        if hasattr(record, 'retry_count'):
            log_data['retry_count'] = record.retry_count
            
        # 如果是異常記錄，添加詳細的異常信息
        if record.exc_info:
            log_data['exception'] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class SpiderLogger:
    """爬蟲專用日誌記錄器"""
    
    def __init__(self, name: str = "rag_spider", log_dir: str = "logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 創建logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重複添加handler
        if not self.logger.handlers:
            self._setup_handlers()
        
        # 統計信息
        self.stats = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "total_duration": 0.0,
            "errors_by_type": {},
            "start_time": time.time()
        }
    
    def _setup_handlers(self):
        """設置日誌處理器"""
        
        # 1. 控制台處理器 - 簡潔格式
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # 2. 文件處理器 - 詳細格式
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.name}.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # 3. 結構化日誌處理器 - JSON格式
        structured_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.name}_structured.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        structured_handler.setLevel(logging.DEBUG)
        structured_handler.setFormatter(StructuredFormatter())
        
        # 4. 錯誤日誌處理器 - 只記錄錯誤
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.name}_errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        # 添加處理器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(structured_handler)
        self.logger.addHandler(error_handler)
    
    def log_request_start(self, url: str, method: str = "GET") -> Dict[str, Any]:
        """記錄請求開始"""
        context = {
            "url": url,
            "method": method,
            "start_time": time.time(),
            "request_id": f"{int(time.time() * 1000)}"
        }
        
        self.logger.info(
            f"🚀 開始請求: {method} {url}",
            extra={"url": url, "request_id": context["request_id"]}
        )
        
        self.stats["requests_total"] += 1
        return context
    
    def log_request_success(self, context: Dict[str, Any], status_code: int = 200, 
                          content_length: int = 0):
        """記錄請求成功"""
        duration = time.time() - context["start_time"]
        
        self.logger.info(
            f"✅ 請求成功: {context['url']} ({status_code}) - {duration:.2f}s - {content_length} bytes",
            extra={
                "url": context["url"],
                "status_code": status_code,
                "duration": duration,
                "content_length": content_length,
                "request_id": context["request_id"]
            }
        )
        
        self.stats["requests_success"] += 1
        self.stats["total_duration"] += duration
    
    def log_request_error(self, context: Dict[str, Any], error: Exception, 
                         status_code: Optional[int] = None, retry_count: int = 0):
        """記錄請求錯誤"""
        duration = time.time() - context["start_time"]
        error_type = type(error).__name__
        
        self.logger.error(
            f"❌ 請求失敗: {context['url']} - {error_type}: {str(error)} (重試: {retry_count})",
            extra={
                "url": context["url"],
                "error_type": error_type,
                "status_code": status_code,
                "duration": duration,
                "retry_count": retry_count,
                "request_id": context["request_id"]
            },
            exc_info=True
        )
        
        self.stats["requests_failed"] += 1
        self.stats["total_duration"] += duration
        
        # 統計錯誤類型
        if error_type not in self.stats["errors_by_type"]:
            self.stats["errors_by_type"][error_type] = 0
        self.stats["errors_by_type"][error_type] += 1
    
    def log_database_operation(self, operation: str, table: str, success: bool, 
                             count: int = 0, error: Optional[Exception] = None):
        """記錄資料庫操作"""
        if success:
            self.logger.info(
                f"💾 資料庫操作成功: {operation} {table} ({count} 條記錄)",
                extra={"operation": operation, "table": table, "count": count}
            )
        else:
            self.logger.error(
                f"💥 資料庫操作失敗: {operation} {table} - {str(error)}",
                extra={"operation": operation, "table": table, "error_type": type(error).__name__},
                exc_info=True
            )
    
    def log_sitemap_parsing(self, sitemap_url: str, urls_found: int, success: bool, 
                           error: Optional[Exception] = None):
        """記錄 sitemap 解析"""
        if success:
            self.logger.info(
                f"🗺️ Sitemap 解析成功: {sitemap_url} ({urls_found} 個 URLs)",
                extra={"url": sitemap_url, "urls_found": urls_found}
            )
        else:
            self.logger.error(
                f"🗺️ Sitemap 解析失敗: {sitemap_url} - {str(error)}",
                extra={"url": sitemap_url, "error_type": type(error).__name__},
                exc_info=True
            )
    
    def log_content_extraction(self, url: str, title: str, content_length: int, 
                             success: bool, error: Optional[Exception] = None):
        """記錄內容提取"""
        if success:
            self.logger.info(
                f"📄 內容提取成功: {url} - '{title}' ({content_length} 字符)",
                extra={"url": url, "title": title, "content_length": content_length}
            )
        else:
            self.logger.error(
                f"📄 內容提取失敗: {url} - {str(error)}",
                extra={"url": url, "error_type": type(error).__name__},
                exc_info=True
            )
    
    def log_chunking(self, url: str, chunks_created: int, chunk_method: str):
        """記錄內容分塊"""
        self.logger.info(
            f"🔪 內容分塊完成: {url} - {chunks_created} 個塊 ({chunk_method})",
            extra={"url": url, "chunks_created": chunks_created, "chunk_method": chunk_method}
        )
    
    def log_retry_attempt(self, url: str, attempt: int, max_attempts: int, 
                         reason: str, delay: float):
        """記錄重試嘗試"""
        self.logger.warning(
            f"🔄 重試嘗試 {attempt}/{max_attempts}: {url} - {reason} (延遲: {delay:.2f}s)",
            extra={"url": url, "retry_count": attempt, "max_retries": max_attempts, 
                  "retry_reason": reason, "delay": delay}
        )
    
    def log_rate_limit(self, url: str, retry_after: Optional[float] = None):
        """記錄速率限制"""
        message = f"⏳ 觸發速率限制: {url}"
        if retry_after:
            message += f" (建議等待: {retry_after}s)"
        
        self.logger.warning(
            message,
            extra={"url": url, "rate_limited": True, "retry_after": retry_after}
        )
    
    def log_statistics(self):
        """記錄統計信息"""
        runtime = time.time() - self.stats["start_time"]
        success_rate = (self.stats["requests_success"] / max(self.stats["requests_total"], 1)) * 100
        avg_duration = self.stats["total_duration"] / max(self.stats["requests_success"], 1)
        
        stats_message = (
            f"📊 爬蟲統計 - "
            f"運行時間: {runtime:.1f}s, "
            f"總請求: {self.stats['requests_total']}, "
            f"成功: {self.stats['requests_success']}, "
            f"失敗: {self.stats['requests_failed']}, "
            f"成功率: {success_rate:.1f}%, "
            f"平均響應時間: {avg_duration:.2f}s"
        )
        
        self.logger.info(stats_message, extra={"stats": self.stats})
        
        # 記錄錯誤類型分布
        if self.stats["errors_by_type"]:
            for error_type, count in self.stats["errors_by_type"].items():
                self.logger.info(f"  錯誤類型 {error_type}: {count} 次")
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計信息"""
        runtime = time.time() - self.stats["start_time"]
        success_rate = (self.stats["requests_success"] / max(self.stats["requests_total"], 1)) * 100
        avg_duration = self.stats["total_duration"] / max(self.stats["requests_success"], 1)
        
        return {
            **self.stats,
            "runtime": runtime,
            "success_rate": success_rate,
            "avg_duration": avg_duration
        }
    
    def info(self, message: str, **kwargs):
        """信息日誌"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告日誌"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """錯誤日誌"""
        self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """調試日誌"""
        self.logger.debug(message, extra=kwargs)


# 全局日誌記錄器實例
spider_logger = SpiderLogger()

# 便捷函數
def get_spider_logger(name: str = "rag_spider") -> SpiderLogger:
    """獲取爬蟲日誌記錄器"""
    return SpiderLogger(name)
