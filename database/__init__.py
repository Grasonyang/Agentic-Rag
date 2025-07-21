"""
資料庫管理模組
管理所有與 Supabase 相關的功能
"""

from .client import SupabaseClient
from .models import (
    ArticleModel, ChunkModel, SearchLogModel, EmbeddingCacheModel,
    SitemapModel, DiscoveredURLModel, RobotsTxtModel,
    CrawlStatus, SitemapType, URLType
)
from .operations import DatabaseOperations

__all__ = [
    'SupabaseClient',
    'ArticleModel', 
    'ChunkModel',
    'SearchLogModel',
    'EmbeddingCacheModel',
    'SitemapModel',
    'DiscoveredURLModel',
    'RobotsTxtModel',
    'CrawlStatus',
    'SitemapType',
    'URLType',
    'DatabaseOperations'
]
