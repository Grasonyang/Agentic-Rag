"""通用腳本工具"""

from spider.utils.enhanced_logger import get_spider_logger


def get_script_logger(name: str):
    """取得腳本專用的日誌器"""
    return get_spider_logger(name)

