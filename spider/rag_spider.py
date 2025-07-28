"""
RAG Spider - 完全對應 schema.sql 資料庫架構
與 database/models.py 完全整合的爬蟲實作
"""

import asyncio
import aiohttp
import logging
import hashlib
import xml.etree.ElementTree as ET
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import time

from database.models import (
    DiscoveredURLModel, ArticleModel, ChunkModel, SitemapModel,
    CrawlStatus, ChangeFreq, ModelFactory
)
from database.operations import get_database_operations

logger = logging.getLogger(__name__)

class RAGSpider:
    """
    RAG 系統爬蟲 - 完全對應 schema.sql 架構
    支援 sitemap 解析和網頁爬取
    """
    
    def __init__(self, max_concurrent: int = 5, delay: float = 1.0):
        """
        初始化爬蟲
        
        Args:
            max_concurrent: 最大並發數
            delay: 請求間隔（秒）
        """
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.session = None
        self.db = get_database_operations()
        
        # 統計信息
        self.stats = {
            "sitemaps_processed": 0,
            "urls_discovered": 0,
            "articles_crawled": 0,
            "chunks_created": 0,
            "errors": 0
        }
        
    async def __aenter__(self):
        """異步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'RAG-Spider/1.0 (compatible; Python-aiohttp)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-TW,en-US;q=0.9,en;q=0.8'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def parse_sitemap(self, sitemap_url: str, update_db: bool = True) -> Tuple[bool, List[DiscoveredURLModel]]:
        """
        解析 sitemap 並返回發現的 URL
        完全對應 discovered_urls 表格架構
        
        Args:
            sitemap_url: Sitemap URL
            update_db: 是否更新資料庫中的 sitemap 狀態
            
        Returns:
            Tuple[bool, List[DiscoveredURLModel]]: (成功標誌, URL列表)
        """
        try:
            logger.info(f"開始解析 Sitemap: {sitemap_url}")
            
            # 1. 如果需要更新資料庫，先查找已存在的 sitemap 記錄
            sitemap_record_id = None
            if update_db and self.db:
                try:
                    from database.client import SupabaseClient
                    db_client = SupabaseClient()
                    admin_client = db_client.get_admin_client()
                    
                    if admin_client:
                        existing = admin_client.table("sitemaps").select("id").eq("url", sitemap_url).execute()
                        if existing.data:
                            sitemap_record_id = existing.data[0]["id"]
                            # 更新狀態為正在爬取
                            admin_client.table("sitemaps").update({"status": "crawling"}).eq("id", sitemap_record_id).execute()
                            print(f"🔄 更新 sitemap 狀態為爬取中: {sitemap_url}")
                except Exception as e:
                    logger.warning(f"更新 sitemap 狀態失敗: {e}")
            
            # 2. 下載 Sitemap
            async with self.session.get(sitemap_url) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    if update_db and sitemap_record_id:
                        try:
                            admin_client.table("sitemaps").update({
                                "status": "error",
                                "error_message": error_msg
                            }).eq("id", sitemap_record_id).execute()
                        except Exception as e:
                            logger.warning(f"更新 sitemap 錯誤狀態失敗: {e}")
                    logger.error(f"下載 Sitemap 失敗: {error_msg}")
                    return False, []
                    
                content = await response.text()
                
            # 3. 解析 XML
            discovered_urls = self._parse_sitemap_xml(content, sitemap_url)
            
            # 4. 批量插入發現的 URL
            if discovered_urls and self.db:
                count = self.db.bulk_create_discovered_urls(discovered_urls)
                logger.info(f"從 Sitemap 發現 {len(discovered_urls)} 個 URL，成功插入 {count} 個")
                
                # 更新 Sitemap 狀態為完成
                if update_db and sitemap_record_id:
                    try:
                        admin_client.table("sitemaps").update({
                            "status": "completed",
                            "urls_count": count,
                            "parsed_at": datetime.now().isoformat()
                        }).eq("id", sitemap_record_id).execute()
                        print(f"✅ 更新 sitemap 完成狀態: {sitemap_url} ({count} 個 URLs)")
                    except Exception as e:
                        logger.warning(f"更新 sitemap 完成狀態失敗: {e}")
            
            self.stats["sitemaps_processed"] += 1
            self.stats["urls_discovered"] += len(discovered_urls)
            
            return True, discovered_urls
            
        except Exception as e:
            logger.error(f"解析 Sitemap 時發生錯誤 {sitemap_url}: {e}")
            if update_db and sitemap_record_id:
                try:
                    admin_client.table("sitemaps").update({
                        "status": "error",
                        "error_message": str(e)
                    }).eq("id", sitemap_record_id).execute()
                except Exception as e2:
                    logger.warning(f"更新 sitemap 錯誤狀態失敗: {e2}")
            self.stats["errors"] += 1
            return False, []
    
    def _parse_sitemap_xml(self, xml_content: str, sitemap_url: str) -> List[DiscoveredURLModel]:
        """
        解析 XML 內容並提取 URL 信息
        完全對應 discovered_urls 表格的所有欄位
        支援 <urlset> 和 <sitemapindex> 兩種格式
        """
        discovered_urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # 定義 XML 命名空間
            namespaces = {
                'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            # 檢查是否為 sitemapindex 格式
            if root.tag.endswith('sitemapindex'):
                print(f"📋 檢測到 sitemap index 格式: {sitemap_url}")
                # 處理 sitemapindex - 提取子 sitemap URLs
                for sitemap_elem in root.findall('.//sitemap:sitemap', namespaces):
                    try:
                        loc_elem = sitemap_elem.find('sitemap:loc', namespaces)
                        if loc_elem is None or not loc_elem.text:
                            continue
                        
                        sub_sitemap_url = loc_elem.text.strip()
                        print(f"🔗 發現子 sitemap: {sub_sitemap_url}")
                        
                        # 使用同步方式處理子 sitemap，避免事件循環衝突
                        try:
                            import requests
                            response = requests.get(sub_sitemap_url, timeout=10)
                            if response.status_code == 200:
                                sub_content = response.text
                                sub_urls = self._parse_sitemap_xml(sub_content, sub_sitemap_url)
                                discovered_urls.extend(sub_urls)
                                print(f"✅ 從子 sitemap 獲得 {len(sub_urls)} 個 URLs: {sub_sitemap_url}")
                                
                                # 限制處理的子 sitemap 數量，避免過多請求
                                if len(discovered_urls) >= 50:  # 限制總數
                                    print(f"⚠️ 已達到 URL 限制，停止處理更多子 sitemap")
                                    break
                            else:
                                print(f"⚠️ 子 sitemap 訪問失敗 (HTTP {response.status_code}): {sub_sitemap_url}")
                        except Exception as e:
                            print(f"⚠️ 處理子 sitemap 異常: {sub_sitemap_url} - {e}")
                            
                    except Exception as e:
                        logger.warning(f"解析子 sitemap 元素時發生錯誤: {e}")
                        continue
                        
            else:
                # 處理標準 urlset 格式
                print(f"📄 檢測到 urlset 格式: {sitemap_url}")
                # 查找所有 URL 元素
                for url_elem in root.findall('.//sitemap:url', namespaces):
                    try:
                        # 提取必要字段
                        loc_elem = url_elem.find('sitemap:loc', namespaces)
                        if loc_elem is None or not loc_elem.text:
                            continue
                        
                        url = loc_elem.text.strip()
                        
                        # 提取可選字段
                        priority = None
                        priority_elem = url_elem.find('sitemap:priority', namespaces)
                        if priority_elem is not None and priority_elem.text:
                            try:
                                priority = float(priority_elem.text)
                                # 確保在 0.0-1.0 範圍內
                                priority = max(0.0, min(1.0, priority))
                            except ValueError:
                                priority = None
                        
                        changefreq = None
                        changefreq_elem = url_elem.find('sitemap:changefreq', namespaces)
                        if changefreq_elem is not None and changefreq_elem.text:
                            try:
                                changefreq = ChangeFreq(changefreq_elem.text.lower())
                            except ValueError:
                                changefreq = None
                        
                        lastmod = None
                        lastmod_elem = url_elem.find('sitemap:lastmod', namespaces)
                        if lastmod_elem is not None and lastmod_elem.text:
                            try:
                                # 解析 ISO 8601 日期格式
                                lastmod_str = lastmod_elem.text.strip()
                                if 'T' in lastmod_str:
                                    lastmod = datetime.fromisoformat(lastmod_str.replace('Z', '+00:00'))
                                else:
                                    lastmod = datetime.fromisoformat(lastmod_str)
                            except ValueError:
                                lastmod = None
                        
                        # 創建 DiscoveredURL 模型
                        url_model = ModelFactory.create_discovered_url(
                            url=url,
                            source_sitemap=sitemap_url,
                            priority=priority,
                            changefreq=changefreq,
                            lastmod=lastmod,
                            crawl_status=CrawlStatus.PENDING,
                            metadata={
                                "discovered_from": "sitemap",
                                "sitemap_url": sitemap_url,
                                "discovered_at": datetime.now().isoformat()
                            }
                        )
                        
                        discovered_urls.append(url_model)
                        
                    except Exception as e:
                        logger.warning(f"解析單個 URL 時發生錯誤: {e}")
                        continue
            
            logger.info(f"成功解析 {len(discovered_urls)} 個 URL")
            return discovered_urls
            
        except ET.ParseError as e:
            logger.error(f"XML 解析錯誤: {e}")
            return []
        except Exception as e:
            logger.error(f"解析 Sitemap XML 時發生錯誤: {e}")
            return []
    
    async def _parse_sub_sitemap(self, sub_sitemap_url: str) -> Tuple[bool, List[DiscoveredURLModel]]:
        """
        解析子 sitemap 文件
        """
        try:
            async with self.session.get(sub_sitemap_url) as response:
                if response.status != 200:
                    return False, []
                content = await response.text()
                
            # 解析子 sitemap 內容
            discovered_urls = self._parse_sitemap_xml(content, sub_sitemap_url)
            return True, discovered_urls
            
        except Exception as e:
            logger.warning(f"解析子 sitemap 失敗 {sub_sitemap_url}: {e}")
            return False, []
    
    async def crawl_url(self, url: str) -> Tuple[bool, Optional[ArticleModel]]:
        """
        爬取單個 URL 並創建文章記錄
        
        Args:
            url: 要爬取的 URL
            
        Returns:
            Tuple[bool, Optional[ArticleModel]]: (成功標誌, 文章模型)
        """
        try:
            logger.info(f"開始爬取 URL: {url}")
            
            # 1. 更新爬取狀態
            if self.db:
                # 查找對應的 discovered_url 記錄
                pending_urls = self.db.get_pending_urls(limit=1000)
                url_record = next((u for u in pending_urls if u.url == url), None)
                
                if url_record:
                    self.db.update_crawl_status(url_record.id, CrawlStatus.CRAWLING)
            
            # 2. 下載網頁內容
            async with self.session.get(url) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    if url_record and self.db:
                        self.db.update_crawl_status(url_record.id, CrawlStatus.ERROR, error_msg)
                    logger.error(f"下載網頁失敗: {error_msg}")
                    return False, None
                
                html_content = await response.text()
            
            # 3. 解析網頁內容
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取標題
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # 提取主要內容
            content = ""
            
            # 嘗試不同的內容選擇器
            content_selectors = [
                'main', 'article', '.content', '#content', 
                '.main-content', '.article-content', '.post-content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(separator=' ', strip=True)
                    break
            
            # 如果沒有找到特定容器，提取 body 內容
            if not content:
                body = soup.find('body')
                if body:
                    # 移除不需要的元素
                    for tag in body.find_all(['script', 'style', 'nav', 'header', 'footer']):
                        tag.decompose()
                    content = body.get_text(separator=' ', strip=True)
            
            # 4. 創建文章模型
            article_model = ModelFactory.create_article(
                url=url,
                title=title,
                content=content,
                crawled_from_url_id=url_record.id if url_record else None,
                metadata={
                    "crawled_at": datetime.now().isoformat(),
                    "content_length": len(content),
                    "title_length": len(title)
                }
            )
            
            # 5. 保存文章
            if self.db:
                success = self.db.create_article(article_model)
                if success:
                    # 更新爬取狀態為完成
                    if url_record:
                        self.db.update_crawl_status(url_record.id, CrawlStatus.COMPLETED)
                    
                    self.stats["articles_crawled"] += 1
                    logger.info(f"成功爬取並保存文章: {title}")
                    return True, article_model
                else:
                    if url_record:
                        self.db.update_crawl_status(url_record.id, CrawlStatus.ERROR, "保存文章失敗")
                    return False, None
            
            return True, article_model
            
        except Exception as e:
            logger.error(f"爬取 URL 時發生錯誤 {url}: {e}")
            if url_record and self.db:
                self.db.update_crawl_status(url_record.id, CrawlStatus.ERROR, str(e))
            self.stats["errors"] += 1
            return False, None
    
    async def create_chunks(self, article: ArticleModel, chunk_size: int = 500) -> List[ChunkModel]:
        """
        將文章內容分塊
        
        Args:
            article: 文章模型
            chunk_size: 塊大小（字符數）
            
        Returns:
            List[ChunkModel]: 文章塊列表
        """
        chunks = []
        
        if not article.content:
            return chunks
        
        content = article.content
        content_length = len(content)
        
        # 簡單分塊策略
        for i in range(0, content_length, chunk_size):
            chunk_content = content[i:i + chunk_size]
            
            chunk_model = ModelFactory.create_chunk(
                article_id=article.id,
                content=chunk_content,
                chunk_index=len(chunks),
                metadata={
                    "chunk_method": "simple_split",
                    "chunk_size": chunk_size,
                    "created_at": datetime.now().isoformat()
                }
            )
            
            chunks.append(chunk_model)
        
        # 保存塊
        if chunks and self.db:
            count = self.db.create_chunks(chunks)
            self.stats["chunks_created"] += count
            logger.info(f"為文章 {article.title} 創建了 {count} 個塊")
        
        return chunks
    
    async def crawl_batch(self, urls: List[str], create_chunks: bool = True) -> Dict[str, Any]:
        """
        批量爬取 URL
        
        Args:
            urls: URL 列表
            create_chunks: 是否創建文章塊
            
        Returns:
            Dict[str, Any]: 爬取結果統計
        """
        if not urls:
            return {"success": 0, "failed": 0, "total": 0}
        
        logger.info(f"開始批量爬取 {len(urls)} 個 URL")
        
        # 使用信號量控制並發
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def crawl_with_delay(url):
            async with semaphore:
                # 添加延遲
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                
                success, article = await self.crawl_url(url)
                
                # 創建文章塊
                if success and article and create_chunks:
                    await self.create_chunks(article)
                
                return success
        
        # 執行批量爬取
        tasks = [crawl_with_delay(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 統計結果
        success_count = sum(1 for r in results if r is True)
        failed_count = len(results) - success_count
        
        logger.info(f"批量爬取完成: 成功 {success_count}, 失敗 {failed_count}")
        
        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(urls)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取爬蟲統計信息"""
        stats = self.stats.copy()
        
        # 添加資料庫統計
        if self.db:
            stats["db_counts"] = {
                "sitemaps": self.db.get_table_count("sitemaps"),
                "discovered_urls": self.db.get_table_count("discovered_urls"),
                "articles": self.db.get_table_count("articles"),
                "article_chunks": self.db.get_table_count("article_chunks")
            }
            
            # 獲取爬取進度
            progress = self.db.get_crawl_progress()
            stats["progress"] = progress
        
        return stats

