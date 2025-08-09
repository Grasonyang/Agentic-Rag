"""
通用網頁爬蟲模組

功能:
- 繼承自 BaseCrawler。
- 抓取指定 URL 的 HTML 內容。
- 使用 BeautifulSoup 解析 HTML，提取主要內容和標題。
- 提取頁面上的所有合法鏈接，用於進一步的爬取發現。
- 返回一個結構化的數據對象 (CrawlResult)。
"""

import logging
from typing import List, Optional, Set
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from .base_crawler import BaseCrawler

# 設置日誌
logger = logging.getLogger(__name__)

@dataclass
class CrawlResult:
    """單個頁面的爬取結果"""
    url: str
    title: str
    content: str
    links: Set[str] = field(default_factory=set)
    error: Optional[str] = None

class WebCrawler(BaseCrawler):
    """
    通用網頁爬蟲，用於提取網頁內容和鏈接。
    """

    def crawl(self, url: str) -> CrawlResult:
        """
        爬取單個 URL，提取其內容和鏈接。

        Args:
            url (str): 要爬取的 URL。

        Returns:
            CrawlResult: 包含結果的數據對象。
        """
        logger.info(f"開始爬取網頁: {url}")
        html_content = self.get_content(url)

        if not html_content:
            error_message = f"無法獲取網頁內容: {url}"
            logger.error(error_message)
            return CrawlResult(url=url, title="", content="", error=error_message)

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 提取標題
            title = soup.title.string.strip() if soup.title else ""

            # 提取主要內容 (這是一個基礎實現，可以根據需要進行優化)
            # 移除腳本和樣式標籤
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            
            # 嘗試找到主要內容區域
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            content_text = main_content.get_text(separator='\n', strip=True) if main_content else ""

            # 提取並過濾鏈接
            links = self._extract_links(soup, url)

            logger.info(f"成功爬取並解析網頁: {url}")
            return CrawlResult(url=url, title=title, content=content_text, links=links)

        except Exception as e:
            error_message = f"解析 HTML 時發生錯誤: {url}, 錯誤: {e}"
            logger.error(error_message, exc_info=True)
            return CrawlResult(url=url, title="", content="", error=error_message)

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """
        從 BeautifulSoup 物件中提取所有合法的、完整的鏈接。
        """
        links = set()
        base_domain = urlparse(base_url).netloc

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
                continue

            # 將相對路徑轉換為絕對路徑
            full_url = urljoin(base_url, href)
            
            # 清理 URL，去除 fragment
            parsed_url = urlparse(full_url)
            cleaned_url = parsed_url._replace(fragment="").geturl()

            # 僅保留相同域名下的鏈接 (可選，根據策略調整)
            if urlparse(cleaned_url).netloc == base_domain:
                links.add(cleaned_url)
        
        return links