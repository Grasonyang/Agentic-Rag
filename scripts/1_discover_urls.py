"""
腳本一: URL 發現 (Discover URLs)

功能:
1. 接收一個或多個根域名作為輸入。
2. 使用 RobotsParser 解析 robots.txt，找到 Sitemaps。
3. 將找到的 Sitemap URL 存入資料庫 `sitemaps` 表。
4. 使用 SitemapCrawler 解析 Sitemap，提取所有頁面 URL。
5. 將解析出的頁面 URL 存入資料庫 `discovered_urls` 表，以供後續爬取。

執行方式:
python -m scripts.1_discover_urls --domains https://www.example.com https://www.another.com
"""

import argparse
import logging
from urllib.parse import urlparse

# 配置專案根目錄，以便正確導入模組
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.operations import get_database_operations, DatabaseOperations
from database.models import SitemapModel, DiscoveredURLModel, CrawlStatus
from spider.crawlers.robots_parser import RobotsParser
from spider.crawlers.sitemap_crawler import SitemapCrawler, SitemapEntry

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def main(domains: list[str]):
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

    for domain_url in domains:
        process_domain(domain_url, db_ops)

def process_domain(domain_url: str, db_ops: DatabaseOperations):
    """
    處理單個域名。
    """
    logger.info(f"正在處理域名: {domain_url}")
    domain = urlparse(domain_url).netloc

    # 1. 解析 robots.txt
    robot_parser = RobotsParser()
    if not robot_parser.parse(domain_url):
        logger.warning(f"無法解析 {domain_url} 的 robots.txt，將嘗試直接尋找 sitemap.xml")
        sitemap_urls = [f"{domain_url.rstrip('/')}/sitemap.xml"]
    else:
        sitemap_urls = robot_parser.get_sitemaps()
        if not sitemap_urls:
            logger.warning(f"在 {domain_url} 的 robots.txt 中未找到 Sitemap，將嘗試預設路徑。")
            sitemap_urls = [f"{domain_url.rstrip('/')}/sitemap.xml"]

    logger.info(f"找到 {len(sitemap_urls)} 個 Sitemap 來源: {sitemap_urls}")

    # 2. 遍歷 Sitemaps 並解析
    sitemap_crawler = SitemapCrawler()
    total_discovered_urls = 0

    for sitemap_url in sitemap_urls:
        # a. 將 sitemap 記錄到資料庫
        sitemap_model = SitemapModel(url=sitemap_url, domain=domain, status=CrawlStatus.PENDING)
        # 這裡可以增加檢查，如果 sitemap 已存在且已完成，則跳過
        db_ops.create_sitemap(sitemap_model)

        # b. 解析 sitemap，獲取頁面 URL
        try:
            sitemap_entries = list(sitemap_crawler.crawl_sitemap(sitemap_url))
            if not sitemap_entries:
                logger.warning(f"Sitemap {sitemap_url} 為空或無法解析。")
                db_ops.update_sitemap_status(sitemap_model.id, CrawlStatus.ERROR, error_message="Sitemap is empty or could not be parsed")
                continue

            # c. 將解析到的 URL 批量存入資料庫
            discovered_url_models = [
                DiscoveredURLModel(
                    url=entry.url,
                    source_sitemap=entry.source_sitemap,
                    priority=entry.priority,
                    lastmod=entry.lastmod,
                    changefreq=entry.changefreq
                )
                for entry in sitemap_entries
            ]
            
            created_count = db_ops.bulk_create_discovered_urls(discovered_url_models)
            total_discovered_urls += created_count
            logger.info(f"從 {sitemap_url} 批量存入 {created_count} 個 URL 到資料庫。")

            # d. 更新 sitemap 狀態為完成
            db_ops.update_sitemap_status(sitemap_model.id, CrawlStatus.COMPLETED, urls_count=len(sitemap_entries))

        except Exception as e:
            logger.error(f"處理 Sitemap {sitemap_url} 時發生嚴重錯誤: {e}", exc_info=True)
            db_ops.update_sitemap_status(sitemap_model.id, CrawlStatus.ERROR, error_message=str(e))

    logger.info(f"域名 {domain_url} 處理完成，共發現 {total_discovered_urls} 個新 URL。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="URL 發現腳本：解析 Sitemaps 並將 URL 存入資料庫。")
    parser.add_argument(
        '--domains',
        nargs='+',
        required=True,
        help='要爬取的根域名 URL 列表 (例如: https://www.example.com)'
    )
    args = parser.parse_args()
    
    main(args.domains)
