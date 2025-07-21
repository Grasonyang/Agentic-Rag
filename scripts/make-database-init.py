#!/usr/bin/env python3
"""
資料庫初始化腳本
用於創建必要的資料庫表格和索引
"""

import logging
import sys
import os
from pathlib import Path

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def read_schema_file() -> str:
    """讀取 SQL schema 檔案"""
    schema_path = Path(__file__).parent / "database" / "schema.sql"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema 檔案不存在: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        return f.read()

def init_database():
    """初始化資料庫"""
    try:
        print("🚀 開始初始化資料庫...")
        
        # 使用新的資料庫管理器
        from database.manage import DatabaseManager
        manager = DatabaseManager()
        
        print(f"📊 連接到資料庫...")
        
        # 測試 Supabase 連線
        if manager.supabase_client.test_connection():
            print("✅ Supabase 連線成功")
        else:
            print("⚠️ Supabase 連線失敗，但仍會嘗試初始化")
        
        # 初始化資料庫
        if manager.initialize_database():
            print("✅ 資料庫初始化成功")
            
            # 顯示資料庫狀態
            status = manager.get_database_status()
            print(f"📊 創建了 {status.get('tables_count', 0)} 個表格")
            if status.get('tables'):
                print(f"� 表格列表: {', '.join(status['tables'])}")
                
            return True
        else:
            print("❌ 資料庫初始化失敗")
            return False
        
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        logger.exception("詳細錯誤信息")
        return False
        print(f"❌ 初始化失敗: {e}")
        logger.exception("詳細錯誤信息")
        return False

def show_manual_setup_instructions():
    """顯示手動設置說明"""
    print("\n" + "="*60)
    print("📋 手動資料庫設置說明")
    print("="*60)
    print("由於 Supabase 客戶端限制，請手動執行以下步驟：")
    print("\n1. 方法一 - 使用 Supabase Dashboard:")
    print("   - 登入 Supabase Dashboard")
    print("   - 進入 SQL Editor")
    print("   - 複製 database/schema.sql 內容並執行")
    
    print("\n2. 方法二 - 使用 psql:")
    print("   - psql -h localhost -p 5432 -U postgres -d postgres")
    print("   - \\i database/schema.sql")
    
    print("\n3. 方法三 - 使用 Docker 容器:")
    print("   - docker exec -i supabase-db psql -U postgres < database/schema.sql")
    
    print(f"\n📄 Schema 檔案位置: {Path(__file__).parent / 'database' / 'schema.sql'}")
    print("="*60)

def main():
    """主函數"""
    try:
        success = init_database()
        
        if success:
            print("\n🎉 資料庫初始化完成！")
        else:
            print("\n❌ 資料庫初始化失敗")
            show_manual_setup_instructions()
            return 1
            
        return 0
        
    except KeyboardInterrupt:
        print("\n⏹️ 使用者中斷操作")
        return 1
    except Exception as e:
        print(f"\n💥 程式異常: {e}")
        logger.exception("程式異常")
        return 1

if __name__ == "__main__":
    sys.exit(main())
