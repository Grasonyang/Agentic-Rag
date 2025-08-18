"""腳本一: URL 發現 (Discover URLs)

此腳本解析指定網域的 sitemap，並將發現的頁面 URL
串流寫入 URLScheduler。使用方式:
python -m scripts.1_discover_urls --domains https://www.example.com
"""

import argparse
import asyncio
import logging
import sys
import os

# 調整匯入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import load_config
from spider.crawlers.sitemap_parser import SitemapParser
from spider.crawlers.url_scheduler import URLScheduler
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.rate_limiter import RateLimiter, RateLimitConfig
from spider.utils.database_manager import EnhancedDatabaseManager

# 載入環境設定
load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# 全局计数器，用于跟踪处理进度
BATCH_SAVE_SIZE = 10  # 每處理10個 URL 報告一次進度

def check_url_exists_in_db(db_ops, url: str) -> bool:
    """使用資料庫操作檢查 URL 是否已存在"""
    try:
        return db_ops.url_exists(url)
    except Exception as e:
        logger.warning(f"檢查 URL {url} 是否存在時出錯: {e}")
        return False

async def main(domains: list[str]):
    """
    主執行函數

    Args:
        domains (list[str]): 要爬取的根域名 URL 列表。
    """
    logger.info(f"腳本開始執行，目標域名: {domains}")

    db_ops = get_database_operations()
    if not db_ops:
        logger.error("無法初始化資料庫連接，腳本終止。")
        return

    # 建立全域速率限制器
    rate_limiter = RateLimiter(
        RateLimitConfig(
            requests_per_second=float(os.getenv("RATE_LIMIT_RPS", 2.0)),
            burst_size=int(os.getenv("RATE_LIMIT_BURST", 5)),
        )
    )

    # 創建連接管理器和 sitemap 解析器
    async with EnhancedConnectionManager(rate_limiter=rate_limiter) as connection_manager:
        sitemap_parser = SitemapParser(connection_manager)

        for domain_url in domains:
            logger.info(f"正在處理域名: {domain_url}")
            initial_urls, initial_sitemaps = await sitemap_parser.discover_urls_from_sitemaps(domain_url)
            logger.info(f"從 {domain_url} 的 sitemaps 中初步發現 {len(initial_urls)} 個 URL。")
            logger.info(f"初步解析了 {len(initial_sitemaps)} 個 sitemap。")

async def main(domains: list[str]) -> None:
    """主程式入口"""
    async with EnhancedDatabaseManager() as db_manager:
        scheduler = URLScheduler(db_manager)
        async with EnhancedConnectionManager() as connection_manager:
            parser = SitemapParser(connection_manager)
            for domain in domains:
                logger.info(f"開始解析 {domain} 的 sitemap")
                await parser.stream_discover(domain, scheduler)
                logger.info(f"完成解析 {domain}")


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
