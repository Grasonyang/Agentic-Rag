"""
修正版的 sitemap 解析器
修復 async/await 問題
"""

import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SitemapEntry:
    """站點地圖條目"""
    url: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None

class FixedSitemapParser:
    """修正版站點地圖解析器"""
    
    def __init__(self):
        self.processed_sitemaps = set()
    
    def detect_sitemap_type(self, xml_text: str) -> str:
        """
        檢測 sitemap 類型
        
        Args:
            xml_text: XML 文本
            
        Returns:
            str: sitemap 類型 ("index", "urlset", "unknown")
        """
        try:
            root = ET.fromstring(xml_text)
            
            if root.tag.endswith('sitemapindex'):
                return "index"
            elif root.tag.endswith('urlset'):
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
        """從 sitemap index 中提取 sitemap URLs"""
        try:
            root = ET.fromstring(xml_text)
            urls = []
            
            for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())
            
            return urls
        except Exception as e:
            logger.error(f"提取 sitemap URLs 時發生錯誤: {e}")
            return []
    
    def _extract_page_urls(self, xml_text: str) -> List[SitemapEntry]:
        """從 sitemap 中提取頁面 URLs"""
        try:
            root = ET.fromstring(xml_text)
            entries = []
            
            for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None and loc.text:
                    url = loc.text.strip()
                    
                    # 提取其他屬性
                    lastmod = None
                    lastmod_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
                    if lastmod_elem is not None and lastmod_elem.text:
                        try:
                            lastmod = datetime.fromisoformat(lastmod_elem.text.replace('Z', '+00:00'))
                        except:
                            pass
                    
                    changefreq = None
                    changefreq_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq')
                    if changefreq_elem is not None:
                        changefreq = changefreq_elem.text
                    
                    priority = None
                    priority_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}priority')
                    if priority_elem is not None and priority_elem.text:
                        try:
                            priority = float(priority_elem.text)
                        except:
                            pass
                    
                    entries.append(SitemapEntry(
                        url=url,
                        lastmod=lastmod,
                        changefreq=changefreq,
                        priority=priority
                    ))
            
            return entries
        except Exception as e:
            logger.error(f"提取頁面 URLs 時發生錯誤: {e}")
            return []
    
    async def _fetch_sitemap(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """簡化版獲取 sitemap 內容"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"獲取 sitemap 失敗 {url}: {e}")
            return None
    
    async def parse_sitemap_recursive(self, session: aiohttp.ClientSession, 
                                     sitemap_url: str, 
                                     collected_entries: List[SitemapEntry],
                                     max_depth: int = 10,
                                     current_depth: int = 0) -> None:
        """遞歸解析 sitemap"""
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
            semaphore = asyncio.Semaphore(3)  # 限制併發數
            
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
        """解析多個 sitemaps"""
        collected_entries = []
        
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=3)
        timeout = aiohttp.ClientTimeout(total=300)
        
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

# 便捷函數
async def parse_sitemap(sitemap_url: str, **kwargs) -> List[str]:
    """便捷函數：解析單個 sitemap 並返回 URL 列表"""
    parser = FixedSitemapParser()
    entries = await parser.parse_sitemaps([sitemap_url], **kwargs)
    return [entry.url for entry in entries]
