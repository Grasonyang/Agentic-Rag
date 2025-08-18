"""
自動化爬蟲流程

依序執行 discover -> crawl -> embed，可單次或週期性運行。
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
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.enhanced_logger import spider_logger

# 建立日誌器
logger = get_script_logger("auto_pipeline")

# 允許的最大 crawl-delay 秒數
MAX_CRAWL_DELAY = 30


def import_script(name: str):
    """動態匯入數字開頭的腳本模組"""
    return import_module(f"scripts.{name}")



async def run_once(domain: str, batch_size: int):
    """執行一次完整流程"""
    logger.info("開始執行一次管線流程")

    # discover 與 crawl 併發執行
    discover = import_script("1_discover_urls")
    crawl = import_script("2_crawl_content")
    await asyncio.gather(
        discover.main([domain]),
        crawl.main(domain, batch_size),
    )

    # embed
    embed = import_script("3_process_and_embed")
    embed.main(batch_size)

    logger.info("本輪流程完成")
    spider_logger.log_statistics()


async def schedule_loop(domain: str, batch_size: int, interval: int):
    """以固定週期重複執行流程"""
    while True:
        await run_once(domain, batch_size)
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
        asyncio.run(run_once(args.domain, args.batch_size))


if __name__ == "__main__":
    main()
