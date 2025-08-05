"""
Enhanced RAG Spider - 完全對應 schema.sql 資料庫架構
與 database/models.py 完全整合的穩定爬蟲實作

增強功能：
- 完整的錯誤處理和重試機制
- 連接池和健康檢查  
- 結構化日誌記錄
- 速率限制和反爬蟲對策
- 數據庫事務管理
- 斷線恢復機制
"""

import asyncio
import hashlib
import xml.etree.ElementTree as ET
import os
import json
import time
import signal
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dataclasses import dataclass

from database.models import (
    DiscoveredURLModel, ArticleModel, ChunkModel, SitemapModel,
    CrawlStatus, ChangeFreq, ModelFactory
)

# 導入增強的工具類
from spider.utils.enhanced_logger import get_spider_logger
from spider.utils.connection_manager import EnhancedConnectionManager, ConnectionConfig
from spider.utils.database_manager import EnhancedDatabaseManager, DatabaseConfig
from spider.utils.retry_manager import RetryManager, RetryConfig, RetryReason


@dataclass
class SpiderConfig:
    """爬蟲配置"""
    # 基本設置
    max_concurrent: int = 5
    delay: float = 1.0
    
    # 重試設置
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 超時設置
    request_timeout: float = 30.0
    read_timeout: float = 60.0
    
    # 內容處理
    chunk_size: int = 500
    max_content_length: int = 1024 * 1024  # 1MB
    
    # 速率限制
    requests_per_second: float = 2.0
    burst_requests: int = 5
    
    # 反爬蟲對策
    randomize_delay: bool = True
    use_proxy_rotation: bool = False
    rotate_user_agents: bool = True


