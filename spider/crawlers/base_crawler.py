"""基底爬蟲，提供連線管理、robots 檢查與錯誤處理"""

from typing import Dict, Optional
from spider.utils.connection_manager import EnhancedConnectionManager
from .robots_handler import is_allowed, apply_to_crawl4ai


class BaseCrawler:
    """封裝共用爬蟲邏輯的基底類別"""

    def __init__(self, connection_manager: Optional[EnhancedConnectionManager] = None) -> None:
        # 若外部未提供連線管理器，則自行建立
        self.connection_manager = connection_manager or EnhancedConnectionManager()

    async def fetch_html(self, url: str, **kwargs) -> Dict[str, str]:
        """下載網頁內容並自動檢查 robots"""
        try:
            if not await is_allowed(url, self.connection_manager):
                return {"success": False, "error": f"被 robots.txt 禁止: {url}"}
            response = await self.connection_manager.get(url, **kwargs)
            html = await response.text()
            return {"success": True, "html": html}
        except Exception as e:  # noqa: BLE001
            return self._error(e)

    def apply_robots(self, session):
        """將 robots 檢查套用至 crawl4ai 工作階段"""
        return apply_to_crawl4ai(session, self.connection_manager)

    def _error(self, e: Exception) -> Dict[str, str]:
        """統一錯誤回傳格式"""
        return {"success": False, "error": str(e)}