# 便捷函數
async def parse_sitemap_urls(sitemap_urls: List[str]) -> List[DiscoveredURLModel]:
    """
    便捷函數：批量解析多個 Sitemap
    
    Args:
        sitemap_urls: Sitemap URL 列表
        
    Returns:
        List[DiscoveredURLModel]: 所有發現的 URL
    """
    all_urls = []
    
    async with RAGSpider() as spider:
        for sitemap_url in sitemap_urls:
            success, urls = await spider.parse_sitemap(sitemap_url)
            if success:
                all_urls.extend(urls)
    
    return all_urls

async def crawl_pending_urls(limit: int = 100, create_chunks: bool = True) -> Dict[str, Any]:
    """
    便捷函數：爬取待處理的 URL
    
    Args:
        limit: 最大爬取數量
        create_chunks: 是否創建文章塊
        
    Returns:
        Dict[str, Any]: 爬取結果
    """
    db = get_database_operations()
    if not db:
        return {"error": "無法連接資料庫"}
    
    # 獲取待爬取的 URL
    pending_urls = db.get_pending_urls(limit=limit)
    if not pending_urls:
        return {"message": "沒有待爬取的 URL", "total": 0}
    
    urls = [url.url for url in pending_urls]
    
    async with RAGSpider() as spider:
        result = await spider.crawl_batch(urls, create_chunks=create_chunks)
    
    return result


