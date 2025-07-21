#!/usr/bin/env python3
"""
Supabase 專用資料庫清理和初始化腳本
由於 Supabase 的限制，我們無法直接刪除表格，但可以清空資料
"""

import sys
from database.manage import DatabaseManager
from database.client import SupabaseClient

def clear_all_data():
    """清空所有表格的資料"""
    try:
        print("🧹 開始清空所有表格資料...")
        
        client = SupabaseClient()
        if not client.test_connection():
            print("❌ 無法連接到 Supabase")
            return False
        
        supabase = client.get_client()
        tables = ['search_logs', 'article_chunks', 'articles']  # 按依賴順序
        
        for table in tables:
            try:
                # 刪除表格中的所有資料
                response = supabase.table(table).delete().neq('id', 0).execute()
                if hasattr(response, 'data') and response.data:
                    print(f"  ✅ 已清空表格 {table}，刪除了 {len(response.data)} 條記錄")
                else:
                    print(f"  📄 表格 {table} 已經是空的")
            except Exception as e:
                print(f"  ⚠️ 清空表格 {table} 時出錯: {e}")
        
        print("✅ 資料清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 清理失敗: {e}")
        return False

def show_schema_setup_guide():
    """顯示 schema 設置指南"""
    print("\n" + "="*60)
    print("📋 Supabase Schema 設置指南")
    print("="*60)
    print("由於 Supabase 的安全限制，表格結構需要手動設置：")
    print("\n1. 登入您的 Supabase Dashboard")
    print("2. 進入 SQL Editor")
    print("3. 複製並執行 database/schema.sql 的內容")
    print("\n或者，如果您有直接的資料庫訪問權限：")
    print("psql -h <your-supabase-host> -p 5432 -U postgres -d postgres")
    print("\\i database/schema.sql")
    print("="*60)

def main():
    """主函數"""
    if len(sys.argv) > 1 and sys.argv[1] == '--clear-data':
        return 0 if clear_all_data() else 1
    
    try:
        manager = DatabaseManager()
        
        # 檢查當前狀態
        print("📊 當前資料庫狀態:")
        status = manager.get_database_status()
        
        if status.get('error'):
            print(f"❌ 錯誤: {status['error']}")
            return 1
        
        print(f"  Supabase 連線: {'✅' if status['supabase_connected'] else '❌'}")
        print(f"  直接連線: {'✅' if status['direct_connection'] else '❌'}")
        print(f"  表格數量: {status['tables_count']}")
        
        if status['tables']:
            print(f"  表格列表: {', '.join(status['tables'])}")
        
        # 如果沒有表格，顯示設置指南
        if status['tables_count'] == 0:
            show_schema_setup_guide()
        
        return 0
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
