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
from spider.crawlers.robots_handler import (
    fetch_and_parse,
    get_crawl_delay,
    is_allowed,
)
from spider.crawlers.url_scheduler import URLScheduler
from spider.crawlers.progressive_crawler import ProgressiveCrawler
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.database_manager import EnhancedDatabaseManager
from spider.utils.rate_limiter import AdaptiveRateLimiter
from spider.utils.retry_manager import RetryManager
from spider.workers.chunk_embed_worker import ChunkEmbedWorker
from scripts.utils import get_script_logger

# 載入環境設定
load_config()

logger = get_script_logger("crawl")

# 允許的最大 crawl-delay 秒數
MAX_CRAWL_DELAY = 30


async def main(domain: str, batch_size: int) -> None:
    """初始化並執行批次爬蟲"""
    async with EnhancedDatabaseManager() as db_manager:
        scheduler = URLScheduler(db_manager)
        async with EnhancedConnectionManager(
            rate_limiter=AdaptiveRateLimiter()
        ) as cm:
            # 下載並解析 robots.txt
            await fetch_and_parse(domain, cm)
            root_url = domain if domain.startswith("http") else f"https://{domain}/"
            if not await is_allowed(root_url, cm):
                logger.warning("該網站禁止爬取，終止流程")
                return
            crawl_delay = await get_crawl_delay(domain, cm)
            if crawl_delay and crawl_delay > MAX_CRAWL_DELAY:
                logger.warning(
                    f"crawl-delay {crawl_delay}s 過大，終止流程"
                )
                return

            # 以 batch_size 同時設定批次大小與並行數量
            worker = ChunkEmbedWorker(scheduler.db_manager)
            crawler = ProgressiveCrawler(
                scheduler,
                RetryManager(),
                cm,
                batch_size=batch_size,
                concurrency=batch_size,
                embed_worker=worker,
            )
            processed = await crawler.crawl_batch()
            await worker.flush()
            logger.info(f"本次處理 {processed} 個 URL")
            logger.log_statistics()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="從排程器抓取內容")
    parser.add_argument("--domain", required=True, help="目標網站網域或 URL")
    parser.add_argument(
        "--batch_size",
        type=int,
        default=10,
        help="每批處理的 URL 數量",
    )
    args = parser.parse_args()
    asyncio.run(main(args.domain, args.batch_size))
