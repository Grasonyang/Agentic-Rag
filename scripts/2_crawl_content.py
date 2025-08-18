"""腳本二: 內容爬取 (Crawl Content)

此腳本從 URLScheduler 取出待抓取的 URL 並進行抓取。
"""

import argparse
import asyncio
import os
import sys

# 調整模組匯入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import load_config
from spider.crawlers.url_scheduler import URLScheduler
from spider.crawlers.progressive_crawler import ProgressiveCrawler
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.database_manager import EnhancedDatabaseManager
from spider.utils.rate_limiter import AdaptiveRateLimiter
from spider.utils.retry_manager import RetryManager
from scripts.utils import get_script_logger

# 載入環境設定
load_config()

logger = get_script_logger("crawl")


async def main(batch_size: int) -> None:
    """初始化並執行批次爬蟲"""
    async with EnhancedDatabaseManager() as db_manager:
        scheduler = URLScheduler(db_manager)
        cm = EnhancedConnectionManager(rate_limiter=AdaptiveRateLimiter())
        crawler = ProgressiveCrawler(scheduler, cm, RetryManager(), batch_size=batch_size)
        processed = await crawler.crawl_batch()
        logger.info(f"本次處理 {processed} 個 URL")
        logger.log_statistics()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="從排程器抓取內容")
    parser.add_argument(
        "--batch_size",
        type=int,
        default=10,
        help="每批處理的 URL 數量",
    )
    args = parser.parse_args()
    asyncio.run(main(args.batch_size))
