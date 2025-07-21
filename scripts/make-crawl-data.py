#!/usr/bin/env python3
"""
make-crawl-data.py
爬蟲第二階段：深度爬取資料內容
支援多種爬取策略：DFS、BFS、從檔案讀取
"""

import sys
import asyncio
from pathlib import Path
from typing import List, Dict
from urllib.parse import urlparse
from datetime import datetime

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.client import SupabaseClient
from database.operations import DatabaseOperations
from database.models import ArticleModel, CrawlStatus
from config import Config
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class CrawlStrategy:
    """爬取策略基類"""
    
    def __init__(self, max_urls: int = 10):
        self.max_urls = max_urls
        self.crawled_count = 0
    
    async def crawl_with_crawl4ai(self, url: str) -> dict:
        """使用 crawl4ai 爬取單個網址"""
        try:
            from crawl4ai import AsyncWebCrawler
            
            print(f"🕷️ 正在爬取: {url}")
            
            async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
                result = await crawler.arun(
                    url=url,
                    word_count_threshold=10,
                    bypass_cache=True
                )
                
                if result.success:
                    content = result.markdown or result.cleaned_html or "無內容"
                    metadata = result.metadata or {}
                    title = metadata.get('title', f"來自 {urlparse(url).netloc} 的文章")
                    
                    return {
                        'success': True,
                        'url': url,
                        'title': title,
                        'content': content,
                        'word_count': len(content.split()),
                        'metadata': metadata
                    }
                else:
                    return {
                        'success': False,
                        'url': url,
                        'error': "爬取失敗"
                    }
                    
        except Exception as e:
            print(f"❌ 爬取錯誤 {url}: {e}")
            return {
                'success': False,
                'url': url,
                'error': str(e)
            }

class DFSCrawlStrategy(CrawlStrategy):
    """深度優先搜尋爬取策略"""
    
    async def crawl(self, start_urls: List[str], db_ops: DatabaseOperations) -> int:
        """使用 crawl4ai 的 DFS 策略進行深度爬取"""
        try:
            from crawl4ai import AsyncWebCrawler
            from crawl4ai.async_crawler_strategy import AsyncCrawlerStrategy
            
            print("🌊 使用 DFS 深度優先策略爬取")
            
            success_count = 0
            
            async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
                for start_url in start_urls[:3]:  # 限制起始 URL 數量
                    if self.crawled_count >= self.max_urls:
                        break
                    
                    print(f"🎯 DFS 起始點: {start_url}")
                    
                    # 使用 crawl4ai 的內建 DFS 策略
                    try:
                        from crawl4ai.crawling_strategy import BFSCrawlerStrategy
                        
                        # 創建爬取策略
                        strategy = BFSCrawlerStrategy(
                            max_depth=2,
                            max_pages=min(10, self.max_urls - self.crawled_count)
                        )
                        
                        # 執行深度爬取
                        results = await crawler.arun_many(
                            urls=[start_url],
                            strategy=strategy,
                            word_count_threshold=10,
                            bypass_cache=True
                        )
                        
                        for result in results:
                            if self.crawled_count >= self.max_urls:
                                break
                                
                            if result.success:
                                # 檢查是否已存在
                                if db_ops.article_exists(result.url):
                                    print(f"⏭️ 跳過 (已存在): {result.url}")
                                    continue
                                
                                # 處理內容
                                content = result.markdown or result.cleaned_html or "無內容"
                                metadata = result.metadata or {}
                                
                                if len(content.split()) < 10:
                                    print(f"⚠️ 內容太短，跳過: {result.url}")
                                    continue
                                
                                # 創建文章記錄
                                article = ArticleModel(
                                    url=result.url,
                                    title=metadata.get('title', f"DFS 文章 {self.crawled_count + 1}"),
                                    content=content,
                                    metadata={
                                        'word_count': len(content.split()),
                                        'content_type': 'markdown',
                                        'crawl_strategy': 'DFS',
                                        'crawl_timestamp': datetime.now().isoformat(),
                                        'source': 'crawl4ai_dfs',
                                        **metadata
                                    }
                                )
                                
                                # 保存到資料庫
                                if db_ops.create_article(article):
                                    success_count += 1
                                    self.crawled_count += 1
                                    print(f"✅ DFS 成功: {article.title[:50]}...")
                                
                    except ImportError:
                        # 如果沒有策略模組，使用基本方法
                        print("⚠️ 使用基本 DFS 方法")
                        result = await self.crawl_with_crawl4ai(start_url)
                        if result['success'] and not db_ops.article_exists(result['url']):
                            if result['word_count'] >= 10:
                                article = ArticleModel(
                                    url=result['url'],
                                    title=result['title'],
                                    content=result['content'],
                                    metadata={**result['metadata'], 'crawl_strategy': 'DFS_basic'}
                                )
                                if db_ops.create_article(article):
                                    success_count += 1
                                    self.crawled_count += 1
                    
                    except Exception as e:
                        logger.error(f"DFS 爬取失敗 {start_url}: {e}")
                        continue
            
            return success_count
            
        except Exception as e:
            logger.error(f"DFS 策略失敗: {e}")
            return 0