class EnhancedRAGSpider:
    """
    增強版 RAG 系統爬蟲 - 完全對應 schema.sql 架構
    
    增強功能：
    - 完整的錯誤處理和重試機制
    - 連接池和健康檢查
    - 結構化日誌記錄
    - 速率限制和反爬蟲對策
    - 數據庫事務管理
    - 斷線恢復機制
    """
    
    def __init__(self, config: Optional[SpiderConfig] = None):
        """
        初始化增強版爬蟲
        
        Args:
            config: 爬蟲配置
        """
        self.config = config or SpiderConfig()
        self.logger = get_spider_logger("enhanced_rag_spider")
        
        # 連接管理器
        self.connection_manager: Optional[EnhancedConnectionManager] = None
        self.database_manager: Optional[EnhancedDatabaseManager] = None
        
        # 狀態管理
        self.is_running = False
        self.is_paused = False
        self._shutdown_event = asyncio.Event()
        
        # 統計信息
        self.stats = {
            "sitemaps_processed": 0,
            "urls_discovered": 0,
            "articles_crawled": 0,
            "chunks_created": 0,
            "errors": 0,
            "retries": 0,
            "start_time": None,
            "processed_urls": set(),  # 避免重複處理
            "failed_urls": set()      # 記錄失敗的URL
        }
        
        # 設置信號處理器
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """設置信號處理器以支持優雅關閉"""
        def signal_handler(signum, frame):
            self.logger.info(f"收到信號 {signum}，準備關閉爬蟲...")
            asyncio.create_task(self.shutdown())
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # 在某些環境中可能無法設置信號處理器
            pass
        
    async def __aenter__(self):
        """異步上下文管理器入口"""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口"""
        await self.shutdown()
    
    async def initialize(self):
        """初始化爬蟲組件"""
        try:
            self.logger.info("🚀 正在初始化增強版 RAG 爬蟲...")
            
            # 創建連接配置
            conn_config = ConnectionConfig(
                timeout=self.config.request_timeout,
                read_timeout=self.config.read_timeout,
                connector_limit=self.config.max_concurrent * 2,
                max_retries=self.config.max_retries,
                retry_delay=self.config.retry_delay,
                requests_per_second=self.config.requests_per_second,
                burst_requests=self.config.burst_requests
            )
            
            # 創建數據庫配置
            db_config = DatabaseConfig(
                max_retries=self.config.max_retries,
                retry_delay=self.config.retry_delay
            )
            
            # 初始化管理器
            self.connection_manager = EnhancedConnectionManager(conn_config)
            self.database_manager = EnhancedDatabaseManager(db_config)
            
            # 啟動管理器
            await self.connection_manager.__aenter__()
            await self.database_manager.__aenter__()
            
            self.is_running = True
            self.stats["start_time"] = time.time()
            
            self.logger.info("✅ 增強版 RAG 爬蟲初始化完成")
            
        except Exception as e:
            self.logger.error(f"❌ 爬蟲初始化失敗: {e}")
            await self.shutdown()
            raise
    
    async def shutdown(self):
        """關閉爬蟲"""
        if not self.is_running:
            return
        
        self.logger.info("🛑 正在關閉增強版 RAG 爬蟲...")
        self.is_running = False
        self._shutdown_event.set()
        
        # 關閉管理器
        if self.connection_manager:
            await self.connection_manager.__aexit__(None, None, None)
        
        if self.database_manager:
            await self.database_manager.__aexit__(None, None, None)
        
        # 記錄最終統計
        self.logger.log_statistics()
        self.logger.info("✅ 增強版 RAG 爬蟲已關閉")
    
    async def pause(self):
        """暫停爬蟲"""
        self.is_paused = True
        self.logger.info("⏸️ 爬蟲已暫停")
    
    async def resume(self):
        """恢復爬蟲"""
        self.is_paused = False
        self.logger.info("▶️ 爬蟲已恢復")
    
    async def _check_pause_and_shutdown(self):
        """檢查暫停和關閉狀態"""
        while self.is_paused and self.is_running:
            await asyncio.sleep(1)
        
        if not self.is_running:
            raise asyncio.CancelledError("爬蟲已關閉")
    
    async def parse_sitemap(self, sitemap_url: str, update_db: bool = True) -> Tuple[bool, List[DiscoveredURLModel]]:
        """
        解析 sitemap 並返回發現的 URL
        
        Args:
            sitemap_url: Sitemap URL
            update_db: 是否更新資料庫中的 sitemap 狀態
            
        Returns:
            Tuple[bool, List[DiscoveredURLModel]]: (成功標誌, URL列表)
        """
        await self._check_pause_and_shutdown()
        
        # 避免重複處理
        if sitemap_url in self.stats["processed_urls"]:
            self.logger.warning(f"⚠️ Sitemap 已處理過，跳過: {sitemap_url}")
            return True, []
        
        try:
            self.logger.info(f"🗺️ 開始解析 Sitemap: {sitemap_url}")
            
            # 記錄請求開始
            request_context = self.logger.log_request_start(sitemap_url, "GET")
            
            # 下載 Sitemap
            async with self.connection_manager.get(sitemap_url) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    self.logger.log_request_error(request_context, Exception(error_msg), response.status)
                    self.stats["errors"] += 1
                    return False, []
                
                content = await response.text()
                
                # 記錄成功
                self.logger.log_request_success(request_context, response.status, len(content))
            
            # 解析 XML
            discovered_urls = self._parse_sitemap_xml(content, sitemap_url)
            
            # 批量插入發現的 URL
            if discovered_urls and self.database_manager:
                count = await self.database_manager.bulk_create_discovered_urls(discovered_urls)
                self.logger.log_sitemap_parsing(sitemap_url, count, True)
            else:
                self.logger.log_sitemap_parsing(sitemap_url, len(discovered_urls), True)
            
            # 標記為已處理
            self.stats["processed_urls"].add(sitemap_url)
            self.stats["sitemaps_processed"] += 1
            self.stats["urls_discovered"] += len(discovered_urls)
            
            return True, discovered_urls
            
        except Exception as e:
            self.logger.log_sitemap_parsing(sitemap_url, 0, False, e)
            self.stats["errors"] += 1
            self.stats["failed_urls"].add(sitemap_url)
            return False, []
    
    def _parse_sitemap_xml(self, xml_content: str, sitemap_url: str) -> List[DiscoveredURLModel]:
        """
        解析 XML 內容並提取 URL 信息
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
                self.logger.info(f"📋 檢測到 sitemap index 格式: {sitemap_url}")
                # 處理 sitemapindex - 提取子 sitemap URLs
                for sitemap_elem in root.findall('.//sitemap:sitemap', namespaces):
                    try:
                        loc_elem = sitemap_elem.find('sitemap:loc', namespaces)
                        if loc_elem is None or not loc_elem.text:
                            continue
                        
                        sub_sitemap_url = loc_elem.text.strip()
                        self.logger.info(f"🔗 發現子 sitemap: {sub_sitemap_url}")
                        
                        # 使用同步方式處理子 sitemap，避免事件循環衝突
                        try:
                            import requests
                            response = requests.get(sub_sitemap_url, timeout=10)
                            if response.status_code == 200:
                                sub_content = response.text
                                sub_urls = self._parse_sitemap_xml(sub_content, sub_sitemap_url)
                                discovered_urls.extend(sub_urls)
                                self.logger.info(f"✅ 從子 sitemap 獲得 {len(sub_urls)} 個 URLs: {sub_sitemap_url}")
                                
                                # 限制處理的子 sitemap 數量，避免過多請求
                                if len(discovered_urls) >= 50:  # 限制總數
                                    self.logger.info(f"⚠️ 已達到 URL 限制，停止處理更多子 sitemap")
                                    break
                            else:
                                self.logger.warning(f"⚠️ 子 sitemap 訪問失敗 (HTTP {response.status_code}): {sub_sitemap_url}")
                        except Exception as e:
                            self.logger.warning(f"⚠️ 處理子 sitemap 異常: {sub_sitemap_url} - {e}")
                            
                    except Exception as e:
                        self.logger.warning(f"解析子 sitemap 元素時發生錯誤: {e}")
                        continue
                        
            else:
                # 處理標準 urlset 格式
                self.logger.info(f"📄 檢測到 urlset 格式: {sitemap_url}")
                
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
                        self.logger.warning(f"解析單個 URL 時發生錯誤: {e}")
                        continue
            
            self.logger.info(f"成功解析 {len(discovered_urls)} 個 URL")
            return discovered_urls
            
        except ET.ParseError as e:
            self.logger.error(f"XML 解析錯誤: {e}")
            return []
        except Exception as e:
            self.logger.error(f"解析 Sitemap XML 時發生錯誤: {e}")
            return []
    
    async def crawl_url(self, url: str) -> Tuple[bool, Optional[ArticleModel]]:
        """
        爬取單個 URL 並創建文章記錄
        
        Args:
            url: 要爬取的 URL
            
        Returns:
            Tuple[bool, Optional[ArticleModel]]: (成功標誌, 文章模型)
        """
        await self._check_pause_and_shutdown()
        
        # 避免重複處理
        if url in self.stats["processed_urls"]:
            self.logger.warning(f"⚠️ URL 已處理過，跳過: {url}")
            return True, None
        
        # 檢查是否在失敗列表中
        if url in self.stats["failed_urls"]:
            self.logger.warning(f"⚠️ URL 之前失敗過，跳過: {url}")
            return False, None
        
        url_record = None
        try:
            self.logger.info(f"🕷️ 開始爬取 URL: {url}")
            
            # 記錄請求開始
            request_context = self.logger.log_request_start(url, "GET")
            
            # 查找對應的 discovered_url 記錄
            if self.database_manager:
                pending_urls = await self.database_manager.get_pending_urls(limit=1000)
                url_record = next((u for u in pending_urls if u.url == url), None)
                
                if url_record:
                    await self.database_manager.safe_update_crawl_status(
                        url_record.id, CrawlStatus.CRAWLING
                    )
            
            # 下載網頁內容
            async with self.connection_manager.get(url) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    if url_record and self.database_manager:
                        await self.database_manager.safe_update_crawl_status(
                            url_record.id, CrawlStatus.ERROR, error_msg
                        )
                    
                    self.logger.log_request_error(
                        request_context, Exception(error_msg), response.status
                    )
                    self.stats["errors"] += 1
                    self.stats["failed_urls"].add(url)
                    return False, None
                
                html_content = await response.text()
                
                # 檢查內容長度限制
                if len(html_content) > self.config.max_content_length:
                    self.logger.warning(f"⚠️ 內容過大，截取前 {self.config.max_content_length} 字符")
                    html_content = html_content[:self.config.max_content_length]
                
                # 記錄成功
                self.logger.log_request_success(request_context, response.status, len(html_content))
            
            # 解析網頁內容
            title, content = self._extract_content(html_content, url)
            
            # 記錄內容提取
            self.logger.log_content_extraction(url, title, len(content), True)
            
            # 創建文章模型
            article_model = ModelFactory.create_article(
                url=url,
                title=title,
                content=content,
                crawled_from_url_id=url_record.id if url_record else None,
                metadata={
                    "crawled_at": datetime.now().isoformat(),
                    "content_length": len(content),
                    "title_length": len(title),
                    "response_status": response.status,
                    "content_type": response.headers.get('content-type', 'unknown')
                }
            )
            
            # 保存文章
            if self.database_manager:
                success = await self.database_manager.create_article(article_model)
                if success:
                    # 更新爬取狀態為完成
                    if url_record:
                        await self.database_manager.safe_update_crawl_status(
                            url_record.id, CrawlStatus.COMPLETED
                        )
                    
                    # 標記為已處理
                    self.stats["processed_urls"].add(url)
                    self.stats["articles_crawled"] += 1
                    self.logger.info(f"✅ 成功爬取並保存文章: {title[:50]}...")
                    return True, article_model
                else:
                    if url_record:
                        await self.database_manager.safe_update_crawl_status(
                            url_record.id, CrawlStatus.ERROR, "保存文章失敗"
                        )
                    self.stats["errors"] += 1
                    self.stats["failed_urls"].add(url)
                    return False, None
            
            # 如果沒有數據庫管理器，仍然標記為成功
            self.stats["processed_urls"].add(url)
            self.stats["articles_crawled"] += 1
            return True, article_model
            
        except Exception as e:
            self.logger.log_content_extraction(url, "", 0, False, e)
            
            if url_record and self.database_manager:
                await self.database_manager.safe_update_crawl_status(
                    url_record.id, CrawlStatus.ERROR, str(e)
                )
            
            self.stats["errors"] += 1
            self.stats["failed_urls"].add(url)
            return False, None
    
    def _extract_content(self, html_content: str, url: str) -> Tuple[str, str]:
        """
        從 HTML 內容中提取標題和正文
        
        Args:
            html_content: HTML 內容
            url: URL（用於生成默認標題）
            
        Returns:
            Tuple[str, str]: (標題, 內容)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取標題
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # 如果沒有標題，使用 URL 生成
            if not title:
                parsed_url = urlparse(url)
                title = f"Page from {parsed_url.netloc}"
            
            # 提取主要內容
            content = ""
            
            # 嘗試不同的內容選擇器（按優先級排序）
            content_selectors = [
                'main article',
                'main',
                'article',
                '.content',
                '#content', 
                '.main-content',
                '.article-content',
                '.post-content',
                '.entry-content',
                '[role="main"]'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(separator=' ', strip=True)
                    if len(content) > 100:  # 確保有足夠的內容
                        break
            
            # 如果沒有找到特定容器或內容太少，提取 body 內容
            if not content or len(content) < 100:
                body = soup.find('body')
                if body:
                    # 移除不需要的元素
                    for tag in body.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                        tag.decompose()
                    content = body.get_text(separator=' ', strip=True)
            
            # 清理內容
            content = self._clean_content(content)
            
            return title, content
            
        except Exception as e:
            self.logger.error(f"內容提取失敗: {e}")
            return "提取失敗", ""
    
    def _clean_content(self, content: str) -> str:
        """
        清理提取的內容
        
        Args:
            content: 原始內容
            
        Returns:
            str: 清理後的內容
        """
        if not content:
            return ""
        
        # 移除多餘的空白字符
        import re
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        
        # 限制內容長度
        if len(content) > self.config.max_content_length:
            content = content[:self.config.max_content_length]
        
        return content
    
    async def create_chunks(self, article: ArticleModel, chunk_size: int = None) -> List[ChunkModel]:
        """
        將文章內容分塊
        
        Args:
            article: 文章模型
            chunk_size: 塊大小（字符數），如果為None則使用配置中的默認值
            
        Returns:
            List[ChunkModel]: 文章塊列表
        """
        chunks = []
        
        if not article.content:
            return chunks
        
        chunk_size = chunk_size or self.config.chunk_size
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
        if chunks and self.database_manager:
            count = await self.database_manager.create_chunks(chunks)
            self.stats["chunks_created"] += count
            self.logger.log_chunking(article.url, count, "simple_split")
        
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
        
        self.logger.info(f"🚀 開始批量爬取 {len(urls)} 個 URL")
        
        # 使用信號量控制並發
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def crawl_with_delay(url):
            async with semaphore:
                # 檢查暫停和關閉狀態
                await self._check_pause_and_shutdown()
                
                # 添加延遲
                if self.config.delay > 0:
                    await asyncio.sleep(self.config.delay)
                
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
        
        self.logger.info(f"✅ 批量爬取完成: 成功 {success_count}, 失敗 {failed_count}")
        
        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(urls)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取爬蟲統計信息"""
        stats = self.stats.copy()
        
        # 添加運行時間
        if self.stats["start_time"]:
            stats["runtime"] = time.time() - self.stats["start_time"]
        
        # 添加連接管理器統計
        if self.connection_manager:
            stats["connection_stats"] = self.connection_manager.get_stats()
        
        # 添加數據庫統計
        if self.database_manager:
            db_stats = asyncio.run(self.database_manager.get_stats())
            stats["database_stats"] = db_stats
        
        return stats


