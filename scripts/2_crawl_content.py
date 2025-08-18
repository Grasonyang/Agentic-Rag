"""
腳本二: 內容爬取 (Crawl Content)

功能:
1. 從資料庫 `discovered_urls` 表中獲取狀態為 'pending' 的 URL。
2. 使用 AsyncWebCrawler 逐一爬取這些 URL 的內容。
3. 將成功爬取的內容（Markdown 格式）存入 `articles` 表。
4. 更新 `discovered_urls` 表中對應 URL 的狀態為 'completed' 或 'error'。
5. 此腳本可重複執行，直到所有待處理的 URL 都被處理完畢。

執行方式:
python -m scripts.2_crawl_content --max_urls 100
"""

import argparse
import logging
import asyncio
import os

# 配置專案根目錄
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import load_config
from database.operations import get_database_operations
from database.models import ArticleModel, CrawlStatus
from crawl4ai import AsyncWebCrawler
from spider.crawlers.robots_handler import (
    fetch_and_parse,
    is_allowed,
    get_crawl_delay,
)
from spider.utils.rate_limiter import AdaptiveRateLimiter, RateLimitConfig

# 載入 .env 配置
load_config()

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def get_rate_limiter() -> AdaptiveRateLimiter:
    """從環境變數讀取並回傳自適應速率限制器"""
    return AdaptiveRateLimiter(
        RateLimitConfig(
            requests_per_second=float(os.getenv("RATE_LIMIT_RPS", 1.0)),
            burst_size=int(os.getenv("RATE_LIMIT_BURST", 5)),
            min_delay=float(os.getenv("RATE_LIMIT_MIN_DELAY", 0.5)),
            max_delay=float(os.getenv("RATE_LIMIT_MAX_DELAY", 10.0)),
        )
    )

