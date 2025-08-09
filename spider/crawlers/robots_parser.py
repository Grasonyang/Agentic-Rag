"""
Robots.txt 解析器

功能:
- 繼承自 BaseCrawler。
- 下載並解析網站的 robots.txt 檔案。
- 提取允許 (Allow) 和禁止 (Disallow) 的路徑規則。
- 提取在 robots.txt 中聲明的 Sitemap URL。
- 提供一個方法來檢查特定 URL 是否允許被爬取。
"""

import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from .base_crawler import BaseCrawler

# 設置日誌
logger = logging.getLogger(__name__)

class RobotsParser(BaseCrawler):
    """
    用於解析 robots.txt 檔案的類別。
    """

    def __init__(self, *args, **kwargs):
        """
        初始化 RobotsParser。
        """
        super().__init__(*args, **kwargs)
        self.parser = RobotFileParser()
        self.sitemaps: List[str] = []

    def parse(self, domain_url: str) -> bool:
        """
        解析指定域名的 robots.txt 檔案。

        Args:
            domain_url (str): 網站的根 URL (例如: https://www.example.com)。

        Returns:
            bool: 如果成功解析返回 True，否則返回 False。
        """
        robots_url = urljoin(domain_url, 'robots.txt')
        logger.info(f"正在解析 robots.txt: {robots_url}")
        
        content = self.get_content(robots_url)
        if not content:
            logger.warning(f"無法獲取 robots.txt 內容或檔案不存在: {robots_url}")
            return False

        try:
            self.parser.parse(content.splitlines())
            # RobotFileParser 沒有直接提供獲取 sitemaps 的標準方法，需要手動解析
            self._extract_sitemaps(content)
            logger.info(f"成功解析 robots.txt: {robots_url}")
            if self.sitemaps:
                logger.info(f"在 robots.txt 中找到 Sitemaps: {self.sitemaps}")
            return True
        except Exception as e:
            logger.error(f"解析 robots.txt 時發生錯誤: {robots_url}, 錯誤: {e}")
            return False

    def _extract_sitemaps(self, content: str):
        """
        從 robots.txt 內容中手動提取 Sitemap 指令。

        Args:
            content (str): robots.txt 的檔案內容。
        """
        self.sitemaps = []
        for line in content.splitlines():
            if line.strip().lower().startswith('sitemap:'):
                try:
                    sitemap_url = line.split(':', 1)[1].strip()
                    self.sitemaps.append(sitemap_url)
                except IndexError:
                    logger.warning(f"發現格式不正確的 Sitemap 行: {line}")

    def get_sitemaps(self) -> List[str]:
        """
        返回在 robots.txt 中找到的 Sitemap URL 列表。

        Returns:
            List[str]: Sitemap URL 列表。
        """
        return self.sitemaps

    def can_fetch(self, url: str) -> bool:
        """
        檢查指定的 URL 是否允許被當前的 User-Agent 爬取。

        Args:
            url (str): 要檢查的 URL。

        Returns:
            bool: 如果允許爬取返回 True，否則返回 False。
        """
        if not self.parser.allow_all:
            return self.parser.can_fetch(self.user_agent, url)
        # 如果 allow_all 為 True，can_fetch 可能會誤判，這裡做個修正
        # 實際上 RobotFileParser 的 can_fetch 已經處理了這個邏輯
        return self.parser.can_fetch(self.user_agent, url)

    def get_crawl_delay(self) -> Optional[float]:
        """
        獲取爬取延遲時間 (秒)。

        Returns:
            Optional[float]: 爬取延遲時間，如果未指定則返回 None。
        """
        return self.parser.crawl_delay(self.user_agent)

