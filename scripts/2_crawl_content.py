"""
腳本二: 內容爬取 (Crawl Content)

功能:
1. 從資料庫 `discovered_urls` 表中獲取狀態為 'pending' 的 URL。
2. 使用 WebCrawler 逐一爬取這些 URL 的內容。
3. 將成功爬取的內容（標題、正文）存入 `articles` 表。
4. 更新 `discovered_urls` 表中對應 URL 的狀態為 'completed' 或 'error'。
5. 此腳本可重複執行，直到所有待處理的 URL 都被處理完畢。

執行方式:
python -m scripts.2_crawl_content --limit 100
"""

import argparse
import logging
import time

# 配置專案根目錄
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.operations import get_database_operations, DatabaseOperations
from database.models import ArticleModel, CrawlStatus
from spider.crawlers.web_crawler import WebCrawler, CrawlResult

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def main(limit: int):
    """
    主執行函數

    Args:
        limit (int): 每次執行時處理的 URL 數量上限。
    """
    logger.info(f"內容爬取腳本開始執行，本次最多處理 {limit} 個 URL。")

    db_ops = get_database_operations()
    if not db_ops:
        logger.error("無法初始化資料庫連接，腳本終止。")
        return

    # 1. 獲取待爬取的 URL
    pending_urls = db_ops.get_pending_urls(limit=limit)
    if not pending_urls:
        logger.info("沒有待處理的 URL，腳本執行完畢。")
        return

    logger.info(f"從資料庫獲取了 {len(pending_urls)} 個待處理的 URL。")

    # 2. 逐一爬取並處理
    crawler = WebCrawler()
    processed_count = 0
    success_count = 0

    for url_model in pending_urls:
        logger.info(f"正在處理 URL (ID: {url_model.id}): {url_model.url}")

        # a. 更新狀態為爬取中
        db_ops.update_crawl_status(url_model.id, CrawlStatus.CRAWLING)

        # b. 執行爬取
        result = crawler.crawl(url_model.url)

        # c. 處理爬取結果
        if result.error:
            # 爬取失敗
            logger.error(f"爬取失敗: {result.url}, 原因: {result.error}")
            db_ops.update_crawl_status(url_model.id, CrawlStatus.ERROR, error_message=result.error)
        else:
            # 爬取成功
            logger.info(f"爬取成功: {result.url}, 標題: {result.title[:50]}...")
            article = ArticleModel(
                url=result.url,
                title=result.title,
                content=result.content,
                crawled_from_url_id=url_model.id,
                metadata={'source': 'web_crawler'}
            )
            
            # 存入文章到資料庫
            if db_ops.create_article(article):
                success_count += 1
                # 更新狀態為完成
                db_ops.update_crawl_status(url_model.id, CrawlStatus.COMPLETED)
            else:
                # 文章已存在或創建失敗
                error_msg = "Article already exists or failed to create."
                logger.warning(f"{result.url} - {error_msg}")
                db_ops.update_crawl_status(url_model.id, CrawlStatus.ERROR, error_message=error_msg)
        
        processed_count += 1
        # 每次處理後短暫休眠，避免請求過於頻繁
        time.sleep(1)

    crawler.close_session()
    logger.info(f"本次執行完成。共處理 {processed_count} 個 URL，其中 {success_count} 個成功存為文章。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="內容爬取腳本：從資料庫讀取待處理 URL，爬取其內容並存儲。")
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='每次執行時處理的 URL 數量上限。'
    )
    args = parser.parse_args()
    
    main(args.limit)
