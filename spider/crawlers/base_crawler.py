"""
基礎爬蟲模組 (Base Crawler)

功能:
- 提供所有爬蟲類別的基礎功能。
- 封裝通用的網路請求、錯誤處理、日誌記錄和重試機制。
- 整合速率限制和 User-Agent 管理。
"""

import requests
import logging
from typing import Optional, Dict, Any
from ..utils.rate_limiter import RateLimiter
from ..utils.retry_manager import RetryManager

# 設置日誌
logger = logging.getLogger(__name__)

class BaseCrawler:
    """
    所有爬蟲的基礎類別，提供通用的網路功能和配置。
    """
    
    def __init__(
        self,
        user_agent: str = "Gemini-RAG-Crawler/1.0",
        rate_limiter: Optional[RateLimiter] = None,
        retry_manager: Optional[RetryManager] = None,
        request_timeout: int = 30
    ):
        """
        初始化基礎爬蟲。

        Args:
            user_agent (str): HTTP請求的 User-Agent。
            rate_limiter (RateLimiter, optional): 速率限制器實例。
            retry_manager (RetryManager, optional): 重試管理器實例。
            request_timeout (int): 請求超時時間 (秒)。
        """
        self.user_agent = user_agent
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_manager = retry_manager or RetryManager()
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def fetch_url(self, url: str) -> Optional[requests.Response]:
        """
        帶有重試和速率限制的 URL 內容獲取方法。

        Args:
            url (str): 要獲取的目標 URL。

        Returns:
            Optional[requests.Response]: 成功時返回 Response 物件，失敗時返回 None。
        """
        
        def _request_logic():
            # 等待速率限制器
            self.rate_limiter.wait()
            
            logger.info(f"正在抓取 URL: {url}")
            try:
                response = self.session.get(url, timeout=self.request_timeout)
                response.raise_for_status()  # 對於 4xx 或 5xx 的狀態碼拋出異常
                logger.info(f"成功抓取 URL: {url}, 狀態碼: {response.status_code}")
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"抓取 URL 時發生錯誤: {url}, 錯誤: {e}")
                # 返回異常以觸發重試
                raise e

        try:
            # 使用重試管理器執行請求
            return self.retry_manager.execute(_request_logic)
        except Exception as e:
            logger.error(f"經過多次重試後，抓取 URL 最終失敗: {url}, 錯誤: {e}")
            return None

    def get_content(self, url: str) -> Optional[str]:
        """
        獲取 URL 的文本內容。

        Args:
            url (str): 目標 URL。

        Returns:
            Optional[str]: 成功時返回頁面文本內容，失敗時返回 None。
        """
        response = self.fetch_url(url)
        if response:
            response.encoding = response.apparent_encoding or 'utf-8'
            return response.text
        return None

    def get_binary_content(self, url: str) -> Optional[bytes]:
        """
        獲取 URL 的二進位內容。

        Args:
            url (str): 目標 URL。

        Returns:
            Optional[bytes]: 成功時返回二進位內容，失敗時返回 None。
        """
        response = self.fetch_url(url)
        if response:
            return response.content
        return None

    def close_session(self):
        """
        關閉請求會話。
        """
        if self.session:
            self.session.close()
            logger.info("請求會話已關閉。")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_session()

