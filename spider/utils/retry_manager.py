"""
重試管理器
提供智能重試機制，包括指數退避和自適應延遲
"""

import time
import random
import logging
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RetryReason(Enum):
    """重試原因枚舉"""
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout" 
    SERVER_ERROR = "server_error"
    RATE_LIMITED = "rate_limited"
    TEMPORARY_FAILURE = "temporary_failure"

@dataclass
class RetryConfig:
    """重試配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    backoff_strategy: str = "exponential"  # "exponential", "linear", "fixed"

class RetryManager:
    """重試管理器"""
    
    def __init__(self, config: RetryConfig = None):
        """
        初始化重試管理器
        
        Args:
            config: 重試配置
        """
        self.config = config or RetryConfig()
        self.retry_stats: Dict[str, Dict] = {}
        
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        判斷是否應該重試
        
        Args:
            exception: 發生的異常
            attempt: 當前嘗試次數
            
        Returns:
            bool: 是否應該重試
        """
        if attempt >= self.config.max_retries:
            return False
            
        # 根據異常類型判斷是否應該重試
        retry_exceptions = (
            ConnectionError,
            TimeoutError,
            OSError,
        )
        
        # 網絡相關錯誤通常值得重試
        if isinstance(exception, retry_exceptions):
            return True
            
        # HTTP 狀態碼相關
        if hasattr(exception, 'status_code'):
            status_code = exception.status_code
            # 5xx 服務器錯誤值得重試
            if 500 <= status_code < 600:
                return True
            # 429 (Too Many Requests) 值得重試
            if status_code == 429:
                return True
            # 4xx 客戶端錯誤通常不值得重試
            if 400 <= status_code < 500:
                return False
                
        return False
    
    def calculate_delay(self, attempt: int, reason: RetryReason = None) -> float:
        """
        計算重試延遲時間
        
        Args:
            attempt: 當前嘗試次數
            reason: 重試原因
            
        Returns:
            float: 延遲秒數
        """
        if self.config.backoff_strategy == "exponential":
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        elif self.config.backoff_strategy == "linear":
            delay = self.config.base_delay * (attempt + 1)
        else:  # fixed
            delay = self.config.base_delay
            
        # 限制最大延遲
        delay = min(delay, self.config.max_delay)
        
        # 添加隨機抖動
        if self.config.jitter:
            jitter_range = delay * 0.1  # 10% 抖動
            delay += random.uniform(-jitter_range, jitter_range)
            
        # 針對特定原因調整延遲
        if reason == RetryReason.RATE_LIMITED:
            delay *= 2  # 速率限制時加倍延遲
        elif reason == RetryReason.SERVER_ERROR:
            delay *= 1.5  # 服務器錯誤時增加延遲
            
        return max(delay, 0.1)  # 最小延遲 0.1 秒
    
    def retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """
        使用退避策略重試函數
        
        Args:
            func: 要重試的函數
            *args: 函數參數
            **kwargs: 函數關鍵字參數
            
        Returns:
            Any: 函數執行結果
            
        Raises:
            Exception: 重試耗盡後的最後一個異常
        """
        last_exception = None
        func_name = func.__name__ if hasattr(func, '__name__') else str(func)
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # 記錄重試統計
                if func_name not in self.retry_stats:
                    self.retry_stats[func_name] = {
                        "total_attempts": 0,
                        "total_retries": 0,
                        "success_count": 0,
                        "failure_count": 0
                    }
                
                self.retry_stats[func_name]["total_attempts"] += 1
                
                # 執行函數
                result = func(*args, **kwargs)
                
                # 成功
                self.retry_stats[func_name]["success_count"] += 1
                if attempt > 0:
                    logger.info(f"✅ {func_name} 在第 {attempt + 1} 次嘗試後成功")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries and self.should_retry(e, attempt):
                    # 確定重試原因
                    reason = self._determine_retry_reason(e)
                    delay = self.calculate_delay(attempt, reason)
                    
                    self.retry_stats[func_name]["total_retries"] += 1
                    
                    logger.warning(
                        f"⚠️ {func_name} 第 {attempt + 1} 次嘗試失敗: {e}，"
                        f"{delay:.2f}秒後重試 (原因: {reason.value})"
                    )
                    
                    time.sleep(delay)
                else:
                    # 不再重試
                    self.retry_stats[func_name]["failure_count"] += 1
                    break
        
        # 重試耗盡，拋出最後一個異常
        logger.error(f"❌ {func_name} 重試 {self.config.max_retries} 次後仍然失敗")
        raise last_exception
    
    def _determine_retry_reason(self, exception: Exception) -> RetryReason:
        """
        根據異常確定重試原因
        
        Args:
            exception: 發生的異常
            
        Returns:
            RetryReason: 重試原因
        """
        if isinstance(exception, TimeoutError):
            return RetryReason.TIMEOUT
        elif isinstance(exception, ConnectionError):
            return RetryReason.NETWORK_ERROR
        elif hasattr(exception, 'status_code'):
            if exception.status_code == 429:
                return RetryReason.RATE_LIMITED
            elif 500 <= exception.status_code < 600:
                return RetryReason.SERVER_ERROR
                
        return RetryReason.TEMPORARY_FAILURE
    
    def get_retry_stats(self) -> Dict[str, Dict]:
        """
        獲取重試統計信息
        
        Returns:
            Dict[str, Dict]: 重試統計信息
        """
        return self.retry_stats.copy()
    
    def reset_stats(self):
        """重置統計信息"""
        self.retry_stats.clear()
        
    def adaptive_retry(self, func: Callable, context: str = None, *args, **kwargs) -> Any:
        """
        自適應重試，根據歷史成功率調整策略
        
        Args:
            func: 要重試的函數
            context: 上下文標識符
            *args: 函數參數
            **kwargs: 函數關鍵字參數
            
        Returns:
            Any: 函數執行結果
        """
        func_key = context or (func.__name__ if hasattr(func, '__name__') else str(func))
        
        # 根據歷史成功率調整配置
        if func_key in self.retry_stats:
            stats = self.retry_stats[func_key]
            success_rate = stats["success_count"] / max(stats["total_attempts"], 1)
            
            # 成功率低時增加重試次數和延遲
            if success_rate < 0.5:
                original_max_retries = self.config.max_retries
                original_base_delay = self.config.base_delay
                
                self.config.max_retries = min(self.config.max_retries + 2, 10)
                self.config.base_delay *= 1.5
                
                try:
                    return self.retry_with_backoff(func, *args, **kwargs)
                finally:
                    # 恢復原始配置
                    self.config.max_retries = original_max_retries
                    self.config.base_delay = original_base_delay
        
        return self.retry_with_backoff(func, *args, **kwargs)