# 工作流程方法
def discover_sitemaps(base_url: str, output_file: str = "sitemaps.txt") -> bool:
    """
    發現並保存網站的sitemap (同時保存到文件和資料庫)
    
    Args:
        base_url: 網站基礎URL 或 robots.txt URL
        output_file: 輸出文件名
        
    Returns:
        是否成功
    """
    try:
        print(f"🔍 正在發現 {base_url} 的 sitemaps...")
        
        sitemap_urls = []
        
        # 如果URL已經指向robots.txt，直接使用
        if base_url.endswith('/robots.txt'):
            robots_url = base_url
            # 從robots.txt URL推導基礎URL
            site_base = base_url.replace('/robots.txt', '')
        else:
            # 否則構建robots.txt URL
            robots_url = urljoin(base_url, "/robots.txt")
            site_base = base_url
        
        print(f"📖 讀取 robots.txt: {robots_url}")
        
        # 嘗試下載和解析robots.txt
        import requests
        try:
            response = requests.get(robots_url, timeout=10)
            if response.status_code == 200:
                robots_content = response.text
                print(f"✅ 成功下載 robots.txt ({len(robots_content)} 字符)")
                
                # 解析robots.txt中的Sitemap條目
                for line in robots_content.split('\n'):
                    line = line.strip()
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        if sitemap_url:
                            sitemap_urls.append(sitemap_url)
                            print(f"🗺️ 在 robots.txt 中發現 sitemap: {sitemap_url}")
                
                if not sitemap_urls:
                    print("⚠️ robots.txt 中沒有找到 sitemap 條目，使用預設位置")
                    # 如果robots.txt中沒有sitemap，使用常見位置
                    sitemap_urls = [
                        urljoin(site_base, "/sitemap.xml"),
                        urljoin(site_base, "/sitemap_index.xml")
                    ]
            else:
                print(f"⚠️ 無法下載 robots.txt (HTTP {response.status_code})，使用預設sitemap位置")
                sitemap_urls = [
                    urljoin(site_base, "/sitemap.xml"),
                    urljoin(site_base, "/sitemap_index.xml")
                ]
        except Exception as e:
            print(f"⚠️ 讀取 robots.txt 失敗: {e}")
            print("使用預設 sitemap 位置")
            sitemap_urls = [
                urljoin(site_base, "/sitemap.xml"),
                urljoin(site_base, "/sitemap_index.xml")
            ]
        
        # 將URLs保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in sitemap_urls:
                f.write(f"{url}\n")
        
        print(f"✅ Sitemap URLs 已保存到 {output_file}")
        
        # 驗證並保存真實存在的sitemap到資料庫
        valid_sitemaps = []
        print("🔍 驗證 sitemap 是否存在...")
        
        import requests
        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    # 檢查是否為有效的 XML sitemap
                    content = response.text.strip()
                    if content and ('<urlset' in content or '<sitemapindex' in content):
                        valid_sitemaps.append(sitemap_url)
                        print(f"✅ 有效的 sitemap: {sitemap_url}")
                    else:
                        print(f"⚠️ 不是有效的 sitemap XML: {sitemap_url}")
                else:
                    print(f"❌ Sitemap 不存在 (HTTP {response.status_code}): {sitemap_url}")
            except Exception as e:
                print(f"❌ 無法訪問 sitemap: {sitemap_url} - {e}")
        
        # 只將驗證過的有效sitemap保存到資料庫
        if valid_sitemaps:
            try:
                from database.client import SupabaseClient
                
                db_client = SupabaseClient()
                admin_client = db_client.get_admin_client()
                
                if admin_client:
                    saved_count = 0
                    
                    for sitemap_url in valid_sitemaps:
                        try:
                            # 檢查是否已存在
                            existing = admin_client.table("sitemaps").select("id").eq("url", sitemap_url).execute()
                            
                            if not existing.data:
                                # 從 URL 中提取 domain
                                parsed_url = urlparse(sitemap_url)
                                domain = parsed_url.netloc
                                
                                # 插入新記錄
                                sitemap_data = {
                                    "url": sitemap_url,
                                    "domain": domain,
                                    "status": "pending",
                                    "metadata": {
                                        "discovered_from": "robots_txt" if base_url.endswith('/robots.txt') else "auto_discovery",
                                        "base_url": base_url,
                                        "verified_at": datetime.now().isoformat(),
                                        "discovered_at": datetime.now().isoformat()
                                    }
                                }
                                
                                result = admin_client.table("sitemaps").insert(sitemap_data).execute()
                                
                                if result.data:
                                    saved_count += 1
                                    print(f"📝 已記錄到資料庫: {sitemap_url}")
                                else:
                                    print(f"⚠️ 記錄失敗: {sitemap_url}")
                            else:
                                print(f"ℹ️ 已存在於資料庫: {sitemap_url}")
                                saved_count += 1
                                
                        except Exception as e:
                            logger.error(f"❌ 保存sitemap到資料庫失敗 {sitemap_url}: {e}")
                            print(f"⚠️ 跳過資料庫記錄: {sitemap_url} - {e}")
                    
                    print(f"💾 資料庫記錄: {saved_count}/{len(valid_sitemaps)} 個有效的 sitemap URLs")
                else:
                    print("⚠️ 無法獲取管理員客戶端，跳過資料庫記錄")
                    
            except Exception as e:
                logger.error(f"❌ 資料庫連接失敗: {e}")
                print("⚠️ 無法連接到資料庫，僅保存到文件")
        else:
            print("⚠️ 沒有找到有效的 sitemap，不記錄到資料庫")
        
        print(f"📝 總共發現 {len(sitemap_urls)} 個潛在的 sitemap URLs")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 發現 sitemap 失敗: {e}")
        print(f"❌ 發現 sitemap 失敗: {e}")
        return False


