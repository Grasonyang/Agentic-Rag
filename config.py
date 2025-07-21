"""
配置管理模組
統一管理整個專案的配置參數
"""

import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Config:
    """配置類別，管理所有應用程式設定"""
    
    # Supabase 配置
    SUPABASE_URL = os.getenv("SUPABASE_URL", "http://host.docker.internal:8000")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    
    # 嵌入模型配置
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    
    # 分塊配置
    CHUNK_WINDOW_SIZE = int(os.getenv("CHUNK_WINDOW_SIZE", "100"))
    CHUNK_STEP_SIZE = int(os.getenv("CHUNK_STEP_SIZE", "50"))
    
    # 網頁爬蟲配置
    CRAWLER_HEADLESS = os.getenv("CRAWLER_HEADLESS", "true").lower() == "true"
    CRAWLER_VERBOSE = os.getenv("CRAWLER_VERBOSE", "false").lower() == "true"
    CRAWLER_DELAY = float(os.getenv("CRAWLER_DELAY", "2.5"))
    CRAWLER_TIMEOUT = int(os.getenv("CRAWLER_TIMEOUT", "60000"))
    CRAWLER_MAX_CONCURRENT = int(os.getenv("CRAWLER_MAX_CONCURRENT", "5"))
    
    # 目標網址配置
    TARGET_URLS = os.getenv("TARGET_URLS", "").split(",") if os.getenv("TARGET_URLS") else []
    SITEMAP_URLS = os.getenv("SITEMAP_URLS", "").split(",") if os.getenv("SITEMAP_URLS") else []
    ROOT_DOMAINS = os.getenv("ROOT_DOMAINS", "").split(",") if os.getenv("ROOT_DOMAINS") else []
    
    # 內容處理配置
    PREFERRED_CONTENT_FORMAT = os.getenv("PREFERRED_CONTENT_FORMAT", "markdown")
    PRESERVE_HTML_STRUCTURE = os.getenv("PRESERVE_HTML_STRUCTURE", "false").lower() == "true"
    CONVERT_TO_MARKDOWN = os.getenv("CONVERT_TO_MARKDOWN", "true").lower() == "true"
    CLEAN_WHITESPACE = os.getenv("CLEAN_WHITESPACE", "true").lower() == "true"
    
    # 速率限制配置
    RATE_LIMIT_BASE_DELAY_MIN = float(os.getenv("RATE_LIMIT_BASE_DELAY_MIN", "1.0"))
    RATE_LIMIT_BASE_DELAY_MAX = float(os.getenv("RATE_LIMIT_BASE_DELAY_MAX", "2.0"))
    RATE_LIMIT_MAX_DELAY = float(os.getenv("RATE_LIMIT_MAX_DELAY", "30.0"))
    RATE_LIMIT_MAX_RETRIES = int(os.getenv("RATE_LIMIT_MAX_RETRIES", "3"))
    
    # 瀏覽器配置
    BROWSER_VIEWPORT_WIDTH = int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1920"))
    BROWSER_VIEWPORT_HEIGHT = int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "1080"))
    BROWSER_USER_DATA_DIR = os.getenv("BROWSER_USER_DATA_DIR", "./user_data")
    
    # 輸出配置
    RESULTS_DIR = os.getenv("RESULTS_DIR", "ex_result")
    MAX_URLS_TO_PROCESS = int(os.getenv("MAX_URLS_TO_PROCESS", "10"))
    
    # Spider 框架配置
    SPIDER_DEFAULT_CHUNKER = os.getenv("SPIDER_DEFAULT_CHUNKER", "sliding_window")
    SPIDER_MAX_RETRIES = int(os.getenv("SPIDER_MAX_RETRIES", "3"))
    SPIDER_ENABLE_CACHING = os.getenv("SPIDER_ENABLE_CACHING", "true").lower() == "true"
    BROWSER_USER_DATA_DIR = os.getenv("BROWSER_USER_DATA_DIR", "./user_data")
    
    # 輸出配置
    RESULTS_DIR = os.getenv("RESULTS_DIR", "ex_result")
    MAX_URLS_TO_PROCESS = int(os.getenv("MAX_URLS_TO_PROCESS", 10))
    
    # Spider 框架配置
    SPIDER_DEFAULT_CHUNKER = os.getenv("SPIDER_DEFAULT_CHUNKER", "sliding_window")
    SPIDER_MAX_RETRIES = int(os.getenv("SPIDER_MAX_RETRIES", 3))
    SPIDER_ENABLE_CACHING = os.getenv("SPIDER_ENABLE_CACHING", "true").lower() == "true"
    
    # 資料庫清理配置
    DB_CLEANUP_DAYS = int(os.getenv("DB_CLEANUP_DAYS", 30))
    DB_AUTO_CLEANUP = os.getenv("DB_AUTO_CLEANUP", "false").lower() == "true"
    
    @classmethod
    def validate_config(cls) -> bool:
        """
        驗證配置是否有效
        
        Returns:
            bool: 配置有效返回 True，否則返回 False
        """
        required_configs = [
            ("SUPABASE_URL", cls.SUPABASE_URL),
            ("SUPABASE_KEY", cls.SUPABASE_KEY),
            ("EMBEDDING_MODEL", cls.EMBEDDING_MODEL),
        ]
        
        for name, value in required_configs:
            if not value:
                logger.error(f"必要配置缺失: {name}")
                return False
                
        logger.info("配置驗證通過")
        return True
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """
        獲取所有配置作為字典
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        return {
            attr: getattr(cls, attr)
            for attr in dir(cls)
            if not attr.startswith('_') and not callable(getattr(cls, attr))
        }
    
    @classmethod
    def print_config(cls):
        """列印當前配置（隱藏敏感信息）"""
        config_dict = cls.get_config_dict()
        
        logger.info("=== 當前配置 ===")
        for key, value in config_dict.items():
            # 隱藏敏感信息
            if "KEY" in key or "PASSWORD" in key:
                display_value = "*" * 8 if value else "未設定"
            else:
                display_value = value
            logger.info(f"{key}: {display_value}")

if __name__ == "__main__":
    Config.print_config()
    Config.validate_config()
