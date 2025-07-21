#!/usr/bin/env python3
"""
make-crawl-robot.py
爬蟲第一階段：解析 robots.txt 和發現連結
"""

import sys
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
from datetime import datetime

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.client import SupabaseClient
from database.operations import DatabaseOperations
from database.models import SitemapModel, DiscoveredURLModel, RobotsTxtModel, SitemapType, URLType, CrawlStatus
from config import Config
import logging
import aiohttp

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class RobotsParser:
    """robots.txt 解析器"""
    
    def __init__(self):
        self.sitemap_urls = []
        self.allowed_paths = []
        self.disallowed_paths = []
        self.crawl_delay = 1.0
    
    def parse_robots(self, robots_content: str, base_url: str) -> Dict:
        """解析 robots.txt 內容"""
        lines = robots_content.strip().split('\n')
        current_user_agent = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if line.lower().startswith('user-agent:'):
                current_user_agent = line.split(':', 1)[1].strip()
            elif line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                self.sitemap_urls.append(sitemap_url)
            elif line.lower().startswith('allow:'):
                path = line.split(':', 1)[1].strip()
                self.allowed_paths.append(path)
            elif line.lower().startswith('disallow:'):
                path = line.split(':', 1)[1].strip()
                if path != '/':  # 不添加完全禁止的路徑
                    self.disallowed_paths.append(path)
            elif line.lower().startswith('crawl-delay:'):
                try:
                    self.crawl_delay = float(line.split(':', 1)[1].strip())
                except:
                    pass
        
        return {
            'sitemap_urls': self.sitemap_urls,
            'allowed_paths': self.allowed_paths,
            'disallowed_paths': self.disallowed_paths,
            'crawl_delay': self.crawl_delay,
            'base_url': base_url
        }

class SitemapParser:
    """Sitemap 解析器"""
    
    async def parse_sitemap(self, sitemap_url: str) -> List[str]:
        """解析 sitemap.xml 獲取 URL 列表"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sitemap_url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        return self._extract_urls_from_sitemap(content)
        except Exception as e:
            logger.error(f"解析 sitemap 失敗 {sitemap_url}: {e}")
        return []
    
    def _extract_urls_from_sitemap(self, sitemap_content: str) -> List[str]:
        """從 sitemap 內容中提取 URL"""
        urls = []
        
        # 使用正則表達式提取 <loc> 標籤中的 URL
        loc_pattern = r'<loc>(.*?)</loc>'
        matches = re.findall(loc_pattern, sitemap_content, re.IGNORECASE)
        
        for url in matches:
            url = url.strip()
            if url and not url.endswith('.xml'):  # 排除其他 sitemap 文件
                urls.append(url)
        
        return urls

class LinkDiscovery:
    """連結發現器"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
    
    async def discover_links_from_homepage(self) -> List[str]:
        """從首頁發現連結"""
        try:
            from crawl4ai import AsyncWebCrawler
            
            async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
                result = await crawler.arun(url=self.base_url, bypass_cache=True)
                
                if result.success and result.links:
                    internal_links = result.links.get('internal', [])
                    # 過濾出有效的內部連結
                    valid_links = []
                    for link in internal_links[:50]:  # 限制數量
                        if self._is_valid_link(link):
                            valid_links.append(link)
                    return valid_links
        except Exception as e:
            logger.error(f"從首頁發現連結失敗: {e}")
        
        return []
    
    def _is_valid_link(self, url: str) -> bool:
        """檢查連結是否有效"""
        try:
            parsed = urlparse(url)
            
            # 必須是相同域名
            if parsed.netloc and parsed.netloc != self.domain:
                return False
            
            # 排除不需要的文件類型
            excluded_extensions = ['.pdf', '.jpg', '.png', '.gif', '.css', '.js', '.xml']
            if any(url.lower().endswith(ext) for ext in excluded_extensions):
                return False
            
            # 排除常見的系統路徑
            excluded_paths = ['/admin', '/api', '/login', '/register', '/search']
            if any(path in url.lower() for path in excluded_paths):
                return False
            
            return True
        except:
            return False

