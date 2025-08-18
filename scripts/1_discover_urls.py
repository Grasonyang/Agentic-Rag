"""腳本一: URL 發現 (Discover URLs)

此腳本解析指定網域的 sitemap，並將發現的頁面 URL
串流寫入 URLScheduler。使用方式:
python -m scripts.1_discover_urls --domains https://www.example.com
"""

import argparse
import asyncio
import sys
import os

# 調整匯入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import load_config
from spider.crawlers.sitemap_parser import SitemapParser
from spider.crawlers.url_scheduler import URLScheduler
from spider.crawlers.robots_handler import (
    fetch_and_parse,
    get_crawl_delay,
    is_allowed,
)
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.database_manager import EnhancedDatabaseManager
from scripts.utils import get_script_logger

# 載入環境設定
load_config()

# 建立日誌器
logger = get_script_logger("discover")

# 允許的最大 crawl-delay 秒數
MAX_CRAWL_DELAY = 30

async def main(domains: list[str]) -> None:
    """主程式入口"""
    async with EnhancedDatabaseManager() as db_manager:
        scheduler = URLScheduler(db_manager)
        try:
            async with EnhancedConnectionManager() as connection_manager:
                parser = SitemapParser(connection_manager)
                for domain in domains:
                    logger.info(f"開始解析 {domain} 的 sitemap")

                    # 解析 robots.txt 並檢查限制
                    await fetch_and_parse(domain, connection_manager)
                    root_url = (
                        domain if domain.startswith("http") else f"https://{domain}/"
                    )
                    if not await is_allowed(root_url, connection_manager):
                        logger.warning("該網站禁止爬取，略過此網域")
                        continue
                    crawl_delay = await get_crawl_delay(domain, connection_manager)
                    if crawl_delay and crawl_delay > MAX_CRAWL_DELAY:
                        logger.warning(
                            f"crawl-delay {crawl_delay}s 過大，略過此網域"
                        )
                        continue

                    await parser.stream_discover(domain, scheduler)
                    logger.info(f"完成解析 {domain}")
        finally:
            await scheduler.close()
            logger.info("URL scheduler closed and remaining URLs flushed to DB.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="解析 sitemap 並加入 URL 排程器")
    parser.add_argument(
        "--domains",
        nargs="+",
        required=True,
        help="要處理的根網域，例如: https://www.example.com",
    )
    args = parser.parse_args()
    asyncio.run(main(args.domains))