# 便捷函數（為了向後兼容）
async def parse_sitemap_urls(sitemap_urls: List[str]) -> List[DiscoveredURLModel]:
    """
    便捷函數：批量解析多個 Sitemap
    
    Args:
        sitemap_urls: Sitemap URL 列表
        
    Returns:
        List[DiscoveredURLModel]: 所有發現的 URL
    """
    all_urls = []
    
    async with EnhancedRAGSpider() as spider:
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
    async with EnhancedRAGSpider() as spider:
        if not spider.database_manager:
            return {"error": "無法連接資料庫"}
        
        # 獲取待爬取的 URL
        pending_urls = await spider.database_manager.get_pending_urls(limit=limit)
        if not pending_urls:
            return {"message": "沒有待爬取的 URL", "total": 0}
        
        urls = [url.url for url in pending_urls]
        result = await spider.crawl_batch(urls, create_chunks=create_chunks)
    
    return result


# 保持向後兼容性，創建一個別名
RAGSpider = EnhancedRAGSpider


# 工作流程方法（保持不變，但使用 self.logger 代替 logger）
def discover_sitemaps(base_url: str, output_file: str = "sitemaps.txt") -> bool:
    """
    發現並保存網站的sitemap (同時保存到文件和資料庫)
    
    Args:
        base_url: 網站基礎URL 或 robots.txt URL
        output_file: 輸出文件名
        
    Returns:
        是否成功
    """
    logger = get_spider_logger("discover_sitemaps")
    
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
        print(f"📝 總共發現 {len(sitemap_urls)} 個潛在的 sitemap URLs")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 發現 sitemap 失敗: {e}")
        print(f"❌ 發現 sitemap 失敗: {e}")
        return False