class BFSCrawlStrategy(CrawlStrategy):
    """廣度優先搜尋爬取策略"""
    
    async def crawl(self, start_urls: List[str], db_ops: DatabaseOperations) -> int:
        """使用 BFS 策略進行廣度爬取"""
        print("🌐 使用 BFS 廣度優先策略爬取")
        
        success_count = 0
        queue = start_urls[:self.max_urls]
        
        while queue and self.crawled_count < self.max_urls:
            url = queue.pop(0)
            
            # 檢查是否已存在
            if db_ops.article_exists(url):
                print(f"⏭️ 跳過 (已存在): {url}")
                continue
            
            # 爬取內容
            result = await self.crawl_with_crawl4ai(url)
            
            if result['success'] and result['word_count'] >= 10:
                # 創建文章記錄
                article = ArticleModel(
                    url=result['url'],
                    title=result['title'],
                    content=result['content'],
                    metadata={
                        **result['metadata'],
                        'crawl_strategy': 'BFS',
                        'crawl_timestamp': datetime.now().isoformat()
                    }
                )
                
                # 保存到資料庫
                if db_ops.create_article(article):
                    success_count += 1
                    self.crawled_count += 1
                    print(f"✅ BFS 成功 [{self.crawled_count}/{self.max_urls}]: {article.title[:50]}...")
        
        return success_count

class DatabaseCrawlStrategy(CrawlStrategy):
    """基於資料庫的爬取策略 - 從 discovered_urls 表格讀取待爬取的 URL"""
    
    def __init__(self, max_urls: int = 10, url_type: str = "content"):
        super().__init__(max_urls)
        self.url_type = url_type
    
    async def crawl(self, start_urls: List[str], db_ops: DatabaseOperations) -> int:
        """從資料庫讀取待爬取的 URL"""
        print(f"🗄️ 從資料庫讀取待爬取的 URL (類型: {self.url_type})")
        
        # 從資料庫獲取待爬取的 URL
        try:
            pending_urls = db_ops.get_pending_urls(limit=self.max_urls, url_type=self.url_type)
            print(f"📋 從資料庫載入 {len(pending_urls)} 個待爬取 URL")
            
            if not pending_urls:
                print("⚠️ 沒有找到待爬取的 URL，嘗試讀取檔案...")
                return await self._fallback_to_file(start_urls, db_ops)
            
        except Exception as e:
            logger.error(f"從資料庫讀取 URL 失敗: {e}")
            print("⚠️ 資料庫讀取失敗，嘗試讀取檔案...")
            return await self._fallback_to_file(start_urls, db_ops)
        
        success_count = 0
        
        for i, discovered_url in enumerate(pending_urls, 1):
            url = discovered_url.url
            print(f"📄 [{i}/{len(pending_urls)}] {url}")
            
            # 更新狀態為爬取中
            db_ops.update_discovered_url_status(
                discovered_url.id, 
                CrawlStatus.CRAWLING.value
            )
            
            # 檢查是否已存在文章
            if db_ops.article_exists(url):
                print(f"⏭️ 跳過 (文章已存在): {url}")
                # 更新狀態為已完成並關聯到文章
                existing_article = db_ops.get_article_by_url(url)
                if existing_article:
                    db_ops.update_discovered_url_status(
                        discovered_url.id,
                        CrawlStatus.COMPLETED.value,
                        existing_article.id
                    )
                continue
            
            # 爬取內容
            result = await self.crawl_with_crawl4ai(url)
            
            if result['success']:
                # 檢查內容品質
                word_count = result['word_count']
                if word_count < 10:
                    print(f"⚠️ 內容太短 ({word_count} 字)，跳過")
                    db_ops.update_discovered_url_status(
                        discovered_url.id,
                        CrawlStatus.SKIPPED.value,
                        error_message="內容太短"
                    )
                    continue
                
                # 創建文章記錄
                article = ArticleModel(
                    url=url,
                    title=result['title'],
                    content=result['content'],
                    metadata={
                        **result['metadata'],
                        'crawl_strategy': 'database',
                        'source_sitemap_id': discovered_url.source_sitemap_id,
                        'original_priority': discovered_url.priority,
                        'crawl_timestamp': datetime.now().isoformat()
                    }
                )
                
                # 保存到資料庫
                if db_ops.create_article(article):
                    success_count += 1
                    print(f"✅ 成功保存: {article.title[:50]}... ({word_count} 字)")
                    
                    # 更新 discovered_url 狀態為已完成
                    db_ops.update_discovered_url_status(
                        discovered_url.id,
                        CrawlStatus.COMPLETED.value,
                        article.id
                    )
                else:
                    print(f"❌ 保存失敗: {url}")
                    db_ops.update_discovered_url_status(
                        discovered_url.id,
                        CrawlStatus.ERROR.value,
                        error_message="文章保存失敗"
                    )
            else:
                print(f"❌ 爬取失敗: {result.get('error', 'Unknown error')}")
                db_ops.update_discovered_url_status(
                    discovered_url.id,
                    CrawlStatus.ERROR.value,
                    error_message=result.get('error', 'Unknown error')
                )
        
        return success_count
    
    async def _fallback_to_file(self, start_urls: List[str], db_ops: DatabaseOperations) -> int:
        """當資料庫沒有待爬取 URL 時，回退到檔案讀取"""
        file_strategy = FileBasedCrawlStrategy(max_urls=self.max_urls)
        return await file_strategy.crawl(start_urls, db_ops)

