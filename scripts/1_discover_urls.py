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
import asyncio
import logging
from urllib.parse import urlparse

# 配置專案根目錄，以便正確導入模組
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import load_config
from database.operations import get_database_operations
from database.models import DiscoveredURLModel, SitemapModel
from spider.crawlers.sitemap_parser import SitemapParser
from spider.utils.connection_manager import EnhancedConnectionManager

# 載入 .env 配置
load_config()

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    stream=sys.stdout
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

    # 創建連接管理器和 sitemap 解析器
    async with EnhancedConnectionManager() as connection_manager:
        sitemap_parser = SitemapParser(connection_manager)

        for domain_url in domains:
            logger.info(f"正在處理域名: {domain_url}")
            initial_urls, initial_sitemaps = await sitemap_parser.discover_urls_from_sitemaps(domain_url)
            logger.info(f"從 {domain_url} 的 sitemaps 中初步發現 {len(initial_urls)} 個 URL。")
            logger.info(f"初步解析了 {len(initial_sitemaps)} 個 sitemap。")

            # 先保存所有已确认的 sitemap URLs (跳过已存在的)
            if initial_sitemaps:
                sitemap_count = 0
                skipped_count = 0
                for sitemap_url in initial_sitemaps:
                    if check_url_exists_in_db(db_ops, sitemap_url):
                        skipped_count += 1
                        logger.debug(f"跳过已存在的 sitemap: {sitemap_url}")
                        continue
                        
                    sitemap_model = SitemapModel(url=sitemap_url, domain=domain_url)
                    if db_ops.create_sitemap(sitemap_model):
                        sitemap_count += 1
                        
                logger.info(f"已將 {sitemap_count} 個新的 sitemap 存入資料庫 (跳過 {skipped_count} 個已存在)。")

            # 逐個驗證 URL 並即時保存 (跳過已存在的)
            final_sitemap_count = 0
            final_url_count = 0
            processed_count = 0
            skipped_count = 0
            error_count = 0
            start_time = asyncio.get_event_loop().time()
            
            if not initial_urls:
                logger.info("沒有待驗證的 URL，跳過驗證步驟。")
            else:
                logger.info(f"開始逐個驗證 {len(initial_urls)} 個 URL...")
                
                for i, url in enumerate(initial_urls, 1):
                    processed_count += 1
                    
                    # 检查是否已经存在
                    if check_url_exists_in_db(db_ops, url):
                        skipped_count += 1
                        logger.debug(f"跳過已存在的 URL: {url}")
                        continue
                    
                    # 每處理指定數量的 URL 或處理完最後一個時報告進度
                    if processed_count % BATCH_SAVE_SIZE == 0 or processed_count == len(initial_urls):
                        elapsed_time = asyncio.get_event_loop().time() - start_time
                        avg_time_per_url = elapsed_time / (processed_count - skipped_count) if (processed_count - skipped_count) > 0 else 0
                        remaining_urls = len(initial_urls) - processed_count
                        estimated_remaining_time = remaining_urls * avg_time_per_url
                        
                        logger.info(f"進度: {processed_count}/{len(initial_urls)} ({processed_count/len(initial_urls)*100:.1f}%)")
                        logger.info(f"  - 已發現 sitemap: {final_sitemap_count} 個")
                        logger.info(f"  - 已保存 URL: {final_url_count} 個") 
                        logger.info(f"  - 跳過已存在: {skipped_count} 個")
                        logger.info(f"  - 處理錯誤: {error_count} 個")
                        logger.info(f"  - 平均處理時間: {avg_time_per_url:.2f}s/URL")
                        if remaining_urls > 0:
                            logger.info(f"  - 預估剩餘時間: {estimated_remaining_time/60:.1f} 分鐘")
                    
                    try:
                        if await sitemap_parser._is_sitemap_by_content(url):
                            # 這是一個隱藏的 sitemap，立即保存
                            sitemap_model = SitemapModel(url=url, domain=domain_url)
                            if db_ops.create_sitemap(sitemap_model):
                                final_sitemap_count += 1
                                logger.debug(f"發現並保存隱藏 sitemap: {url}")
                            else:
                                logger.warning(f"保存隱藏 sitemap 失敗: {url}")
                                error_count += 1
                        else:
                            # 這是一個待爬取的 URL，立即保存
                            discovered_url_model = DiscoveredURLModel(url=url)
                            if db_ops.create_discovered_url(discovered_url_model):
                                final_url_count += 1
                                logger.debug(f"保存待爬取 URL: {url}")
                            else:
                                logger.warning(f"保存待爬取 URL 失敗: {url}")
                                error_count += 1
                            
                    except KeyboardInterrupt:
                        logger.warning(f"收到中斷信號，已處理 {processed_count}/{len(initial_urls)} 個 URL")
                        logger.info(f"當前結果: sitemap={final_sitemap_count}, URL={final_url_count}, 跳過={skipped_count}, 錯誤={error_count}")
                        raise
                        
                    except Exception as e:
                        error_count += 1
                        logger.warning(f"驗證 URL {url} 時發生錯誤: {e}，將其視為待爬取 URL")
                        # 出錯時也嘗試保存為待爬取 URL
                        try:
                            discovered_url_model = DiscoveredURLModel(url=url)
                            if db_ops.create_discovered_url(discovered_url_model):
                                final_url_count += 1
                                logger.debug(f"錯誤 URL 已保存為待爬取: {url}")
                            else:
                                logger.error(f"保存錯誤 URL {url} 到資料庫也失敗")
                        except Exception as save_error:
                            logger.error(f"保存 URL {url} 到資料庫失敗: {save_error}")
            
            # 最終報告
            total_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"域名 {domain_url} 處理完成 (耗時 {total_time:.1f}s):")
            logger.info(f"  - 初始 sitemap: {len(initial_sitemaps)} 個")
            logger.info(f"  - 新發現的 sitemap: {final_sitemap_count} 個") 
            logger.info(f"  - 待爬取 URL: {final_url_count} 個")
            logger.info(f"  - 跳過已存在: {skipped_count} 個")
            logger.info(f"  - 處理錯誤: {error_count} 個")
            logger.info(f"  - 總處理數量: {processed_count} 個")
            logger.info(f"  - 成功率: {((final_sitemap_count + final_url_count)/(processed_count - skipped_count)*100) if (processed_count - skipped_count) > 0 else 100:.1f}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="URL 發現腳本：解析 Sitemaps 並將 URL 存入資料庫。")
    parser.add_argument(
        '--domains',
        nargs='+',
        required=True,
        help='要爬取的根域名 URL 列表 (例如: https://www.example.com)'
    )
    args = parser.parse_args()
    
    asyncio.run(main(args.domains))
