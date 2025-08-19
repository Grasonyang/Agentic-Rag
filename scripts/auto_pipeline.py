"""
自動化爬蟲流程

循環執行 discover → crawl → embed，直到 URLScheduler 無待抓取 URL。
"""

import argparse
import asyncio
import os
import sys
from importlib import import_module

# 加入專案根目錄以便匯入模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import get_script_logger
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
from spider.utils.enhanced_logger import spider_logger

# 建立日誌器
logger = get_script_logger("auto_pipeline")

# 允許的最大 crawl-delay 秒數
MAX_CRAWL_DELAY = 30


def import_script(name: str):
    """動態匯入數字開頭的腳本模組"""
    return import_module(f"scripts.{name}")



async def crawl_once(domain: str, batch_size: int) -> int:
    """抓取一批 URL 並回傳處理數量"""
    async with EnhancedDatabaseManager() as db_manager:
        scheduler = URLScheduler(db_manager)
        async with EnhancedConnectionManager(rate_limiter=AdaptiveRateLimiter()) as cm:
            await fetch_and_parse(domain, cm)
            crawl_delay = await get_crawl_delay(domain, cm)
            if crawl_delay and crawl_delay > MAX_CRAWL_DELAY:
                logger.warning(f"crawl-delay {crawl_delay}s 過大，終止爬取階段")
                return 0
            if crawl_delay:
                rl = getattr(cm, "_rate_limiter", None)
                if rl:
                    rl.config.min_delay = max(rl.config.min_delay, float(crawl_delay))
            crawler = ProgressiveCrawler(
                scheduler,
                RetryManager(),
                cm,
                batch_size=batch_size,
                concurrency=batch_size,
            )
            processed = await crawler.crawl_batch()
            logger.info(f"本輪抓取 {processed} 個 URL")
            return processed


async def run_pipeline(domain: str, batch_size: int) -> None:
    """持續執行 discover → crawl → embed，直到無待抓取 URL"""
    current_batch = batch_size
    round_count = 1
    while True:
        logger.info(f"開始第 {round_count} 輪流程，batch_size={current_batch}")
        discover = import_script("1_discover_urls")
        embed = import_script("3_process_and_embed")

        async with asyncio.TaskGroup() as tg:
            tg.create_task(discover.main([domain]))
            crawl_task = tg.create_task(crawl_once(domain, current_batch))

        processed = crawl_task.result()
        if processed == 0:
            logger.info("URLScheduler 無待抓取 URL，流程結束")
            break

        embed.main(processed)
        logger.info(f"完成向量化 {processed} 篇文章")
        spider_logger.log_statistics()

        current_batch = processed
        round_count += 1


async def schedule_loop(domain: str, batch_size: int, interval: int):
    """以固定週期重複執行流程"""
    while True:
        await run_pipeline(domain, batch_size)
        logger.info(f"等待 {interval} 秒後進行下一輪...")
        await asyncio.sleep(interval)


async def verify_robots(domain: str) -> bool:
    """解析 robots.txt 並檢查限制"""
    async with EnhancedConnectionManager() as cm:
        await fetch_and_parse(domain, cm)
        root_url = domain if domain.startswith("http") else f"https://{domain}/"
        if not await is_allowed(root_url, cm):
            logger.warning("該網站禁止爬取，終止流程")
            return False
        crawl_delay = await get_crawl_delay(domain, cm)
        if crawl_delay and crawl_delay > MAX_CRAWL_DELAY:
            logger.warning(
                f"crawl-delay {crawl_delay}s 過大，終止流程",
            )
            return False
    return True


def main():
    """解析參數並啟動流程"""
    parser = argparse.ArgumentParser(description="自動化爬蟲流程")
    parser.add_argument("--domain", required=True, help="目標網站網域或 URL")
    parser.add_argument("--batch_size", type=int, default=100, help="每輪處理的最大數量")
    parser.add_argument("--schedule", type=int, help="以秒為單位的執行間隔；若未設定則僅執行一次")
    args = parser.parse_args()

    # 解析 robots.txt，若不允許則終止
    if not asyncio.run(verify_robots(args.domain)):
        return

    if args.schedule:
        logger.info(f"啟動長駐模式，間隔 {args.schedule} 秒")
        asyncio.run(schedule_loop(args.domain, args.batch_size, args.schedule))
    else:
        asyncio.run(run_pipeline(args.domain, args.batch_size))


if __name__ == "__main__":
    main()
