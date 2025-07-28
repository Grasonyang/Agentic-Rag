#!/usr/bin/env python3
"""
test_db_check.py - 測試資料庫檢查腳本

這個腳本用於測試 make-db-check.py 的功能
"""

import sys
import asyncio
import importlib.util
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent.parent))

# 動態導入 make-db-check.py 模組
make_db_check_path = Path(__file__).parent / "make-db-check.py"
spec = importlib.util.spec_from_file_location("make_db_check", make_db_check_path)
make_db_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_db_check)


async def test_db_check():
    """測試資料庫檢查功能"""
    print("🧪 開始測試資料庫檢查功能")
    
    checker = make_db_check.DatabaseHealthChecker()
    db_form = await checker.run_health_check()
    
    if db_form:
        print("\n✅ 測試成功！資料庫檢查回傳了表單數據")
        print(f"📊 資料庫狀態: {db_form['database_info']['status']}")
        print(f"📋 表格數量: {db_form['summary']['existing_tables']}/{db_form['summary']['total_tables']}")
        print(f"🗂️ 總記錄數: {db_form['summary']['total_records']:,}")
        return True
    else:
        print("\n❌ 測試失敗！資料庫檢查沒有回傳表單數據")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_db_check())
    sys.exit(0 if success else 1)
