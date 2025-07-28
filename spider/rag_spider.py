"""
RAG Spider - 完全對應 schema.sql 資料庫架構
與 database/models.py 完全整合的爬蟲實作
"""

import asyncio
import aiohttp
import logging
import hashlib
import xml.etree.ElementTree as ET
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

    async def parse_sitemap(self, sitemap_url: str) -> Tuple[bool, List[DiscoveredURLModel]]:
        """
        解析 sitemap 並返回發現的 URL
        完全對應 discovered_urls 表格架構
        
        Args:
            sitemap_url: Sitemap URL
            
        Returns:
            Tuple[bool, List[DiscoveredURLModel]]: (成功標誌, URL列表)
        """
        try:
            logger.info(f"開始解析 Sitemap: {sitemap_url}")
            
            # 1. 創建 Sitemap 記錄
            sitemap_model = ModelFactory.create_sitemap(
                url=sitemap_url,
                status=CrawlStatus.CRAWLING
            )
            
            if self.db:
                self.db.create_sitemap(sitemap_model)
            
            # 2. 下載 Sitemap
            async with self.session.get(sitemap_url) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    if self.db:
                        self.db.update_sitemap_status(sitemap_model.id, CrawlStatus.ERROR, error_message=error_msg)
                    logger.error(f"下載 Sitemap 失敗: {error_msg}")
                    return False, []
                    
                content = await response.text()
                
            # 3. 解析 XML
            discovered_urls = self._parse_sitemap_xml(content, sitemap_url)
            
            # 4. 批量插入發現的 URL
            if discovered_urls and self.db:
                count = self.db.bulk_create_discovered_urls(discovered_urls)
                logger.info(f"從 Sitemap 發現 {len(discovered_urls)} 個 URL，成功插入 {count} 個")
                
                # 更新 Sitemap 狀態
                self.db.update_sitemap_status(
                    sitemap_model.id, 
                    CrawlStatus.COMPLETED, 
                    urls_count=count
                )
            
            self.stats["sitemaps_processed"] += 1
            self.stats["urls_discovered"] += len(discovered_urls)
            
            return True, discovered_urls
            
        except Exception as e:
            logger.error(f"解析 Sitemap 時發生錯誤 {sitemap_url}: {e}")
            if self.db:
                self.db.update_sitemap_status(sitemap_model.id, CrawlStatus.ERROR, error_message=str(e))
            self.stats["errors"] += 1
            return False, []
    
    def _parse_sitemap_xml(self, xml_content: str, sitemap_url: str) -> List[DiscoveredURLModel]:
        """
        解析 XML 內容並提取 URL 信息
        完全對應 discovered_urls 表格的所有欄位
        """
        discovered_urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # 定義 XML 命名空間
            namespaces = {
                'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
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
