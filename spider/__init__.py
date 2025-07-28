"""
Spider 爬蟲框架(基於craw4ai)
提供穩健的網頁爬取、資料處理和存儲功能
"""

from .crawlers.web_crawler import WebCrawler
from .crawlers.sitemap_parser import SitemapParser
from .crawlers.simple_crawler import SimpleWebCrawler
from .chunking.sliding_window import SlidingWindowChunking
from .chunking.sentence_chunking import SentenceChunking
from .utils.retry_manager import RetryManager
from .utils.rate_limiter import RateLimiter

__version__ = "1.0.0"
__all__ = [
    "WebCrawler",
    "SimpleWebCrawler",
    "SitemapParser", 
    "SlidingWindowChunking",
    "SentenceChunking",
    "RetryManager",
    "RateLimiter"
]