def extract_urls_from_sitemaps(sitemap_list_file: str, output_file: str = "urls.txt", max_urls: int = 1000) -> bool:
    """
    從sitemap文件列表中提取URLs (同時保存到文件和資料庫)
    
    Args:
        sitemap_list_file: sitemap列表文件
        output_file: 輸出URL文件
        max_urls: 最大URL數量
        
    Returns:
        是否成功
    """
    try:
        print(f"📖 正在讀取 sitemap 列表: {sitemap_list_file}")
        
        # 檢查文件是否存在
        if not os.path.exists(sitemap_list_file):
            print(f"❌ 文件不存在: {sitemap_list_file}")
            return False
        
        # 讀取sitemap列表
        with open(sitemap_list_file, 'r', encoding='utf-8') as f:
            sitemap_urls = [line.strip() for line in f if line.strip()]
        
        print(f"🗺️ 找到 {len(sitemap_urls)} 個 sitemap URLs")
        
        if not sitemap_urls:
            print("⚠️ 沒有找到有效的sitemap URLs")
            return False
        
        # 運行異步函數提取URLs
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            print("🔄 開始解析 sitemaps...")
            discovered_urls = loop.run_until_complete(
                parse_sitemap_urls(sitemap_urls[:3])  # 限制處理數量
            )
            
            print(f"🔗 從 sitemaps 中發現 {len(discovered_urls)} 個 URLs")
            
            # 限制URL數量
            if len(discovered_urls) > max_urls:
                discovered_urls = discovered_urls[:max_urls]
                print(f"⚠️ 限制URL數量為 {max_urls}")
            
            # 保存URLs到文件
            with open(output_file, 'w', encoding='utf-8') as f:
                for url_model in discovered_urls:
                    f.write(f"{url_model.url}\n")
            
            print(f"✅ {len(discovered_urls)} 個 URLs 已保存到文件 {output_file}")
            
            # 檢查資料庫中的記錄狀態
            try:
                from database.client import SupabaseClient
                
                db_client = SupabaseClient()
                
                # 獲取資料庫統計
                discovered_urls_result = db_client.table("discovered_urls").select("id", count="exact").execute()
                db_url_count = discovered_urls_result.count if discovered_urls_result.count is not None else 0
                print(f"💾 資料庫中已有 {db_url_count} 個 discovered URLs 記錄")
                
                # 顯示爬取狀態統計
                try:
                    pending_result = db_client.table("discovered_urls").select("id", count="exact").eq("crawl_status", "pending").execute()
                    pending_count = pending_result.count if pending_result.count is not None else 0
                    completed_count = db_url_count - pending_count
                    print(f"📊 爬取狀態: 待處理 {pending_count} 個, 已完成 {completed_count} 個")
                except Exception as e:
                    print(f"⚠️ 無法獲取爬取狀態: {e}")
                    
            except Exception as e:
                logger.error(f"❌ 資料庫狀態檢查失敗: {e}")
                print("⚠️ 無法連接到資料庫進行狀態檢查")
            
            return True
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"❌ 提取 URLs 失敗: {e}")
        print(f"❌ 提取 URLs 失敗: {e}")
        return False