class FileBasedCrawlStrategy(CrawlStrategy):
    """基於檔案的爬取策略"""
    
    def __init__(self, max_urls: int = 10, urls_file: str = "discovered_urls.txt"):
        super().__init__(max_urls)
        self.urls_file = urls_file
    
    async def crawl(self, start_urls: List[str], db_ops: DatabaseOperations) -> int:
        """從檔案讀取 URL 進行爬取"""
        print(f"📁 從檔案讀取 URL: {self.urls_file}")
        
        # 讀取檔案中的 URL
        urls_to_crawl = []
        try:
            if Path(self.urls_file).exists():
                with open(self.urls_file, 'r', encoding='utf-8') as f:
                    urls_to_crawl = [line.strip() for line in f if line.strip()]
                print(f"📋 從檔案載入 {len(urls_to_crawl)} 個 URL")
            else:
                print(f"⚠️ 檔案不存在，使用預設 URL")
                urls_to_crawl = start_urls
        except Exception as e:
            logger.error(f"讀取檔案失敗: {e}")
            urls_to_crawl = start_urls
        
        # 限制數量
        urls_to_crawl = urls_to_crawl[:self.max_urls]
        success_count = 0
        
        for i, url in enumerate(urls_to_crawl, 1):
            print(f"📄 [{i}/{len(urls_to_crawl)}] {url}")
            
            # 檢查是否已存在
            if db_ops.article_exists(url):
                print(f"⏭️ 跳過 (已存在): {url}")
                continue
            
            # 爬取內容
            result = await self.crawl_with_crawl4ai(url)
            
            if result['success']:
                # 檢查內容品質
                word_count = result['word_count']
                if word_count < 10:
                    print(f"⚠️ 內容太短 ({word_count} 字)，跳過")
                    continue
                
                # 創建文章記錄
                article = ArticleModel(
                    url=url,
                    title=result['title'],
                    content=result['content'],
                    metadata={
                        **result['metadata'],
                        'crawl_strategy': 'file_based',
                        'source_file': self.urls_file,
                        'crawl_timestamp': datetime.now().isoformat()
                    }
                )
                
                # 保存到資料庫
                try:
                    if db_ops.create_article(article):
                        success_count += 1
                        print(f"✅ 成功儲存: {article.title[:50]}...")
                        print(f"   📝 內容: {word_count} 字")
                    else:
                        print(f"❌ 儲存失敗: 可能是資料庫錯誤")
                except Exception as e:
                    if "已存在" in str(e):
                        print(f"⏭️ 文章已存在，跳過")
                    else:
                        print(f"❌ 儲存錯誤: {e}")
            else:
                print(f"❌ 爬取失敗: {result.get('error', '未知錯誤')}")
        
        return success_count

