"""
Sitemap 爬蟲模組

功能:
- 繼承自 BaseCrawler。
- 解析 sitemap.xml 和 sitemap.xml.gz 檔案。
- 遞歸處理 sitemap 索引檔案 (sitemap index files)。
- 提取 URL 及其元數據 (lastmod, changefreq, priority)。
- 使用生成器 (yield) 逐一返回解析到的 URL 條目，以節省內存。
"""

import logging
import gzip
import xml.etree.ElementTree as ET
from typing import Iterator, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from .base_crawler import BaseCrawler

# 設置日誌
logger = logging.getLogger(__name__)

@dataclass
class SitemapEntry:
    """Sitemap 中的一個 URL 條目"""
    url: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None
    # source 用於追蹤該條目是從哪個 sitemap 文件解析出來的
    source_sitemap: str = field(default="", repr=False)

class SitemapCrawler(BaseCrawler):
    """
    遞歸解析 Sitemap 檔案並提取 URL。
    """

    def __init__(self, *args, **kwargs):
        """
        初始化 SitemapCrawler。
        """
        super().__init__(*args, **kwargs)
        self.processed_sitemaps = set()
        # XML Namespace for sitemaps
        self.namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

    def crawl_sitemap(self, sitemap_url: str) -> Iterator[SitemapEntry]:
        """
        遞歸爬取並解析 sitemap，使用生成器返回結果。

        Args:
            sitemap_url (str): 起始 sitemap 的 URL。

        Yields:
            Iterator[SitemapEntry]: 解析出的 SitemapEntry 物件。
        """
        if sitemap_url in self.processed_sitemaps:
            logger.debug(f"Sitemap 已處理，跳過: {sitemap_url}")
            return

        self.processed_sitemaps.add(sitemap_url)
        logger.info(f"正在處理 Sitemap: {sitemap_url}")

        content = self._fetch_content(sitemap_url)
        if not content:
            return

        try:
            root = ET.fromstring(content)
            sitemap_type = self._detect_sitemap_type(root)

            if sitemap_type == 'index':
                child_sitemaps = self._extract_sitemap_urls(root)
                logger.info(f"發現 {len(child_sitemaps)} 個子 sitemaps 於 {sitemap_url}")
                for child_url in child_sitemaps:
                    # 遞歸調用，並將子生成器的結果 yield 出去
                    yield from self.crawl_sitemap(child_url)

            elif sitemap_type == 'urlset':
                page_entries = self._extract_page_urls(root, sitemap_url)
                logger.info(f"從 {sitemap_url} 提取了 {len(page_entries)} 個頁面 URL")
                for entry in page_entries:
                    yield entry
            else:
                logger.warning(f"未知的 sitemap 類型或格式錯誤於: {sitemap_url}")

        except ET.ParseError as e:
            logger.error(f"解析 XML 時發生錯誤: {sitemap_url}, 錯誤: {e}")
        except Exception as e:
            logger.error(f"處理 sitemap 時發生未知錯誤: {sitemap_url}, 錯誤: {e}")

    def _fetch_content(self, url: str) -> Optional[bytes]:
        """
        獲取並可能解壓 sitemap 內容。
        """
        response_bytes = self.get_binary_content(url)
        if not response_bytes:
            return None

        if url.endswith('.gz'):
            try:
                return gzip.decompress(response_bytes)
            except gzip.BadGzipFile as e:
                logger.error(f"解壓 Gzip 檔案失敗: {url}, 錯誤: {e}")
                return None
        
        return response_bytes

    def _detect_sitemap_type(self, root: ET.Element) -> str:
        """
        從 XML 的根元素檢測 sitemap 類型。
        """
        if root.tag.endswith('sitemapindex'):
            return "index"
        elif root.tag.endswith('urlset'):
            return "urlset"
        return "unknown"

    def _extract_sitemap_urls(self, root: ET.Element) -> list[str]:
        """
        從 sitemap index 中提取 sitemap URLs。
        """
        urls = []
        for sitemap_elem in root.findall('sm:sitemap', self.namespace):
            loc_elem = sitemap_elem.find('sm:loc', self.namespace)
            if loc_elem is not None and loc_elem.text:
                urls.append(loc_elem.text.strip())
        return urls

    def _extract_page_urls(self, root: ET.Element, source_sitemap: str) -> list[SitemapEntry]:
        """
        從 sitemap 中提取頁面 URLs。
        """
        entries = []
        for url_elem in root.findall('sm:url', self.namespace):
            loc_elem = url_elem.find('sm:loc', self.namespace)
            if loc_elem is not None and loc_elem.text:
                url = loc_elem.text.strip()
                entry = SitemapEntry(url=url, source_sitemap=source_sitemap)

                lastmod_elem = url_elem.find('sm:lastmod', self.namespace)
                if lastmod_elem is not None and lastmod_elem.text:
                    try:
                        entry.lastmod = datetime.fromisoformat(lastmod_elem.text.strip().replace('Z', '+00:00'))
                    except ValueError:
                        logger.debug(f"無法解析的 lastmod 格式: {lastmod_elem.text}")

                changefreq_elem = url_elem.find('sm:changefreq', self.namespace)
                if changefreq_elem is not None and changefreq_elem.text:
                    entry.changefreq = changefreq_elem.text.strip()

                priority_elem = url_elem.find('sm:priority', self.namespace)
                if priority_elem is not None and priority_elem.text:
                    try:
                        entry.priority = float(priority_elem.text)
                    except ValueError:
                        logger.debug(f"無法解析的 priority 格式: {priority_elem.text}")
                
                entries.append(entry)
        return entries