async def crawl_robot_phase(robot_urls: List[str] = None) -> Dict:
    """
    爬蟲第一階段：解析 robots.txt 和發現連結
    使用新的資料庫結構來儲存 sitemap 層級關係
    """
    print("🤖 RAG 爬蟲階段 1: Robot 解析與連結發現")
    print("=" * 60)
    
    if robot_urls is None:
        robot_urls = [url.strip() for url in Config.TARGET_URLS if url.strip()]
    
    if not robot_urls:
        print("❌ 沒有找到 robots.txt URL")
        return {'discovered_urls': [], 'robots_info': {}}
    
    # 初始化資料庫連接
    try:
        client = SupabaseClient()
        db_ops = DatabaseOperations(client.get_client())
        logger.info("✅ 資料庫連接成功")
    except Exception as e:
        logger.error(f"❌ 資料庫連接失敗: {e}")
        return {'discovered_urls': [], 'robots_info': {}}
    
    all_discovered_urls = set()
    robots_info = {}
    
    try:
        # 初始化解析器
        robots_parser = RobotsParser()
        sitemap_parser = SitemapParser()
        
        for robot_url in robot_urls:
            print(f"\n🔍 處理: {robot_url}")
            base_url = robot_url.replace('/robots.txt', '')
            domain = urlparse(base_url).netloc
            
            try:
                # 1. 解析 robots.txt
                async with aiohttp.ClientSession() as session:
                    async with session.get(robot_url, timeout=30) as response:
                        if response.status == 200:
                            robots_content = await response.text()
                            robots_data = robots_parser.parse_robots(robots_content, base_url)
                            robots_info[robot_url] = robots_data
                            
                            # 儲存 robots.txt 到資料庫
                            robots_model = RobotsTxtModel(
                                domain=domain,
                                robots_url=robot_url,
                                content=robots_content,
                                sitemaps_count=len(robots_data['sitemap_urls']),
                                rules_count=len(robots_data['allowed_paths']) + len(robots_data['disallowed_paths']),
                                metadata={
                                    'crawl_delay': robots_data['crawl_delay'],
                                    'allowed_paths': robots_data['allowed_paths'],
                                    'disallowed_paths': robots_data['disallowed_paths']
                                }
                            )
                            
                            if db_ops.create_robots_txt(robots_model):
                                logger.info(f"✅ robots.txt 已儲存到資料庫: {domain}")
                            
                            print(f"📄 發現 {len(robots_data['sitemap_urls'])} 個 sitemap")
                            print(f"⏱️ 建議爬取延遲: {robots_data['crawl_delay']} 秒")
                            
                            # 2. 處理 sitemap 層級結構
                            for sitemap_url in robots_data['sitemap_urls']:
                                print(f"🗺️ 處理 sitemap: {sitemap_url}")
                                
                                # 創建或獲取 sitemap 記錄
                                sitemap_model = SitemapModel(
                                    url=sitemap_url,
                                    sitemap_type=SitemapType.SITEMAP,
                                    status=CrawlStatus.PENDING,
                                    metadata={
                                        'source_robots': robot_url,
                                        'domain': domain
                                    }
                                )
                                
                                if db_ops.create_sitemap(sitemap_model):
                                    logger.info(f"✅ Sitemap 已儲存: {sitemap_url}")
                                
                                # 解析 sitemap 內容
                                sitemap_urls = await sitemap_parser.parse_sitemap(sitemap_url)
                                
                                if sitemap_urls:
                                    # 更新 sitemap 狀態和 URL 數量
                                    db_sitemap = db_ops.get_sitemap_by_url(sitemap_url)
                                    if db_sitemap:
                                        db_ops.update_sitemap_status(db_sitemap.id, CrawlStatus.COMPLETED.value)
                                        
                                        # 創建發現的 URL 記錄
                                        discovered_models = []
                                        for url in sitemap_urls:
                                            # 判斷 URL 類型
                                            url_type = URLType.SITEMAP if url.endswith('.xml') else URLType.CONTENT
                                            
                                            discovered_url = DiscoveredURLModel(
                                                url=url,
                                                source_sitemap_id=db_sitemap.id,
                                                url_type=url_type,
                                                priority=0.5,  # 默認優先級
                                                crawl_status=CrawlStatus.PENDING,
                                                metadata={
                                                    'discovered_from': sitemap_url,
                                                    'domain': domain
                                                }
                                            )
                                            discovered_models.append(discovered_url)
                                        
                                        # 批量儲存發現的 URL
                                        created_count = db_ops.bulk_create_discovered_urls(discovered_models)
                                        logger.info(f"✅ 批量創建 {created_count} 個發現的 URL")
                                        
                                        all_discovered_urls.update(sitemap_urls)
                                        print(f"   ✅ 發現並儲存 {len(sitemap_urls)} 個 URL")
                                    
                                else:
                                    # 標記為錯誤狀態
                                    db_sitemap = db_ops.get_sitemap_by_url(sitemap_url)
                                    if db_sitemap:
                                        db_ops.update_sitemap_status(db_sitemap.id, CrawlStatus.ERROR.value, "無法解析 sitemap 內容")
                            
                            # 3. 從首頁發現連結（可選）
                            if len(all_discovered_urls) < 50:  # 如果發現的 URL 不多，嘗試首頁發現
                                link_discovery = LinkDiscovery(base_url)
                                homepage_links = await link_discovery.discover_links_from_homepage()
                                
                                if homepage_links:
                                    # 創建一個特殊的 "首頁發現" sitemap 記錄
                                    homepage_sitemap = SitemapModel(
                                        url=f"{base_url}/homepage-discovery",
                                        sitemap_type=SitemapType.URLSET,
                                        status=CrawlStatus.COMPLETED,
                                        title="Homepage Link Discovery",
                                        urls_count=len(homepage_links),
                                        metadata={
                                            'source_type': 'homepage_discovery',
                                            'base_url': base_url,
                                            'domain': domain
                                        }
                                    )
                                    
                                    if db_ops.create_sitemap(homepage_sitemap):
                                        db_sitemap = db_ops.get_sitemap_by_url(homepage_sitemap.url)
                                        if db_sitemap:
                                            # 儲存首頁發現的連結
                                            homepage_discovered = []
                                            for url in homepage_links:
                                                discovered_url = DiscoveredURLModel(
                                                    url=url,
                                                    source_sitemap_id=db_sitemap.id,
                                                    url_type=URLType.CONTENT,
                                                    priority=0.3,  # 較低優先級
                                                    crawl_status=CrawlStatus.PENDING,
                                                    metadata={
                                                        'discovered_from': 'homepage',
                                                        'domain': domain
                                                    }
                                                )
                                                homepage_discovered.append(discovered_url)
                                            
                                            created_count = db_ops.bulk_create_discovered_urls(homepage_discovered)
                                            all_discovered_urls.update(homepage_links)
                                            print(f"🏠 從首頁發現並儲存 {created_count} 個連結")
                        
                        else:
                            print(f"❌ 無法訪問 robots.txt: HTTP {response.status}")
                            
            except Exception as e:
                logger.error(f"處理 {robot_url} 失敗: {e}")
                continue
        
        discovered_urls = list(all_discovered_urls)
        
        print(f"\n📊 Robot 階段完成!")
        print(f"🔗 總共發現 {len(discovered_urls)} 個有效 URL")
        print(f"💾 所有數據已儲存到資料庫")
        print(f"🎯 下一步: 執行 'make crawl-data' 進行內容爬取")
        
        # 仍然保存到檔案以便兼容性
        urls_file = Path("discovered_urls.txt")
        with open(urls_file, 'w', encoding='utf-8') as f:
            for url in discovered_urls:
                f.write(f"{url}\n")
        
        print(f"📄 URL 列表也已保存到: {urls_file}")
        
        # 顯示資料庫統計
        try:
            sitemap_stats = db_ops.get_sitemap_stats()
            if sitemap_stats:
                print(f"\n📊 資料庫統計:")
                for table_name, stats in sitemap_stats.items():
                    print(f"  {table_name}: {stats.get('count', 0)} 條記錄")
        except Exception as e:
            logger.warning(f"無法獲取統計信息: {e}")
        
        return {
            'discovered_urls': discovered_urls,
            'robots_info': robots_info,
            'total_count': len(discovered_urls)
        }
        
    except Exception as e:
        logger.error(f"Robot 階段失敗: {e}")
        return {'discovered_urls': [], 'robots_info': {}}

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="爬蟲 Robot 階段")
    parser.add_argument("--robots", nargs="+", help="指定 robots.txt URL")
    parser.add_argument("--save-to-db", action="store_true", help="保存結果到資料庫")
    
    args = parser.parse_args()
    
    # 執行 Robot 階段
    try:
        result = asyncio.run(crawl_robot_phase(args.robots))
        
        if result['discovered_urls']:
            print(f"\n🎉 Robot 階段完成! 發現 {len(result['discovered_urls'])} 個 URL")
            sys.exit(0)
        else:
            print(f"\n❌ Robot 階段失敗!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ 用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 程式異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