def get_default_urls() -> List[str]:
    """獲取預設 URL"""
    urls = []
    
    # 從配置獲取網址
    if hasattr(Config, 'TARGET_URLS') and Config.TARGET_URLS:
        urls.extend([url.strip() for url in Config.TARGET_URLS if url.strip()])
    
    # 如果沒有配置，使用預設網址
    if not urls:
        urls = [
            "https://httpbin.org/html",
            "https://httpbin.org/json"
        ]
    
    return urls

async def crawl_data_phase(strategy: str = "database", max_urls: int = 10, urls: List[str] = None):
    """
    爬蟲第二階段：資料爬取
    支援多種策略：database, file, dfs, bfs
    """
    print("📊 RAG 爬蟲階段 2: 資料內容爬取")
    print("=" * 60)
    
    if urls is None:
        urls = get_default_urls()
    
    try:
        # 初始化資料庫
        print("🔗 連接資料庫...")
        supabase_client = SupabaseClient()
        db_ops = DatabaseOperations(supabase_client.get_client())
        
        # 選擇爬取策略
        if strategy.lower() == "database" or strategy.lower() == "db":
            crawler = DatabaseCrawlStrategy(max_urls)
            print("🗄️ 使用資料庫驅動策略")
        elif strategy.lower() == "dfs":
            crawler = DFSCrawlStrategy(max_urls)
            print("🌊 使用深度優先 (DFS) 策略")
        elif strategy.lower() == "bfs":
            crawler = BFSCrawlStrategy(max_urls)
            print("🌐 使用廣度優先 (BFS) 策略")
        else:  # file
            crawler = FileBasedCrawlStrategy(max_urls)
            print("📁 使用檔案驅動策略")
        
        # 執行爬取
        success_count = await crawler.crawl(urls, db_ops)
        
        # 總結
        print(f"📊 資料爬取完成!")
        print(f"✅ 成功: {success_count}/{max_urls}")
        print(f"📈 成功率: {(success_count/max_urls*100):.1f}%")
        
        # 顯示資料庫統計
        try:
            stats = db_ops.get_database_statistics()
            if stats:
                print(f"\n📈 資料庫統計:")
                for table_name, stat in stats.items():
                    if isinstance(stat, dict) and 'count' in stat:
                        print(f"  {table_name}: {stat['count']} 條記錄")
        except Exception as e:
            logger.warning(f"無法獲取統計信息: {e}")
        
        if success_count > 0:
            print("🎯 下一步: 執行 'make chunk' 進行資料分塊")
            return True
        else:
            print("❌ 沒有成功爬取任何資料")
            return False
            
    except Exception as e:
        logger.error(f"資料爬取階段失敗: {e}")
        return False

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG 資料爬取工具 - 第二階段")
    parser.add_argument("--strategy", choices=["database", "file", "dfs", "bfs"], default="database",
                       help="爬取策略: database(資料庫佇列), file(檔案), dfs(深度優先), bfs(廣度優先)")
    parser.add_argument("--urls", nargs="+", help="指定要爬取的網址")
    parser.add_argument("--max-urls", type=int, default=10, help="最大爬取數量")
    
    args = parser.parse_args()
    
    # 執行資料爬取
    try:
        result = asyncio.run(crawl_data_phase(args.strategy, args.max_urls, args.urls))
        
        if result:
            print(f"\n🎉 資料爬取完成!")
            sys.exit(0)
        else:
            print(f"\n❌ 資料爬取失敗!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ 用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 程式異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

def get_target_urls() -> List[str]:
    """從環境變數獲取目標網址"""
    urls = []
    
    # 從配置獲取網址
    if hasattr(Config, 'TARGET_URLS') and Config.TARGET_URLS:
        urls.extend([url.strip() for url in Config.TARGET_URLS if url.strip()])
        print(f"📋 從配置載入 {len(urls)} 個網址")
    
    # 如果沒有配置，使用預設網址
    if not urls:
        print("⚠️ 未找到配置的網址，使用預設測試網址")
        urls = [
            "https://httpbin.org/html",
            "https://httpbin.org/json"
        ]
    
    return urls

async def crawl_with_crawl4ai(url: str) -> dict:
    """使用 crawl4ai 爬取單個網址"""
    try:
        from crawl4ai import AsyncWebCrawler
        
        print(f"🕷️ 正在爬取: {url}")
        
        async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
            result = await crawler.arun(
                url=url,
                word_count_threshold=10,
                bypass_cache=True
            )
            
            if result.success:
                content = result.markdown or result.cleaned_html or "無內容"
                metadata = result.metadata or {}
                title = metadata.get('title', f"來自 {urlparse(url).netloc} 的文章")
                
                return {
                    'success': True,
                    'url': url,
                    'title': title,
                    'content': content,
                    'word_count': len(content.split()),
                    'metadata': metadata
                }
            else:
                return {
                    'success': False,
                    'url': url,
                    'error': "爬取失敗"
                }
                
    except Exception as e:
        print(f"❌ 爬取錯誤 {url}: {e}")
        return {
            'success': False,
            'url': url,
            'error': str(e)
        }

async def crawl_urls(urls: List[str] = None, max_urls: int = 10):
    """爬取網址列表"""
    print("🕷️ RAG 步驟 2: 資料爬取")
    print("=" * 50)
    
    if urls is None:
        urls = get_target_urls()
    
    if not urls:
        print("❌ 沒有要爬取的網址")
        return False
    
    # 限制數量
    urls = urls[:max_urls]
    print(f"📊 準備爬取 {len(urls)} 個網址")
    
    try:
        # 初始化資料庫
        print("🔗 連接資料庫...")
        supabase_client = SupabaseClient()
        db_ops = DatabaseOperations(supabase_client)
        
        success_count = 0
        
        for i, url in enumerate(urls, 1):
            print(f"\n📄 [{i}/{len(urls)}] {url}")
            
            # 檢查是否已存在
            if db_ops.article_exists(url):
                print(f"⏭️ 跳過 (已存在): {url}")
                continue
            
            # 爬取內容
            result = await crawl_with_crawl4ai(url)
            
            if result['success']:
                # 檢查內容品質
                word_count = result['word_count']
                if word_count < 10:
                    print(f"⚠️ 內容太短 ({word_count} 字)，跳過")
                    continue
                
                # 創建文章記錄
                article = ArticleModel(
                    url=url,
                    title=result['title'],
                    content=result['content'],
                    metadata={
                        'word_count': word_count,
                        'content_type': 'markdown',
                        'crawl_timestamp': datetime.now().isoformat(),
                        'source': 'crawl4ai',
                        **result.get('metadata', {})
                    }
                )
                
                # 儲存到資料庫
                try:
                    saved = db_ops.create_article(article)
                    if saved:
                        success_count += 1
                        print(f"✅ 成功儲存: {article.title[:50]}...")
                        print(f"   📝 內容: {word_count} 字")
                    else:
                        print(f"❌ 儲存失敗: 可能是資料庫錯誤")
                except Exception as e:
                    if "已存在" in str(e):
                        print(f"⏭️ 文章已存在，跳過")
                    else:
                        print(f"❌ 儲存錯誤: {e}")
            else:
                print(f"❌ 爬取失敗: {result.get('error', '未知錯誤')}")
        
        # 總結
        print(f"\n📊 爬取完成!")
        print(f"✅ 成功: {success_count}/{len(urls)}")
        print(f"📈 成功率: {(success_count/len(urls)*100):.1f}%")
        
        if success_count > 0:
            print("🎯 下一步: 執行 'make chunk' 進行資料分塊")
            return True
        else:
            print("❌ 沒有成功爬取任何資料")
            return False
            
    except Exception as e:
        print(f"❌ 爬取過程出錯: {e}")
        logger.exception("詳細錯誤信息")
        return False

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG 資料爬取工具")
    parser.add_argument("--urls", nargs="+", help="指定要爬取的網址")
    parser.add_argument("--max-urls", type=int, default=5, help="最大爬取數量")
    
    args = parser.parse_args()
    
    # 執行爬取
    try:
        result = asyncio.run(crawl_urls(args.urls, args.max_urls))
        
        if result:
            print("\n🎉 爬取任務完成!")
            sys.exit(0)
        else:
            print("\n❌ 爬取任務失敗!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ 用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 程式異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
