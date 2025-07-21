"""
Supabase 客戶端管理
負責連線管理和基本配置
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# 載入環境變數
load_dotenv()

# 設置日誌
logger = logging.getLogger(__name__)

class SupabaseClient:
    """Supabase 客戶端管理器"""
    
    def __init__(self):
        """初始化 Supabase 客戶端"""
        self.url = os.getenv("SUPABASE_URL", "http://host.docker.internal:8000")
        self.key = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzUyOTQwODAwLCJleHAiOjE5MTA3MDcyMDB9.6kOE4rH2zJPRENgZCjcYMsCO277ZwOcXGovfwziAYkk")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NTI5NDA4MDAsImV4cCI6MTkxMDcwNzIwMH0.FKE6J7Mj-pUXDnIlZnTFE-mNbUQSluYG4s7sINtWWw0")
        self._client: Optional[Client] = None
        self._admin_client: Optional[Client] = None
        
    def connect(self) -> bool:
        """
        建立 Supabase 連線
        
        Returns:
            bool: 連線成功返回 True，否則返回 False
        """
        try:
            logger.info(f"正在連接到 Supabase: {self.url}")
            self._client = create_client(self.url, self.key)
            
            # 簡單的連線測試 - 只創建客戶端
            logger.info("✅ Supabase 客戶端創建成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ Supabase 連線失敗: {e}")
            self._client = None
            return False
    
    def get_client(self) -> Optional[Client]:
        """
        獲取 Supabase 客戶端實例
        
        Returns:
            Client: Supabase 客戶端，未連線時返回 None
        """
        if self._client is None:
            if not self.connect():
                return None
        return self._client
    
    def table(self, table_name: str):
        """
        獲取表格操作實例
        
        Args:
            table_name: 表格名稱
            
        Returns:
            表格操作實例
        """
        client = self.get_client()
        if client is None:
            raise Exception("Supabase 客戶端未連線")
        return client.table(table_name)
    
    def get_admin_client(self) -> Optional[Client]:
        """
        獲取具有管理員權限的 Supabase 客戶端實例
        
        Returns:
            Client: 管理員 Supabase 客戶端，未連線時返回 None
        """
        if self._admin_client is None:
            try:
                logger.info("正在創建管理員客戶端...")
                self._admin_client = create_client(self.url, self.service_key)
                logger.info("✅ 管理員客戶端創建成功")
            except Exception as e:
                logger.error(f"❌ 管理員客戶端創建失敗: {e}")
                return None
        return self._admin_client
    
    def test_connection(self) -> bool:
        """
        測試連線狀態
        
        Returns:
            bool: 連線正常返回 True，否則返回 False
        """
        try:
            if self._client is None:
                if not self.connect():
                    return False
            
            # 使用簡單的查詢來測試連線
            response = self._client.table('articles').select('id').limit(1).execute()
            logger.info("✅ Supabase 連線測試成功")
            return True
            
        except Exception as e:
            logger.error(f"連線測試失敗: {e}")
            return False
    
    def disconnect(self):
        """斷開連線"""
        if self._client:
            self._client = None
            logger.info("Supabase 連線已斷開")
    
    @property
    def is_connected(self) -> bool:
        """檢查是否已連線"""
        return self._client is not None
    
    def get_connection_info(self) -> dict:
        """
        獲取連線信息
        
        Returns:
            dict: 連線信息字典
        """
        return {
            "url": self.url,
            "connected": self.is_connected,
            "client_available": self._client is not None
        }
