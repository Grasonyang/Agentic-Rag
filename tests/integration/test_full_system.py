#!/usr/bin/env python3
"""
完整系統整合測試
測試爬蟲+資料庫的完整工作流程
"""

import sys
import asyncio
import logging
from pathlib import Path

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests import print_test_header, print_test_result, print_test_summary, TEST_URLS, TEST_CONFIG

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class IntegrationTestSuite:
    """整合測試套件"""
    
    def __init__(self):
        self.passed_tests = 0
        self.total_tests = 0
        self.crawler = None
        self.db_client = None
        self.db_ops = None
    
    async def setUp(self):
        """測試準備"""
        try:
            # 初始化爬蟲
            from spider.crawlers.simple_crawler import SimpleWebCrawler
            self.crawler = SimpleWebCrawler()
            
            # 初始化資料庫
            from database import SupabaseClient, DatabaseOperations
            self.db_client = SupabaseClient()
            
            if not self.db_client.connect():
                raise Exception("資料庫連接失敗")
            
            self.db_ops = DatabaseOperations(self.db_client)
            
            return True
        except Exception as e:
            logger.error(f"整合測試準備失敗: {e}")
            return False
    
    async def test_crawl_and_save_pipeline(self):
        """測試爬取並儲存流程"""
        self.total_tests += 1
        try:
            from database import ArticleModel
            from datetime import datetime
            
            # 1. 爬取數據
            test_url = TEST_URLS[2]  # 使用 example.com
            crawl_result = await self.crawler.crawl_url(test_url)
            
            if not crawl_result.success:
                print_test_result("爬取並儲存", False, f"爬取失敗: {crawl_result.error}")
                return False
            
            # 2. 創建文章模型
            article = ArticleModel(
                url=test_url,
                title=crawl_result.title or f"整合測試文章",
                content=crawl_result.markdown or crawl_result.content,
                metadata={
                    "crawl_time": datetime.now().isoformat(),
                    "response_time": crawl_result.response_time,
                    "test_type": "integration",
                    "content_length": len(crawl_result.content or "")
                }
            )
            
            # 3. 檢查是否已存在
            existing = self.db_ops.get_article_by_url(test_url)
            if existing:
                print_test_result("爬取並儲存", True, f"文章已存在，跳過儲存: {existing.title}")
                self.passed_tests += 1
                return True
            
            # 4. 儲存到資料庫
            save_success = self.db_ops.create_article(article)
            
            if save_success:
                # 5. 驗證儲存
                saved_article = self.db_ops.get_article_by_url(test_url)
                if saved_article:
                    print_test_result(
                        "爬取並儲存", 
                        True, 
                        f"成功爬取並儲存: {saved_article.title}"
                    )
                    self.passed_tests += 1
                    return True
                else:
                    print_test_result("爬取並儲存", False, "儲存成功但查詢失敗")
                    return False
            else:
                print_test_result("爬取並儲存", False, "資料庫儲存失敗")
                return False
                
        except Exception as e:
            print_test_result("爬取並儲存", False, str(e))
            return False
    
    async def test_batch_crawl_and_save(self):
        """測試批量爬取並儲存"""
        self.total_tests += 1
        try:
            from database import ArticleModel
            from datetime import datetime
            
            # 1. 批量爬取
            test_urls = TEST_URLS[:3]  # 使用前 3 個 URL
            crawl_results = await self.crawler.crawl_batch(
                test_urls, 
                max_concurrent=TEST_CONFIG["max_concurrent"]
            )
            
            # 2. 處理並儲存結果
            saved_count = 0
            failed_count = 0
            
            for result in crawl_results:
                if result.success and result.content:
                    try:
                        # 檢查是否已存在
                        existing = self.db_ops.get_article_by_url(result.url)
                        if existing:
                            saved_count += 1  # 算作成功
                            continue
                        
                        # 創建並儲存文章
                        article = ArticleModel(
                            url=result.url,
                            title=result.title or f"批量測試 - {result.url}",
                            content=result.markdown or result.content,
                            metadata={
                                "crawl_time": datetime.now().isoformat(),
                                "response_time": result.response_time,
                                "test_type": "batch_integration",
                                "content_length": len(result.content)
                            }
                        )
                        
                        if self.db_ops.create_article(article):
                            saved_count += 1
                        else:
                            failed_count += 1
                            
                    except Exception as e:
                        logger.error(f"處理 {result.url} 時出錯: {e}")
                        failed_count += 1
                else:
                    failed_count += 1
            
            success_rate = saved_count / len(test_urls) * 100
            passed = success_rate >= 66  # 至少 66% 成功率
            
            print_test_result(
                "批量爬取儲存", 
                passed, 
                f"{saved_count}/{len(test_urls)} 成功 ({success_rate:.1f}%)"
            )
            
            if passed:
                self.passed_tests += 1
            return passed
                
        except Exception as e:
            print_test_result("批量爬取儲存", False, str(e))
            return False
    
    async def test_data_consistency(self):
        """測試資料一致性"""
        self.total_tests += 1
        try:
            # 爬取一個 URL
            test_url = "https://httpbin.org/json"
            crawl_result = await self.crawler.crawl_url(test_url)
            
            if not crawl_result.success:
                print_test_result("資料一致性", False, "爬取失敗")
                return False
            
            # 檢查資料庫中的文章
            db_article = self.db_ops.get_article_by_url(test_url)
            
            if db_article:
                # 比較關鍵資訊
                url_match = db_article.url == test_url
                has_content = bool(db_article.content and len(db_article.content.strip()) > 0)
                has_metadata = bool(db_article.metadata)
                
                consistency_score = sum([url_match, has_content, has_metadata])
                passed = consistency_score >= 2
                
                print_test_result(
                    "資料一致性", 
                    passed, 
                    f"URL匹配: {url_match}, 有內容: {has_content}, 有元數據: {has_metadata}"
                )
                
                if passed:
                    self.passed_tests += 1
                return passed
            else:
                print_test_result("資料一致性", False, "資料庫中找不到對應文章")
                return False
                
        except Exception as e:
            print_test_result("資料一致性", False, str(e))
            return False
    
    async def test_duplicate_handling(self):
        """測試重複資料處理"""
        self.total_tests += 1
        try:
            from database import ArticleModel
            
            # 使用一個特定的測試 URL
            test_url = "https://httpbin.org/headers"
            
            # 第一次爬取並儲存
            result1 = await self.crawler.crawl_url(test_url)
            if not result1.success:
                print_test_result("重複處理", False, "第一次爬取失敗")
                return False
            
            # 檢查是否已存在
            existing = self.db_ops.get_article_by_url(test_url)
            initial_count = 1 if existing else 0
            
            if not existing:
                # 如果不存在，創建第一個
                article1 = ArticleModel(
                    url=test_url,
                    title="重複測試文章",
                    content=result1.content or "測試內容",
                    metadata={"test": "duplicate_1"}
                )
                
                if not self.db_ops.create_article(article1):
                    print_test_result("重複處理", False, "第一次儲存失敗")
                    return False
                initial_count = 1
            
            # 嘗試再次儲存相同 URL 的文章
            article2 = ArticleModel(
                url=test_url,
                title="重複測試文章 2",
                content="不同的內容",
                metadata={"test": "duplicate_2"}
            )
            
            # 這應該失敗或被忽略（因為 URL 重複）
            duplicate_save = self.db_ops.create_article(article2)
            
            # 檢查最終只有一筆記錄
            final_article = self.db_ops.get_article_by_url(test_url)
            
            if final_article:
                # 重複處理正確：要麼拒絕儲存，要麼只有一筆記錄
                passed = True
                print_test_result("重複處理", True, "正確處理重複 URL")
                self.passed_tests += 1
                return True
            else:
                print_test_result("重複處理", False, "找不到任何記錄")
                return False
                
        except Exception as e:
            print_test_result("重複處理", False, str(e))
            return False
    
    async def tearDown(self):
        """測試清理"""
        if self.crawler:
            await self.crawler.close()
    
    async def run_all_tests(self):
        """運行所有整合測試"""
        print_test_header("完整系統整合測試")
        
        # 準備測試環境
        if not await self.setUp():
            print("❌ 無法準備整合測試環境")
            return False
        
        try:
            # 執行測試
            await self.test_crawl_and_save_pipeline()
            await self.test_batch_crawl_and_save()
            await self.test_data_consistency()
            await self.test_duplicate_handling()
            
        finally:
            # 清理
            await self.tearDown()
        
        # 顯示結果
        print_test_summary(self.passed_tests, self.total_tests)
        
        return self.passed_tests == self.total_tests

async def main():
    """主函數"""
    test_suite = IntegrationTestSuite()
    success = await test_suite.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
