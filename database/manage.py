"""
資料庫管理模組
提供資料庫初始化、重置和維護功能
"""

import os
import logging
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
from client import SupabaseClient

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
        
    # def get_direct_connection(self) -> Optional[psycopg2.extensions.connection]:
    #     """
    #     獲取直接的 PostgreSQL 連線
        
    #     Returns:
    #         psycopg2.connection: PostgreSQL 連線物件
    #     """
    #     try:
    #         conn = psycopg2.connect(
    #             host=self.db_host,
    #             port=self.db_port,
    #             database=self.db_name,
    #             user=self.db_user,
    #             password=self.db_password
    #         )
    #         logger.info(f"成功連接到 PostgreSQL: {self.db_host}:{self.db_port}")
    #         return conn
    #     except Exception as e:
    #         logger.error(f"PostgreSQL 連線失敗: {e}")
    #         return None
    
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
            # 使用 Supabase RPC 函數或手動清除
            return self._drop_tables_supabase()
                
        except Exception as e:
            logger.error(f"刪除表格失敗: {e}")
            print(f"❌ 刪除表格失敗: {e}")
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
            
            # 嘗試獲取表格統計信息
            table_stats = {}
            if supabase_connected:
                try:
                    from .operations import DatabaseOperations
                    client = self.supabase_client.get_client()
                    if client:
                        ops = DatabaseOperations(client)
                        table_stats = ops.get_table_row_counts()
                except Exception as e:
                    logger.warning(f"無法獲取表格統計信息: {e}")
            
            return {
                "tables_count": len(tables),
                "tables": tables,
                "table_statistics": table_stats,
                "supabase_connected": supabase_connected,
                "direct_connection": False  # 暫時禁用直接連接檢測
            }
            
        except Exception as e:
            logger.error(f"獲取資料庫狀態失敗: {e}")
            return {"error": str(e)}
    
    def clear_database_data(self, table_name: str = None) -> bool:
        """
        清除資料庫數據
        
        Args:
            table_name: 可選，指定要清除的表格名稱。如果為 None，則清除所有表格
            
        Returns:
            bool: 清除成功返回 True，否則返回 False
        """
        try:
            from .operations import DatabaseOperations
            
            client = self.supabase_client.get_client()
            if not client:
                print("❌ 無法連接到資料庫")
                return False
            
            ops = DatabaseOperations(client)
            
            if table_name:
                print(f"🧹 清除表格數據: {table_name}")
                return ops.clear_table_data(table_name)
            else:
                print("🧹 清除所有表格數據...")
                return ops.clear_all_data()
                
        except Exception as e:
            logger.error(f"清除資料庫數據失敗: {e}")
            print(f"❌ 清除資料庫數據失敗: {e}")
            return False
    
    def show_table_statistics(self):
        """顯示表格統計信息"""
        try:
            from .operations import DatabaseOperations
            
            client = self.supabase_client.get_client()
            if not client:
                print("❌ 無法連接到資料庫")
                return
            
            ops = DatabaseOperations(client)
            stats = ops.get_table_row_counts()
            
            print("📊 Database Table Statistics:")
            print("-" * 40)
            
            total_rows = 0
            for table_name, count in stats.items():
                if count >= 0:
                    print(f"  {table_name:<20}: {count:>8} rows")
                    total_rows += count
                else:
                    print(f"  {table_name:<20}: {'ERROR':>8}")
            
            print("-" * 40)
            print(f"  {'Total':<20}: {total_rows:>8} rows")
            
        except Exception as e:
            logger.error(f"顯示表格統計信息失敗: {e}")
            print(f"❌ 無法獲取表格統計信息: {e}")

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

def clear_all_data():
    """清除所有數據的便利函數"""
    try:
        from .operations import DatabaseOperations
        
        manager = DatabaseManager()
        client = manager.supabase_client.get_client()
        
        if not client:
            print("❌ 無法連接到資料庫")
            return False
        
        ops = DatabaseOperations(client)
        return ops.clear_all_data()
        
    except Exception as e:
        logger.error(f"清除所有數據失敗: {e}")
        return False

def clear_table_data(table_name: str):
    """清除指定表格數據的便利函數"""
    try:
        from .operations import DatabaseOperations
        
        manager = DatabaseManager()
        client = manager.supabase_client.get_client()
        
        if not client:
            print("❌ 無法連接到資料庫")
            return False
        
        ops = DatabaseOperations(client)
        return ops.clear_table_data(table_name)
        
    except Exception as e:
        logger.error(f"清除表格 {table_name} 失敗: {e}")
        return False

def get_table_statistics():
    """獲取表格統計信息的便利函數"""
    try:
        from .operations import DatabaseOperations
        
        manager = DatabaseManager()
        client = manager.supabase_client.get_client()
        
        if not client:
            print("❌ 無法連接到資料庫")
            return {}
        
        ops = DatabaseOperations(client)
        return ops.get_table_row_counts()
        
    except Exception as e:
        logger.error(f"獲取表格統計信息失敗: {e}")
        return {}

if __name__ == "__main__":
    import sys
    
    # 測試資料庫管理功能
    manager = DatabaseManager()
    
    # 檢查命令行參數
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "status":
            print("📊 資料庫狀態:")
            status = manager.get_database_status()
            for key, value in status.items():
                if key != "table_statistics":
                    print(f"  {key}: {value}")
            
            # 顯示表格統計
            if "table_statistics" in status and status["table_statistics"]:
                print("\n📊 表格統計:")
                for table, count in status["table_statistics"].items():
                    print(f"  {table}: {count} rows")
                    
        elif command == "clear":
            table_name = sys.argv[2] if len(sys.argv) > 2 else None
            if manager.clear_database_data(table_name):
                print("✅ 清除操作完成")
            else:
                print("❌ 清除操作失敗")
                
        elif command == "stats":
            manager.show_table_statistics()
            
        elif command == "reset":
            if manager.reset_database():
                print("✅ 資料庫重置完成")
            else:
                print("❌ 資料庫重置失敗")
                
        elif command == "init":
            if manager.initialize_database():
                print("✅ 資料庫初始化完成")
            else:
                print("❌ 資料庫初始化失敗")
                
        else:
            print("❌ 未知命令")
            print("可用命令: status, clear [table_name], stats, reset, init")
    else:
        print("📊 資料庫狀態:")
        status = manager.get_database_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        print("\n💡 使用方法:")
        print("  python manage.py status     - 顯示資料庫狀態")
        print("  python manage.py clear      - 清除所有數據")
        print("  python manage.py clear <table> - 清除指定表格")
        print("  python manage.py stats      - 顯示表格統計")
        print("  python manage.py reset      - 重置資料庫")
        print("  python manage.py init       - 初始化資料庫")
