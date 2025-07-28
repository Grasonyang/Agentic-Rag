"""
網站地圖解析器
解析和處理 sitemap.xml 文件
"""

import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
from dataclasses import dataclass

from ..utils.retry_manager import RetryManager, RetryConfig
from ..utils.rate_limiter import RateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)

@dataclass
class SitemapEntry:
    """站點地圖條目"""
    url: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None

class SitemapParser:
    """站點地圖解析器"""
    
    def __init__(self, retry_config: RetryConfig = None, rate_config: RateLimitConfig = None):
        """
        初始化站點地圖解析器
        
        Args:
            retry_config: 重試配置
            rate_config: 速率限制配置
        """
        self.retry_manager = RetryManager(retry_config)
        self.rate_limiter = RateLimiter(rate_config)
        self.processed_sitemaps: Set[str] = set()
        
    def detect_sitemap_type(self, xml_text: str) -> str:
        """
        檢測 sitemap 類型
        
        Args:
            xml_text: XML 文本
            
        Returns:
            str: 'index', 'urlset', 或 'unknown'
        """
        try:
            root = ET.fromstring(xml_text)
            tag = root.tag.lower()
            
            if tag.endswith("sitemapindex"):
                return "index"
            elif tag.endswith("urlset"):
                return "urlset"
            else:
                return "unknown"
        except ET.ParseError as e:
            logger.error(f"XML 解析錯誤: {e}")
            return "unknown"
        except Exception as e:
            logger.error(f"檢測 sitemap 類型時發生錯誤: {e}")
            return "unknown"
    
    def _extract_sitemap_urls(self, xml_text: str) -> List[str]:
        """
        從 sitemap index 中提取 sitemap URLs
        
        Args:
            xml_text: XML 文本
            
        Returns:
            List[str]: sitemap URLs
        """
        try:
            root = ET.fromstring(xml_text)
            urls = []
            
            for sitemap in root.findall(".//{*}sitemap"):
                loc_elem = sitemap.find("{*}loc")
                if loc_elem is not None and loc_elem.text:
                    urls.append(loc_elem.text.strip())
            
            return urls
        except Exception as e:
            logger.error(f"提取 sitemap URLs 時發生錯誤: {e}")
            return []
    
    def _extract_page_urls(self, xml_text: str) -> List[SitemapEntry]:
        """
        從 sitemap 中提取頁面 URLs
        
        Args:
            xml_text: XML 文本
            
        Returns:
            List[SitemapEntry]: 頁面條目列表
        """
        try:
            root = ET.fromstring(xml_text)
            entries = []
            
            for url_elem in root.findall(".//{*}url"):
                loc_elem = url_elem.find("{*}loc")
                if loc_elem is not None and loc_elem.text:
                    entry = SitemapEntry(url=loc_elem.text.strip())
                    
                    # 提取可選字段
                    lastmod_elem = url_elem.find("{*}lastmod")
                    if lastmod_elem is not None and lastmod_elem.text:
                        try:
                            entry.lastmod = datetime.fromisoformat(
                                lastmod_elem.text.replace('Z', '+00:00')
                            )
                        except ValueError:
                            pass
                    
                    changefreq_elem = url_elem.find("{*}changefreq")
                    if changefreq_elem is not None and changefreq_elem.text:
                        entry.changefreq = changefreq_elem.text.strip()
                    
                    priority_elem = url_elem.find("{*}priority")
                    if priority_elem is not None and priority_elem.text:
                        try:
                            entry.priority = float(priority_elem.text)
                        except ValueError:
                            pass
                    
                    entries.append(entry)
            
            return entries
        except Exception as e:
            logger.error(f"提取頁面 URLs 時發生錯誤: {e}")
            return []
    
    async def _fetch_sitemap(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """
        獲取 sitemap 內容
        
        Args:
            session: HTTP 會話
            url: sitemap URL
            
        Returns:
            Optional[str]: XML 內容，失敗時返回 None
        """
        domain = urlparse(url).netloc
        
        try:
            # 應用速率限制
            await self.rate_limiter.acquire_async(domain)
            
            # 重試機制包裹的請求
            async def fetch():
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        content = await response.text()
                        self.rate_limiter.report_success(domain)
                        return content
                    else:
                        self.rate_limiter.report_failure(domain)
                        raise aiohttp.ClientError(f"HTTP {response.status}")
            
            # 直接調用異步函數，不使用 retry_with_backoff（它是為同步函數設計的）
            return await fetch()
            
        except Exception as e:
            logger.error(f"獲取 sitemap 失敗 {url}: {e}")
            self.rate_limiter.report_failure(domain, severe=True)
            return None
    
    async def parse_sitemap_recursive(self, session: aiohttp.ClientSession, 
                                     sitemap_url: str, 
                                     collected_entries: List[SitemapEntry],
                                     max_depth: int = 10,
                                     current_depth: int = 0) -> None:
        """
        遞歸解析 sitemap
        
        Args:
            session: HTTP 會話
            sitemap_url: sitemap URL
            collected_entries: 收集的條目列表
            max_depth: 最大遞歸深度
            current_depth: 當前遞歸深度
        """
        if current_depth >= max_depth:
            logger.warning(f"達到最大遞歸深度 {max_depth}，停止解析 {sitemap_url}")
            return
        
        if sitemap_url in self.processed_sitemaps:
            logger.debug(f"Sitemap 已處理，跳過: {sitemap_url}")
            return
        
        self.processed_sitemaps.add(sitemap_url)
        logger.info(f"解析 sitemap: {sitemap_url} (深度: {current_depth})")
        
        xml_content = await self._fetch_sitemap(session, sitemap_url)
        if not xml_content:
            return
        
        sitemap_type = self.detect_sitemap_type(xml_content)
        
        if sitemap_type == "index":
            # 這是一個 sitemap index，遞歸處理子 sitemaps
            child_sitemaps = self._extract_sitemap_urls(xml_content)
            logger.info(f"發現 {len(child_sitemaps)} 個子 sitemaps")
            
            # 並行處理子 sitemaps（限制並發數）
            semaphore = asyncio.Semaphore(5)  # 最多同時處理5個
            
            async def process_child_sitemap(child_url):
                async with semaphore:
                    await self.parse_sitemap_recursive(
                        session, child_url, collected_entries, 
                        max_depth, current_depth + 1
                    )
            
            tasks = [process_child_sitemap(child_url) for child_url in child_sitemaps]
            await asyncio.gather(*tasks, return_exceptions=True)
            
        elif sitemap_type == "urlset":
            # 這是一個頁面 sitemap，提取 URLs
            entries = self._extract_page_urls(xml_content)
            collected_entries.extend(entries)
            logger.info(f"提取了 {len(entries)} 個頁面 URLs")
            
        else:
            logger.warning(f"未知的 sitemap 類型: {sitemap_url}")
    
    async def parse_sitemaps(self, sitemap_urls: List[str], 
                           max_depth: int = 10) -> List[SitemapEntry]:
        """
        解析多個 sitemaps
        
        Args:
            sitemap_urls: sitemap URLs 列表
            max_depth: 最大遞歸深度
            
        Returns:
            List[SitemapEntry]: 收集的所有條目
        """
        collected_entries = []
        
        connector = aiohttp.TCPConnector(limit=20, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=300)  # 5分鐘總超時
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SitemapBot/1.0)",
                "Accept": "application/xml,text/xml,*/*"
            }
        ) as session:
            
            tasks = []
            for sitemap_url in sitemap_urls:
                task = self.parse_sitemap_recursive(
                    session, sitemap_url, collected_entries, max_depth
                )
                tasks.append(task)
            
            # 等待所有任務完成
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # 去重
        seen_urls = set()
        unique_entries = []
        for entry in collected_entries:
            if entry.url not in seen_urls:
                seen_urls.add(entry.url)
                unique_entries.append(entry)
        
        logger.info(f"總共收集了 {len(unique_entries)} 個唯一頁面")
        return unique_entries
    
    def filter_entries(self, entries: List[SitemapEntry], 
                      include_patterns: List[str] = None,
                      exclude_patterns: List[str] = None,
                      min_priority: float = None,
                      since_date: datetime = None) -> List[SitemapEntry]:
        """
        根據條件過濾條目
        
        Args:
            entries: 條目列表
            include_patterns: 包含模式列表
            exclude_patterns: 排除模式列表
            min_priority: 最小優先級
            since_date: 最早修改日期
            
        Returns:
            List[SitemapEntry]: 過濾後的條目
        """
        filtered_entries = []
        
        for entry in entries:
            # 檢查包含模式
            if include_patterns:
                if not any(pattern in entry.url for pattern in include_patterns):
                    continue
            
            # 檢查排除模式
            if exclude_patterns:
                if any(pattern in entry.url for pattern in exclude_patterns):
                    continue
            
            # 檢查優先級
            if min_priority is not None and entry.priority is not None:
                if entry.priority < min_priority:
                    continue
            
            # 檢查修改日期
            if since_date is not None and entry.lastmod is not None:
                if entry.lastmod < since_date:
                    continue
            
            filtered_entries.append(entry)
        
        logger.info(f"過濾後剩餘 {len(filtered_entries)} 個條目")
        return filtered_entries
    
    def get_stats(self) -> Dict[str, any]:
        """
        獲取解析統計信息
        
        Returns:
            Dict[str, any]: 統計信息
        """
        return {
            "processed_sitemaps": len(self.processed_sitemaps),
            "retry_stats": self.retry_manager.get_retry_stats(),
            "rate_limiter_stats": self.rate_limiter.get_domain_stats()
        }
    
    def reset(self):
        """重置解析器狀態"""
        self.processed_sitemaps.clear()
        self.retry_manager.reset_stats()

# 便捷函數
async def parse_sitemap(sitemap_url: str, **kwargs) -> List[str]:
    """
    便捷函數：解析單個 sitemap 並返回 URL 列表
    
    Args:
        sitemap_url: sitemap URL
        **kwargs: 其他參數
        
    Returns:
        List[str]: URL 列表
    """
    parser = SitemapParser()
    entries = await parser.parse_sitemaps([sitemap_url], **kwargs)
    return [entry.url for entry in entries]
