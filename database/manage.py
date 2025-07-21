"""
資料庫管理模組
提供資料庫初始化、重置和維護功能
"""

import os
import logging
import psycopg2
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
from .client import SupabaseClient

# 載入環境變數
load_dotenv()

# 設置日誌
logger = logging.getLogger(__name__)

class DatabaseManager:
    """資料庫管理器"""
    
    def __init__(self):
        """初始化資料庫管理器"""
        # 從環境變數或默認值獲取資料庫連線參數
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("DB_NAME", "postgres")
        self.db_user = os.getenv("DB_USER", "postgres")
        self.db_password = os.getenv("DB_PASSWORD", "postgres")
        
        # Supabase 客戶端
        self.supabase_client = SupabaseClient()
        
    def get_direct_connection(self) -> Optional[psycopg2.extensions.connection]:
        """
        獲取直接的 PostgreSQL 連線
        
        Returns:
            psycopg2.connection: PostgreSQL 連線物件
        """
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            logger.info(f"成功連接到 PostgreSQL: {self.db_host}:{self.db_port}")
            return conn
        except Exception as e:
            logger.error(f"PostgreSQL 連線失敗: {e}")
            return None
    
    def read_schema_file(self) -> str:
        """讀取 SQL schema 檔案"""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema 檔案不存在: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def get_table_list(self) -> List[str]:
        """獲取資料庫中的表格列表"""
        try:
            # 優先嘗試直接連線
            conn = self.get_direct_connection()
            if conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT tablename 
                        FROM pg_tables 
                        WHERE schemaname = 'public'
                        AND tablename NOT LIKE 'pg_%'
                        AND tablename NOT LIKE 'sql_%'
                    """)
                    tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                return tables
            else:
                # 使用 Supabase 檢查已知表格
                return self._get_tables_supabase()
                
        except Exception as e:
            logger.error(f"獲取表格列表失敗: {e}")
            return self._get_tables_supabase()
    
    def _get_tables_supabase(self) -> List[str]:
        """使用 Supabase 檢查已知表格是否存在"""
        try:
            client = self.supabase_client.get_client()
            if not client:
                return []
            
            known_tables = ['articles', 'article_chunks', 'search_logs']
            existing_tables = []
            
            for table in known_tables:
                try:
                    # 嘗試查詢表格來檢查是否存在
                    response = client.table(table).select('id').limit(1).execute()
                    existing_tables.append(table)
                except Exception:
                    # 表格不存在或無法訪問
                    pass
            
            return existing_tables
            
        except Exception as e:
            logger.error(f"Supabase 表格檢查失敗: {e}")
            return []
    
    def drop_all_tables(self) -> bool:
        """
        刪除所有使用者定義的表格
        
        Returns:
            bool: 成功返回 True，否則返回 False
        """
        try:
            # 優先嘗試使用直接連線
            conn = self.get_direct_connection()
            if conn:
                return self._drop_tables_direct(conn)
            else:
                # 使用 Supabase RPC 函數
                return self._drop_tables_supabase()
                
        except Exception as e:
            logger.error(f"刪除表格失敗: {e}")
            print(f"❌ 刪除表格失敗: {e}")
            return False
    
    def _drop_tables_direct(self, conn) -> bool:
        """使用直接連線刪除表格"""
        try:
            with conn.cursor() as cursor:
                # 獲取所有使用者表格
                tables = self.get_table_list()
                
                if not tables:
                    print("📄 沒有找到需要刪除的表格")
                    return True
                
                print(f"🔥 準備刪除 {len(tables)} 個表格: {', '.join(tables)}")
                
                # 刪除每個表格
                for table in tables:
                    try:
                        cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
                        print(f"  ✅ 已刪除表格: {table}")
                    except Exception as e:
                        print(f"  ❌ 刪除表格 {table} 失敗: {e}")
                
                # 提交更改
                conn.commit()
            
            conn.close()
            print("🎯 所有表格已成功刪除")
            return True
            
        except Exception as e:
            logger.error(f"直接刪除表格失敗: {e}")
            return False
    
    def _drop_tables_supabase(self) -> bool:
        """使用 Supabase RPC 函數刪除表格"""
        try:
            client = self.supabase_client.get_client()
            if not client:
                print("❌ 無法獲取 Supabase 客戶端")
                return False
            
            # 嘗試使用 RPC 函數
            try:
                response = client.rpc('drop_all_user_tables').execute()
                print("✅ 使用 Supabase RPC 刪除所有表格")
                return True
            except Exception as e:
                logger.warning(f"RPC 函數不可用: {e}")
                
            # 手動刪除已知表格
            known_tables = ['articles', 'article_chunks', 'search_logs']
            success_count = 0
            
            for table in known_tables:
                try:
                    # 先檢查表格是否存在
                    response = client.table(table).select('id').limit(1).execute()
                    
                    # 如果表格存在，嘗試刪除其中的資料（這是我們能做的最接近刪除表格的操作）
                    # 注意：Supabase 客戶端無法直接刪除表格，只能清空資料
                    response = client.table(table).delete().neq('id', 0).execute()
                    print(f"  🗑️ 已清空表格資料: {table}")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ⚠️ 處理表格 {table} 失敗: {e}")
            
            if success_count > 0:
                print(f"✅ 成功處理 {success_count} 個表格")
                print("💡 注意：由於 Supabase 限制，只能清空表格資料，無法刪除表格結構")
                return True
            else:
                print("❌ 沒有成功處理任何表格")
                return False
                
        except Exception as e:
            logger.error(f"Supabase 刪除失敗: {e}")
            return False
    
    def create_tables(self) -> bool:
        """
        根據 schema.sql 創建表格
        
        Returns:
            bool: 成功返回 True，否則返回 False
        """
        try:
            # 讀取 schema
            schema_sql = self.read_schema_file()
            
            # 優先嘗試直接連線
            conn = self.get_direct_connection()
            if conn:
                with conn.cursor() as cursor:
                    # 執行 schema SQL
                    cursor.execute(schema_sql)
                    conn.commit()
                conn.close()
                print("✅ 表格創建成功（使用直接連線）")
                return True
            else:
                # 使用 Supabase（提示用戶手動執行）
                print("⚠️ 無法使用直接連線創建表格")
                print("💡 請手動在 Supabase Dashboard 中執行 database/schema.sql")
                print("   或使用 psql 連接到 Supabase 資料庫執行 schema")
                
                # 嘗試檢查表格是否已經存在
                tables = self.get_table_list()
                if tables:
                    print(f"✅ 發現現有表格: {', '.join(tables)}")
                    return True
                else:
                    print("❌ 沒有發現表格，請手動執行 schema.sql")
                    return False
                
        except Exception as e:
            logger.error(f"創建表格失敗: {e}")
            print(f"❌ 創建表格失敗: {e}")
            return False
    
    def reset_database(self) -> bool:
        """
        重置資料庫：刪除所有表格並重新創建
        
        Returns:
            bool: 成功返回 True，否則返回 False
        """
        print("🚀 開始重置資料庫...")
        
        # 1. 刪除所有表格
        if not self.drop_all_tables():
            return False
        
        # 2. 重新創建表格
        if not self.create_tables():
            return False
        
        # 3. 驗證表格
        tables = self.get_table_list()
        if tables:
            print(f"✅ 資料庫重置完成！創建了 {len(tables)} 個表格: {', '.join(tables)}")
            return True
        else:
            print("❌ 資料庫重置後沒有找到表格")
            return False
    
    def initialize_database(self) -> bool:
        """
        初始化資料庫（僅在表格不存在時創建）
        
        Returns:
            bool: 成功返回 True，否則返回 False
        """
        try:
            print("🔍 檢查現有表格...")
            tables = self.get_table_list()
            
            if tables:
                print(f"📊 發現現有表格: {', '.join(tables)}")
                return True
            
            print("📄 沒有找到表格，開始初始化...")
            return self.create_tables()
            
        except Exception as e:
            logger.error(f"初始化資料庫失敗: {e}")
            return False
    
    def get_database_status(self) -> dict:
        """
        獲取資料庫狀態
        
        Returns:
            dict: 資料庫狀態信息
        """
        try:
            tables = self.get_table_list()
            supabase_connected = self.supabase_client.test_connection()
            
            return {
                "tables_count": len(tables),
                "tables": tables,
                "supabase_connected": supabase_connected,
                "direct_connection": self.get_direct_connection() is not None
            }
            
        except Exception as e:
            logger.error(f"獲取資料庫狀態失敗: {e}")
            return {"error": str(e)}

# 便利函數
def reset_database():
    """重置資料庫的便利函數"""
    manager = DatabaseManager()
    return manager.reset_database()

def initialize_database():
    """初始化資料庫的便利函數"""
    manager = DatabaseManager()
    return manager.initialize_database()

def get_database_status():
    """獲取資料庫狀態的便利函數"""
    manager = DatabaseManager()
    return manager.get_database_status()

if __name__ == "__main__":
    # 測試資料庫管理功能
    manager = DatabaseManager()
    
    print("📊 資料庫狀態:")
    status = manager.get_database_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