def crawl_and_chunk_urls(url_list_file: str, chunk_size: int = 200) -> bool:
    """
    爬取URL列表中的網頁並進行分塊
    
    Args:
        url_list_file: URL列表文件
        chunk_size: 分塊大小
        
    Returns:
        是否成功
    """
    try:
        print(f"📄 正在讀取 URL 列表: {url_list_file}")
        
        # 檢查文件是否存在
        if not os.path.exists(url_list_file):
            print(f"❌ 文件不存在: {url_list_file}")
            return False
        
        # 讀取URL列表
        with open(url_list_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        print(f"🔗 找到 {len(urls)} 個 URLs 待爬取")
        
        if not urls:
            print("⚠️ 沒有找到有效的URLs")
            return False
        
        # 限制爬取數量以避免過載
        max_crawl = min(len(urls), 5)  # 限制為5個URL
        urls_to_crawl = urls[:max_crawl]
        
        print(f"🚀 開始爬取前 {max_crawl} 個 URLs...")
        
        # 運行異步爬取
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def run_crawl():
                async with RAGSpider() as spider:
                    return await spider.crawl_batch(urls_to_crawl, create_chunks=True)
            
            results = loop.run_until_complete(run_crawl())
            
            print(f"✅ 爬取完成!")
            print(f"📊 成功: {results.get('success', 0)}, 失敗: {results.get('failed', 0)}")
            print(f"📄 總計: {results.get('total', 0)}")
            
            # 顯示資料庫統計
            try:
                from database.client import SupabaseClient
                
                db_client = SupabaseClient()
                
                # 獲取文章和文章塊統計
                articles_result = db_client.table("articles").select("id", count="exact").execute()
                articles_count = articles_result.count if articles_result.count is not None else 0
                
                chunks_result = db_client.table("article_chunks").select("id", count="exact").execute()
                chunks_count = chunks_result.count if chunks_result.count is not None else 0
                
                print(f"💾 資料庫記錄: {articles_count} 篇文章, {chunks_count} 個文章塊")
                
            except Exception as e:
                logger.error(f"❌ 資料庫統計獲取失敗: {e}")
                print(f"⚠️ 無法獲取資料庫統計: {e}")
            
            return True
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"❌ 爬取和分塊失敗: {e}")
        print(f"❌ 爬取失敗: {e}")
        return False
