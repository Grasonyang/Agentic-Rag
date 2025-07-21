#!/usr/bin/env python3
"""
make-database-setup.py
資料庫建置腳本 - RAG 流程第一步
設置和初始化 Supabase 資料庫
"""

import sys
import os
from pathlib import Path

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.client import SupabaseClient
from database.operations import DatabaseOperations
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def setup_database():
    """設置並驗證資料庫連線"""
    print("🗄️ RAG 步驟 1: 資料庫建置")
    print("=" * 50)
    
    try:
        # 測試連線
        print("📡 測試 Supabase 連線...")
        client = SupabaseClient()
        
        if not client.test_connection():
            print("❌ 資料庫連線失敗")
            print("\n📋 請確認:")
            print("1. Supabase 服務正在運行 (localhost:8000)")
            print("2. .env 檔案中的 SUPABASE_URL 和 SUPABASE_KEY 正確")
            return False
            
        print("✅ 資料庫連線成功")
        
        # 檢查資料庫狀態
        print("\n📊 檢查資料庫狀態...")
        db_ops = DatabaseOperations(client.get_client())
        stats = db_ops.get_statistics()
        
        print(f"📈 資料統計:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
            
        print("\n✅ 資料庫建置完成!")
        print("🎯 下一步: 執行 'make crawl' 開始爬取資料")
        return True
        
    except Exception as e:
        print(f"❌ 資料庫建置失敗: {e}")
        return False

def clear_database():
    """清空資料庫"""
    print("🧹 清空資料庫...")
    try:
        # 執行清理腳本
        import subprocess
        script_path = Path(__file__).parent / "make-database-clean.py"
        result = subprocess.run([sys.executable, str(script_path), "--clear-data"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 資料庫已清空")
        else:
            print(f"❌ 清空失敗: {result.stderr}")
    except Exception as e:
        print(f"❌ 清空失敗: {e}")

def main():
    """主函數"""
    import argparse
    parser = argparse.ArgumentParser(description="資料庫建置工具")
    parser.add_argument("--clear", action="store_true", help="清空資料庫")
    args = parser.parse_args()
    
    if args.clear:
        clear_database()
    else:
        setup_database()

if __name__ == "__main__":
    main()
