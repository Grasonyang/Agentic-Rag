#!/usr/bin/env python3
"""
資料庫功能測試套件
測試 Supabase 連接、寫入、查詢等核心功能
"""

import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests import print_test_header, print_test_result, print_test_summary, TEST_CONFIG

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class DatabaseTestSuite:
    """資料庫測試套件"""
    
    def __init__(self):
        self.passed_tests = 0
        self.total_tests = 0
        self.client = None
        self.db_ops = None
    
    def setUp(self):
        """測試準備"""
        try:
            from database import SupabaseClient, DatabaseOperations, ArticleModel
            self.client = SupabaseClient()
            if self.client.connect():
                self.db_ops = DatabaseOperations(self.client)
                return True
            return False
        except Exception as e:
            logger.error(f"測試準備失敗: {e}")
            return False
    
    def test_connection(self):
        """測試資料庫連接"""
        self.total_tests += 1
        try:
            success = self.client.connect()
            print_test_result("資料庫連接", success)
            if success:
                self.passed_tests += 1
            return success
        except Exception as e:
            print_test_result("資料庫連接", False, str(e))
            return False
    
    def test_table_access(self):
        """測試表格訪問"""
        self.total_tests += 1
        try:
            # 測試每個表格
            tables = ['articles', 'article_chunks', 'search_logs']
            for table_name in tables:
                result = self.client.table(table_name).select('id').limit(1).execute()
            
            print_test_result("表格訪問", True, f"成功訪問 {len(tables)} 個表格")
            self.passed_tests += 1
            return True
        except Exception as e:
            print_test_result("表格訪問", False, str(e))
            return False
    
    def test_direct_insert(self):
        """測試直接插入資料"""
        self.total_tests += 1
        try:
            test_data = {
                "url": f"https://test-direct-{datetime.now().strftime('%Y%m%d%H%M%S')}.example.com",
                "title": "直接插入測試",
                "content": "這是直接插入測試的內容",
                "metadata": {"test_type": "direct_insert"}
            }
            
            response = self.client.table("articles").insert(test_data).execute()
            
            if response.data:
                article_id = response.data[0]['id']
                print_test_result("直接插入", True, f"成功插入文章 ID: {article_id}")
                self.passed_tests += 1
                return True
            else:
                print_test_result("直接插入", False, "插入後無資料返回")
                return False
                
        except Exception as e:
            print_test_result("直接插入", False, str(e))
            return False
    
    def test_database_operations(self):
        """測試 DatabaseOperations 類別"""
        self.total_tests += 1
        try:
            from database import ArticleModel
            
            # 創建測試文章
            article = ArticleModel(
                url=f"https://test-ops-{datetime.now().strftime('%Y%m%d%H%M%S')}.example.com",
                title="DatabaseOperations 測試",
                content="這是 DatabaseOperations 測試內容",
                metadata={"test_type": "database_operations"}
            )
            
            # 測試創建
            success = self.db_ops.create_article(article)
            
            if success:
                # 測試查詢
                retrieved = self.db_ops.get_article_by_url(article.url)
                if retrieved:
                    print_test_result("DatabaseOperations", True, f"成功創建並查詢文章: {retrieved.title}")
                    self.passed_tests += 1
                    return True
                else:
                    print_test_result("DatabaseOperations", False, "創建成功但查詢失敗")
                    return False
            else:
                print_test_result("DatabaseOperations", False, "文章創建失敗")
                return False
                
        except Exception as e:
            print_test_result("DatabaseOperations", False, str(e))
            return False
    
    def test_batch_operations(self):
        """測試批量操作"""
        self.total_tests += 1
        try:
            from database import ArticleModel
            
            # 創建多個測試文章
            articles = []
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            for i in range(3):
                article = ArticleModel(
                    url=f"https://test-batch-{timestamp}-{i}.example.com",
                    title=f"批量測試文章 {i+1}",
                    content=f"這是批量測試文章 {i+1} 的內容",
                    metadata={"test_type": "batch", "index": i}
                )
                articles.append(article)
            
            # 批量創建
            success_count = 0
            for article in articles:
                if self.db_ops.create_article(article):
                    success_count += 1
            
            if success_count == len(articles):
                print_test_result("批量操作", True, f"成功創建 {success_count} 篇文章")
                self.passed_tests += 1
                return True
            else:
                print_test_result("批量操作", False, f"僅創建 {success_count}/{len(articles)} 篇文章")
                return False
                
        except Exception as e:
            print_test_result("批量操作", False, str(e))
            return False
    
    def run_all_tests(self):
        """運行所有測試"""
        print_test_header("資料庫功能測試")
        
        # 準備測試環境
        if not self.setUp():
            print("❌ 無法準備測試環境")
            return False
        
        # 執行測試
        print("🔧 檢查配置...")
        print(f"   資料庫 URL: {self.client.url}")
        print("✅ 配置檢查通過\n")
        
        self.test_connection()
        self.test_table_access()
        self.test_direct_insert()
        self.test_database_operations()
        self.test_batch_operations()
        
        # 顯示結果
        print_test_summary(self.passed_tests, self.total_tests)
        
        return self.passed_tests == self.total_tests

def main():
    """主函數"""
    test_suite = DatabaseTestSuite()
    success = test_suite.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
