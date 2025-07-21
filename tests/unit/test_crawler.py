#!/usr/bin/env python3
"""
爬蟲功能單元測試
測試爬蟲的核心功能，包括單URL和批量爬取
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

class CrawlerTestSuite:
    """爬蟲測試套件"""
    
    def __init__(self):
        self.passed_tests = 0
        self.total_tests = 0
        self.crawler = None
    
    async def setUp(self):
        """測試準備"""
        try:
            from spider.crawlers.simple_crawler import SimpleWebCrawler
            self.crawler = SimpleWebCrawler()
            return True
        except Exception as e:
            logger.error(f"爬蟲測試準備失敗: {e}")
            return False
    
    async def test_single_url_crawl(self):
        """測試單個 URL 爬取"""
        self.total_tests += 1
        try:
            test_url = TEST_URLS[0]  # 使用第一個測試 URL
            result = await self.crawler.crawl_url(test_url)
            
            if result.success:
                print_test_result(
                    "單 URL 爬取", 
                    True, 
                    f"成功爬取 {test_url} ({result.response_time:.2f}s)"
                )
                self.passed_tests += 1
                return True
            else:
                print_test_result("單 URL 爬取", False, result.error)
                return False
                
        except Exception as e:
            print_test_result("單 URL 爬取", False, str(e))
            return False
    
    async def test_batch_crawl(self):
        """測試批量爬取"""
        self.total_tests += 1
        try:
            test_urls = TEST_URLS[:TEST_CONFIG["test_batch_size"]]
            results = await self.crawler.crawl_batch(
                test_urls, 
                max_concurrent=TEST_CONFIG["max_concurrent"]
            )
            
            success_count = sum(1 for r in results if r.success)
            success_rate = success_count / len(results) * 100
            
            # 認為 >= 80% 成功率為通過
            passed = success_rate >= 80
            
            print_test_result(
                "批量爬取", 
                passed, 
                f"{success_count}/{len(results)} 成功 ({success_rate:.1f}%)"
            )
            
            if passed:
                self.passed_tests += 1
            return passed
                
        except Exception as e:
            print_test_result("批量爬取", False, str(e))
            return False
    
    async def test_error_handling(self):
        """測試錯誤處理"""
        self.total_tests += 1
        try:
            # 測試無效 URL
            invalid_urls = [
                "https://invalid-domain-that-does-not-exist-12345.com",
                "http://localhost:99999",  # 無效端口
                "not-a-url"
            ]
            
            results = await self.crawler.crawl_batch(invalid_urls, max_concurrent=2)
            
            # 檢查是否正確處理錯誤
            error_count = sum(1 for r in results if not r.success and r.error)
            
            if error_count == len(invalid_urls):
                print_test_result("錯誤處理", True, f"正確處理 {error_count} 個錯誤 URL")
                self.passed_tests += 1
                return True
            else:
                print_test_result("錯誤處理", False, f"僅處理 {error_count}/{len(invalid_urls)} 個錯誤")
                return False
                
        except Exception as e:
            print_test_result("錯誤處理", False, str(e))
            return False
    
    async def test_content_extraction(self):
        """測試內容提取"""
        self.total_tests += 1
        try:
            # 使用一個已知有內容的 URL
            test_url = "https://example.com"
            result = await self.crawler.crawl_url(test_url)
            
            if result.success:
                has_title = bool(result.title and len(result.title.strip()) > 0)
                has_content = bool(result.content and len(result.content.strip()) > 0)
                has_markdown = bool(result.markdown and len(result.markdown.strip()) > 0)
                
                content_score = sum([has_title, has_content, has_markdown])
                
                if content_score >= 2:  # 至少要有 2 種內容
                    print_test_result(
                        "內容提取", 
                        True, 
                        f"成功提取標題: {has_title}, 內容: {has_content}, Markdown: {has_markdown}"
                    )
                    self.passed_tests += 1
                    return True
                else:
                    print_test_result("內容提取", False, "提取的內容不足")
                    return False
            else:
                print_test_result("內容提取", False, result.error)
                return False
                
        except Exception as e:
            print_test_result("內容提取", False, str(e))
            return False
    
    async def test_performance(self):
        """測試性能"""
        self.total_tests += 1
        try:
            # 測試並發性能
            test_urls = TEST_URLS[:3]  # 使用 3 個 URL
            
            import time
            start_time = time.time()
            
            results = await self.crawler.crawl_batch(
                test_urls, 
                max_concurrent=TEST_CONFIG["max_concurrent"]
            )
            
            end_time = time.time()
            total_time = end_time - start_time
            
            success_count = sum(1 for r in results if r.success)
            avg_time = total_time / len(test_urls)
            
            # 平均每個 URL 不超過 10 秒認為性能合格
            performance_ok = avg_time <= 10.0 and success_count > 0
            
            print_test_result(
                "性能測試", 
                performance_ok, 
                f"平均 {avg_time:.2f}s/URL, {success_count} 成功"
            )
            
            if performance_ok:
                self.passed_tests += 1
            return performance_ok
                
        except Exception as e:
            print_test_result("性能測試", False, str(e))
            return False
    
    async def tearDown(self):
        """測試清理"""
        if self.crawler:
            await self.crawler.close()
    
    async def run_all_tests(self):
        """運行所有測試"""
        print_test_header("爬蟲功能單元測試")
        
        # 準備測試環境
        if not await self.setUp():
            print("❌ 無法準備測試環境")
            return False
        
        try:
            # 執行測試
            await self.test_single_url_crawl()
            await self.test_batch_crawl()
            await self.test_error_handling()
            await self.test_content_extraction()
            await self.test_performance()
            
        finally:
            # 清理
            await self.tearDown()
        
        # 顯示結果
        print_test_summary(self.passed_tests, self.total_tests)
        
        return self.passed_tests == self.total_tests

async def main():
    """主函數"""
    test_suite = CrawlerTestSuite()
    success = await test_suite.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
