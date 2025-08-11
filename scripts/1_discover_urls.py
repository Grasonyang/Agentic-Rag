"""
腳本一: URL 發現 (Discover URLs)

功能:
1. 接收一個或多個根域名作為輸入。
2. 使用 SitemapParser 解析 robots.txt 和 sitemaps，提取所有頁面 URL。
3. 將解析出的頁面 URL 存入資料庫 `discovered_urls` 表，以供後續爬取。

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

from config_manager import load_config
from database.operations import get_database_operations
from database.models import DiscoveredURLModel
from spider.crawlers.sitemap_parser import SitemapParser

# 載入 .env 配置
load_config()

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

    sitemap_parser = SitemapParser()

    for domain_url in domains:
        logger.info(f"正在處理域名: {domain_url}")
        urls = sitemap_parser.discover_urls_from_sitemaps(domain_url)
        logger.info(f"從 {domain_url} 的 sitemaps 中發現 {len(urls)} 個 URL。")

        if urls:
            discovered_url_models = [
                DiscoveredURLModel(url=url) for url in urls
            ]
            
            created_count = db_ops.bulk_create_discovered_urls(discovered_url_models)
            logger.info(f"批量存入 {created_count} 個 URL 到資料庫。")

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
