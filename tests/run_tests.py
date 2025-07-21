#!/usr/bin/env python3
"""
測試運行器 - 統一運行所有測試
"""

import sys
import asyncio
import argparse
from pathlib import Path

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests import print_test_header

def print_usage():
    """顯示使用說明"""
    print("""
🧪 Agentic RAG Framework 測試套件
================================

可用的測試類型:
  all           - 運行所有測試
  unit          - 單元測試 (爬蟲功能)
  database      - 資料庫測試
  integration   - 整合測試
  quick         - 快速測試 (基本功能)

使用方法:
  python run_tests.py [測試類型]

範例:
  python run_tests.py all           # 運行所有測試
  python run_tests.py unit          # 只運行單元測試
  python run_tests.py database      # 只運行資料庫測試
  python run_tests.py quick         # 快速測試

注意事項:
  - 確保 Supabase 容器正在運行
  - 確保網絡連接正常
  - 某些測試需要較長時間
""")

async def run_unit_tests():
    """運行單元測試"""
    print_test_header("運行單元測試")
    try:
        from tests.unit.test_crawler import CrawlerTestSuite
        suite = CrawlerTestSuite()
        return await suite.run_all_tests()
    except Exception as e:
        print(f"❌ 單元測試運行失敗: {e}")
        return False

def run_database_tests():
    """運行資料庫測試"""
    print_test_header("運行資料庫測試")
    try:
        from tests.database.test_database_operations import DatabaseTestSuite
        suite = DatabaseTestSuite()
        return suite.run_all_tests()
    except Exception as e:
        print(f"❌ 資料庫測試運行失敗: {e}")
        return False

async def run_integration_tests():
    """運行整合測試"""
    print_test_header("運行整合測試")
    try:
        from tests.integration.test_full_system import IntegrationTestSuite
        suite = IntegrationTestSuite()
        return await suite.run_all_tests()
    except Exception as e:
        print(f"❌ 整合測試運行失敗: {e}")
        return False

async def run_quick_tests():
    """運行快速測試"""
    print_test_header("運行快速測試")
    
    print("🚀 快速測試包含:")
    print("  1. 資料庫連接測試")
    print("  2. 單個 URL 爬取測試")
    print("  3. 基本儲存測試\n")
    
    # 1. 測試資料庫連接
    try:
        from database import SupabaseClient
        client = SupabaseClient()
        if client.connect():
            print("✅ 資料庫連接正常")
        else:
            print("❌ 資料庫連接失敗")
            return False
    except Exception as e:
        print(f"❌ 資料庫測試失敗: {e}")
        return False
    
    # 2. 測試基本爬蟲功能
    try:
        from spider.crawlers.simple_crawler import SimpleWebCrawler
        
        async with SimpleWebCrawler() as crawler:
            result = await crawler.crawl_url("https://httpbin.org/json")
            if result.success:
                print("✅ 爬蟲功能正常")
            else:
                print(f"❌ 爬蟲測試失敗: {result.error}")
                return False
    except Exception as e:
        print(f"❌ 爬蟲測試失敗: {e}")
        return False
    
    # 3. 測試基本儲存
    try:
        from database import DatabaseOperations, ArticleModel
        from datetime import datetime
        
        db_ops = DatabaseOperations(client)
        test_article = ArticleModel(
            url=f"https://quick-test-{datetime.now().strftime('%Y%m%d%H%M%S')}.example.com",
            title="快速測試文章",
            content="這是快速測試的內容",
            metadata={"test_type": "quick"}
        )
        
        if db_ops.create_article(test_article):
            print("✅ 資料庫儲存正常")
        else:
            print("❌ 資料庫儲存失敗")
            return False
    except Exception as e:
        print(f"❌ 儲存測試失敗: {e}")
        return False
    
    print("\n🎉 快速測試全部通過！")
    return True

async def run_all_tests():
    """運行所有測試"""
    print_test_header("運行完整測試套件")
    
    results = {
        "database": False,
        "unit": False,
        "integration": False
    }
    
    # 1. 資料庫測試
    print("\n📊 第 1 階段: 資料庫測試")
    results["database"] = run_database_tests()
    
    if not results["database"]:
        print("⚠️ 資料庫測試失敗，跳過其他測試")
        return False
    
    # 2. 單元測試
    print("\n🕷️ 第 2 階段: 爬蟲單元測試")
    results["unit"] = await run_unit_tests()
    
    # 3. 整合測試
    print("\n🔗 第 3 階段: 整合測試")
    results["integration"] = await run_integration_tests()
    
    # 總結
    passed = sum(results.values())
    total = len(results)
    
    print("\n" + "="*60)
    print("📋 完整測試報告")
    print("="*60)
    for test_type, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_type.upper()} 測試")
    
    print(f"\n📊 總結: {passed}/{total} 測試套件通過")
    
    if passed == total:
        print("🎉 所有測試套件通過！系統運行正常。")
        return True
    else:
        print("⚠️ 部分測試失敗，請檢查系統配置。")
        return False

async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='Agentic RAG Framework 測試套件')
    parser.add_argument('test_type', nargs='?', default='help',
                      choices=['all', 'unit', 'database', 'integration', 'quick', 'help'],
                      help='要運行的測試類型')
    
    args = parser.parse_args()
    
    if args.test_type == 'help':
        print_usage()
        return 0
    
    print("🧪 Agentic RAG Framework 測試系統")
    print("="*50)
    
    success = False
    
    try:
        if args.test_type == 'all':
            success = await run_all_tests()
        elif args.test_type == 'unit':
            success = await run_unit_tests()
        elif args.test_type == 'database':
            success = run_database_tests()
        elif args.test_type == 'integration':
            success = await run_integration_tests()
        elif args.test_type == 'quick':
            success = await run_quick_tests()
        
    except KeyboardInterrupt:
        print("\n⏹️ 用戶中斷測試")
        return 1
    except Exception as e:
        print(f"\n💥 測試運行異常: {e}")
        return 1
    
    if success:
        print(f"\n✅ {args.test_type.upper()} 測試完成！")
        return 0
    else:
        print(f"\n❌ {args.test_type.upper()} 測試失敗！")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
