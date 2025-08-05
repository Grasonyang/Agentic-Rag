"""
配置管理模組
提供統一的配置管理，支援環境變數和配置文件
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路徑（JSON格式）
        """
        self.logger = logging.getLogger(__name__)
        self.config_data = {}
        
        # 載入配置文件（如果提供）
        if config_file:
            self.load_config_file(config_file)
    
    def load_config_file(self, config_file: str):
        """載入JSON配置文件"""
        try:
            config_path = Path(config_file)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                self.logger.info(f"成功載入配置文件: {config_file}")
            else:
                self.logger.warning(f"配置文件不存在: {config_file}")
        except Exception as e:
            self.logger.error(f"載入配置文件失敗: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        獲取配置值
        優先順序：環境變數 > 配置文件 > 默認值
        
        Args:
            key: 配置鍵
            default: 默認值
            
        Returns:
            配置值
        """
        # 1. 檢查環境變數
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value
        
        # 2. 檢查配置文件
        if key in self.config_data:
            return self.config_data[key]
        
        # 3. 返回默認值
        return default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """獲取整數配置值"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """獲取浮點數配置值"""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """獲取布爾配置值"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    def get_database_config(self) -> Dict[str, Any]:
        """獲取資料庫配置"""
        return {
            'host': self.get('SUPABASE_HOST', 'localhost'),
            'port': self.get_int('SUPABASE_PORT', 5432),
            'database': self.get('SUPABASE_DATABASE', 'postgres'),
            'user': self.get('SUPABASE_USER', 'postgres'),
            'password': self.get('SUPABASE_PASSWORD', ''),
            'url': self.get('SUPABASE_URL', ''),
            'key': self.get('SUPABASE_KEY', ''),
            'service_key': self.get('SERVICE_ROLE_KEY', ''),
            'anon_key': self.get('ANON_KEY', '')
        }
    
    def get_spider_config(self) -> Dict[str, Any]:
        """獲取爬蟲配置"""
        return {
            'max_concurrent': self.get_int('SPIDER_MAX_CONCURRENT', 5),
            'delay': self.get_float('SPIDER_DELAY', 1.0),
            'max_retries': self.get_int('SPIDER_MAX_RETRIES', 3),
            'timeout': self.get_float('SPIDER_TIMEOUT', 30.0),
            'user_agent': self.get('SPIDER_USER_AGENT', 'RAG-Spider/2.0'),
            'requests_per_second': self.get_float('SPIDER_REQUESTS_PER_SECOND', 2.0)
        }
    
    def set(self, key: str, value: Any):
        """設置配置值（僅在記憶體中）"""
        self.config_data[key] = value
    
    def save_config_file(self, config_file: str):
        """保存配置到文件"""
        try:
            config_path = Path(config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"配置已保存到: {config_file}")
        except Exception as e:
            self.logger.error(f"保存配置文件失敗: {e}")


# 全局配置管理器實例
_global_config: Optional[ConfigManager] = None

def get_config(config_file: Optional[str] = None) -> ConfigManager:
    """
    獲取全局配置管理器實例
    
    Args:
        config_file: 配置文件路徑
        
    Returns:
        ConfigManager: 配置管理器實例
    """
    global _global_config
    
    if _global_config is None:
        _global_config = ConfigManager(config_file)
    
    return _global_config

def init_config(config_file: Optional[str] = None):
    """
    初始化配置管理器
    
    Args:
        config_file: 配置文件路徑
    """
    global _global_config
    _global_config = ConfigManager(config_file)


# 便捷函數
def get_database_config() -> Dict[str, Any]:
    """獲取資料庫配置"""
    return get_config().get_database_config()

def get_spider_config() -> Dict[str, Any]:
    """獲取爬蟲配置"""
    return get_config().get_spider_config()