async def main(max_urls: int):
    """
    主執行函數

    Args:
        max_urls (int): 每次執行時處理的 URL 數量上限。
    """
    if max_urls:
        logger.info(f"內容爬取腳本開始執行，本次最多處理 {max_urls} 個 URL。")
    else:
        logger.info(f"內容爬取腳本開始執行，本次將處理所有待處理的 URL。")

    db_ops = get_database_operations()
    if not db_ops:
        logger.error("無法初始化資料庫連接，腳本終止。")
        return

    # 1. 獲取待爬取的 URL
    pending_urls = db_ops.get_pending_urls(limit=max_urls)
    if not pending_urls:
        logger.info("沒有待處理的 URL，腳本執行完畢。")
        return

    logger.info(f"從資料庫獲取了 {len(pending_urls)} 個待處理的 URL。")

    # 先下載並解析各網域的 robots.txt 以利後續判斷
    domains = {u.domain for u in pending_urls}
    for domain in domains:
        fetch_and_parse(domain)

    # 2. 逐一爬取並處理
    processed_count = 0
    success_count = 0
    crawler_restart_count = 0
    max_crawler_restarts = 3
    
    rate_limiter = get_rate_limiter()

    # 使用更健壯的爬蟲管理
    crawler = None
    try:
        for url_model in pending_urls:
            # 如果爬虫未初始化或需要重启
            if crawler is None:
                try:
                    logger.info("正在初始化/重啟爬蟲...")
                    crawler = AsyncWebCrawler(
                        # 添加更穩健的配置
                        browser_config={
                            "headless": True,
                            "args": [
                                "--no-sandbox",
                                "--disable-dev-shm-usage",
                                "--disable-extensions",
                                "--disable-gpu",
                                "--disable-web-security",
                                "--ignore-certificate-errors",
                                "--memory-pressure-off",
                                "--max_old_space_size=4096",
                            ]
                        }
                    )
                    # 套用自定義速率限制器
                    rate_limiter.apply_to_crawl4ai(crawler)
                    await crawler.__aenter__()
                    logger.info("爬蟲初始化成功")
                except Exception as e:
                    logger.error(f"爬虫初始化失败: {e}")
                    break

            # 先確認 robots.txt 是否允許
            if not is_allowed(url_model.url):
                logger.info(f"URL 被 robots.txt 禁止: {url_model.url}")
                db_ops.update_crawl_status(url_model.id, CrawlStatus.SKIPPED)
                continue

            # 若有設定 crawl-delay，於此等待
            delay = get_crawl_delay(url_model.domain)
            if delay:
                logger.info(f"遵守 crawl-delay {delay} 秒")
                await asyncio.sleep(delay)

            logger.info(f"正在處理 URL (ID: {url_model.id}): {url_model.url}")

            # a. 更新狀態為爬取中
            db_ops.update_crawl_status(url_model.id, CrawlStatus.CRAWLING)

            # b. 執行爬取
            try:
                result = await crawler.arun(url_model.url)
                
                if not result.success:
                    raise Exception(f"Crawl failed with error: {result.error_message}")

                # c. 處理爬取結果
                logger.info(f"爬取成功: {url_model.url}")
                article = ArticleModel(
                    url=url_model.url,
                    title=url_model.url,  # 使用 URL 作為標題
                    content=result.markdown,
                    crawled_from_url_id=url_model.id,
                    metadata={'source': 'crawl4ai'}
                )
                
                # 存入文章到資料庫
                if db_ops.create_article(article):
                    success_count += 1
                    # 更新狀態為完成
                    db_ops.update_crawl_status(url_model.id, CrawlStatus.COMPLETED)
                else:
                    # 文章已存在或創建失敗
                    error_msg = "Article already exists or failed to create."
                    logger.warning(f"{url_model.url} - {error_msg}")
                    db_ops.update_crawl_status(url_model.id, CrawlStatus.ERROR, error_message=error_msg)

            except Exception as e:
                error_message = str(e)
                logger.error(f"爬取失敗: {url_model.url}, 原因: {error_message}")
                
                # 检查是否是连接错误，需要重启爬虫
                if ("Connection closed" in error_message or 
                    "Target page, context or browser has been closed" in error_message or
                    "Browser" in error_message and "close" in error_message):
                    
                    logger.warning("检测到浏览器连接问题，准备重启爬虫...")
                    
                    # 清理当前爬虫
                    try:
                        if crawler:
                            await crawler.__aexit__(None, None, None)
                    except:
                        pass  # 忽略清理时的错误
                    
                    crawler = None
                    crawler_restart_count += 1
                    
                    if crawler_restart_count <= max_crawler_restarts:
                        logger.info(f"将在下次循环中重启爬虫 ({crawler_restart_count}/{max_crawler_restarts})")
                        # 为这个URL设置错误状态，下次运行时会重试
                        db_ops.update_crawl_status(url_model.id, CrawlStatus.PENDING, error_message=f"Browser restart needed: {error_message}")
                    else:
                        logger.error(f"爬虫重启次数已达上限，跳过此URL")
                        db_ops.update_crawl_status(url_model.id, CrawlStatus.ERROR, error_message=error_message)
                else:
                    # 其他类型的错误
                    db_ops.update_crawl_status(url_model.id, CrawlStatus.ERROR, error_message=error_message)
            
            processed_count += 1

            # 根據 crawl-delay 或預設 1 秒延遲
            delay = get_crawl_delay(url_model.domain) or 1
            await asyncio.sleep(delay)

    finally:
        # 确保爬虫被正确关闭
        if crawler:
            try:
                await crawler.__aexit__(None, None, None)
                logger.info("爬虫已正常关闭")
            except Exception as e:
                logger.warning(f"爬虫关闭时出现警告: {e}")

    logger.info(f"本次執行完成。共處理 {processed_count} 個 URL，其中 {success_count} 個成功存為文章。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="內容爬取腳本：從資料庫讀取待處理 URL，爬取其內容並存儲。")
    parser.add_argument(
        '--max_urls',
        type=int,
        default=None,
        help='每次執行時處理的 URL 數量上限。如果未設定，則處理所有待處理的 URL。'
    )
    args = parser.parse_args()
    
    asyncio.run(main(args.max_urls))