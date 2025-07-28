"""
RAG 資料庫模型定義
對應 schema.sql 的完整模型定義
簡化為 4 個核心表格：discovered_urls, articles, article_chunks, sitemaps
"""

import uuid
import hashlib
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

class CrawlStatus(Enum):
    """爬取狀態枚舉"""
    PENDING = "pending"          # 待爬取
    CRAWLING = "crawling"        # 爬取中
    COMPLETED = "completed"      # 成功
    ERROR = "error"              # 失敗
    SKIPPED = "skipped"          # 跳過

class ChangeFreq(Enum):
    """變更頻率枚舉"""
    ALWAYS = "always"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    NEVER = "never"


class URLType(Enum):
    """URL 類型枚舉"""
    ARTICLE = "article"         # 文章頁面
    CONTENT = "content"         # 內容頁面
    OTHER = "other"            # 其他類型


class SitemapType(Enum):
    """Sitemap 類型枚舉"""
    SITEMAP = "sitemap"             # 標準 sitemap
    SITEMAPINDEX = "sitemapindex"   # sitemap 索引

class BaseModel:
    """基礎模型類別"""
    
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, Enum):
                data[key] = value.value
            else:
                data[key] = value
        return data
    
    def validate(self) -> bool:
        """驗證模型數據"""
        return True

class DiscoveredURLModel(BaseModel):
    """發現的 URL 模型 - 對應 discovered_urls 表"""
    
    def __init__(self, url: str, source_sitemap: str = None, priority: float = None,
                 changefreq: Union[ChangeFreq, str] = None, lastmod: datetime = None,
                 crawl_status: Union[CrawlStatus, str] = CrawlStatus.PENDING, 
                 metadata: Dict[str, Any] = None):
        super().__init__()
        self.url = url
        self.domain = urlparse(url).netloc
        self.source_sitemap = source_sitemap
        self.priority = priority
        self.changefreq = changefreq if isinstance(changefreq, ChangeFreq) else (ChangeFreq(changefreq) if changefreq else None)
        self.lastmod = lastmod
        self.crawl_status = crawl_status if isinstance(crawl_status, CrawlStatus) else CrawlStatus(crawl_status)
        self.crawl_attempts = 0
        self.last_crawl_at = None
        self.error_message = None
        self.metadata = metadata or {}
        self.updated_at = datetime.now()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiscoveredURLModel':
        """從字典創建實例"""
        # 處理時間字段
        lastmod = None
        if data.get("lastmod"):
            if isinstance(data["lastmod"], str):
                try:
                    lastmod = datetime.fromisoformat(data["lastmod"].replace('Z', '+00:00'))
                except ValueError:
                    lastmod = None
            elif isinstance(data["lastmod"], datetime):
                lastmod = data["lastmod"]
        
        url_model = cls(
            url=data["url"],
            source_sitemap=data.get("source_sitemap"),
            priority=data.get("priority"),
            changefreq=data.get("changefreq"),
            lastmod=lastmod,
            crawl_status=data.get("crawl_status", "pending"),
            metadata=data.get("metadata", {})
        )
        
        # 設置其他屬性
        if "id" in data:
            url_model.id = data["id"]
        if "created_at" in data:
            if isinstance(data["created_at"], str):
                url_model.created_at = datetime.fromisoformat(data["created_at"])
            else:
                url_model.created_at = data["created_at"]
        if "updated_at" in data:
            if isinstance(data["updated_at"], str):
                url_model.updated_at = datetime.fromisoformat(data["updated_at"])
            else:
                url_model.updated_at = data["updated_at"]
        if "crawl_attempts" in data:
            url_model.crawl_attempts = data["crawl_attempts"]
        if "last_crawl_at" in data and data["last_crawl_at"]:
            if isinstance(data["last_crawl_at"], str):
                url_model.last_crawl_at = datetime.fromisoformat(data["last_crawl_at"])
            else:
                url_model.last_crawl_at = data["last_crawl_at"]
        if "error_message" in data:
            url_model.error_message = data["error_message"]
        
        return url_model
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.url:
            logger.error("URL 不能為空")
            return False
        if not self.url.startswith(('http://', 'https://')):
            logger.error("URL 格式不正確")
            return False
        if self.priority is not None and (self.priority < 0.0 or self.priority > 1.0):
            logger.error("優先級必須在 0.0 到 1.0 之間")
            return False
        return True

class ArticleModel(BaseModel):
    """文章模型 - 對應 articles 表"""
    
    def __init__(self, url: str, title: str = "", content: str = "",
                 crawled_from_url_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__()
        self.url = url
        self.title = title
        self.content = content
        self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest() if content else ""
        self.word_count = len(content.split()) if content else 0
        self.crawled_from_url_id = crawled_from_url_id
        self.metadata = metadata or {}
        self.updated_at = datetime.now()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArticleModel':
        """從字典創建實例"""
        article = cls(
            url=data["url"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            crawled_from_url_id=data.get("crawled_from_url_id"),
            metadata=data.get("metadata", {})
        )
        
        if "id" in data:
            article.id = data["id"]
        if "created_at" in data:
            if isinstance(data["created_at"], str):
                article.created_at = datetime.fromisoformat(data["created_at"])
            else:
                article.created_at = data["created_at"]
        if "updated_at" in data:
            if isinstance(data["updated_at"], str):
                article.updated_at = datetime.fromisoformat(data["updated_at"])
            else:
                article.updated_at = data["updated_at"]
        if "content_hash" in data:
            article.content_hash = data["content_hash"]
        if "word_count" in data:
            article.word_count = data["word_count"]
            
        return article
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.url:
            logger.error("URL 不能為空")
            return False
        if not self.url.startswith(('http://', 'https://')):
            logger.error("URL 格式不正確")
            return False
        return True

class ChunkModel(BaseModel):
    """文章塊模型 - 對應 article_chunks 表"""
    
    def __init__(self, article_id: str, content: str, chunk_index: int, 
                 embedding: List[float] = None, metadata: Dict[str, Any] = None):
        super().__init__()
        self.article_id = article_id
        self.content = content
        self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        self.embedding = embedding
        self.chunk_index = chunk_index
        self.chunk_size = len(content)
        self.metadata = metadata or {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkModel':
        """從字典創建實例"""
        chunk = cls(
            article_id=data["article_id"],
            content=data["content"],
            chunk_index=data["chunk_index"],
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {})
        )
        
        if "id" in data:
            chunk.id = data["id"]
        if "created_at" in data:
            if isinstance(data["created_at"], str):
                chunk.created_at = datetime.fromisoformat(data["created_at"])
            else:
                chunk.created_at = data["created_at"]
        if "content_hash" in data:
            chunk.content_hash = data["content_hash"]
        if "chunk_size" in data:
            chunk.chunk_size = data["chunk_size"]
            
        return chunk
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.article_id:
            logger.error("文章 ID 不能為空")
            return False
        if not self.content:
            logger.error("內容不能為空")
            return False
        if self.chunk_index < 0:
            logger.error("塊索引不能為負數")
            return False
        if self.embedding and len(self.embedding) != 1024:
            logger.error("嵌入向量維度必須為 1024")
            return False
        return True

class SitemapModel(BaseModel):
    """Sitemap 模型 - 對應 sitemaps 表"""
    
    def __init__(self, url: str, domain: str = None, 
                 status: Union[CrawlStatus, str] = CrawlStatus.PENDING,
                 urls_count: int = 0, parsed_at: datetime = None,
                 error_message: str = None, metadata: Dict[str, Any] = None):
        super().__init__()
        self.url = url
        self.domain = domain or urlparse(url).netloc
        self.status = status if isinstance(status, CrawlStatus) else CrawlStatus(status)
        self.urls_count = urls_count
        self.parsed_at = parsed_at
        self.error_message = error_message
        self.metadata = metadata or {}
        self.updated_at = datetime.now()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SitemapModel':
        """從字典創建實例"""
        parsed_at = None
        if data.get("parsed_at"):
            if isinstance(data["parsed_at"], str):
                try:
                    parsed_at = datetime.fromisoformat(data["parsed_at"])
                except ValueError:
                    parsed_at = None
            elif isinstance(data["parsed_at"], datetime):
                parsed_at = data["parsed_at"]
        
        sitemap = cls(
            url=data["url"],
            domain=data.get("domain"),
            status=data.get("status", "pending"),
            urls_count=data.get("urls_count", 0),
            parsed_at=parsed_at,
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {})
        )
        
        if "id" in data:
            sitemap.id = data["id"]
        if "created_at" in data:
            if isinstance(data["created_at"], str):
                sitemap.created_at = datetime.fromisoformat(data["created_at"])
            else:
                sitemap.created_at = data["created_at"]
        if "updated_at" in data:
            if isinstance(data["updated_at"], str):
                sitemap.updated_at = datetime.fromisoformat(data["updated_at"])
            else:
                sitemap.updated_at = data["updated_at"]
                
        return sitemap
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.url:
            logger.error("Sitemap URL 不能為空")
            return False
        if not self.url.startswith(('http://', 'https://')):
            logger.error("Sitemap URL 格式不正確")
            return False
        return True

# 模型工廠類別
class ModelFactory:
    """模型工廠類別，用於統一創建和管理模型"""
    
    @staticmethod
    def create_discovered_url(url: str, **kwargs) -> DiscoveredURLModel:
        """創建發現的 URL 模型"""
        return DiscoveredURLModel(url=url, **kwargs)
    
    @staticmethod
    def create_article(url: str, **kwargs) -> ArticleModel:
        """創建文章模型"""
        return ArticleModel(url=url, **kwargs)
    
    @staticmethod
    def create_chunk(article_id: str, content: str, chunk_index: int, **kwargs) -> ChunkModel:
        """創建文章塊模型"""
        return ChunkModel(article_id=article_id, content=content, chunk_index=chunk_index, **kwargs)
    
    @staticmethod
    def create_sitemap(url: str, **kwargs) -> SitemapModel:
        """創建 Sitemap 模型"""
        return SitemapModel(url=url, **kwargs)

# 實用函數
def get_model_by_name(model_name: str):
    """根據名稱獲取模型類別"""
    models = {
        'discovered_url': DiscoveredURLModel,
        'article': ArticleModel,
        'chunk': ChunkModel,
        'sitemap': SitemapModel
    }
    return models.get(model_name.lower())

def validate_all_models(*models) -> bool:
    """批次驗證多個模型"""
    return all(model.validate() for model in models if model)

# 導出所有核心類別
__all__ = [
    'CrawlStatus',
    'ChangeFreq', 
    'BaseModel',
    'DiscoveredURLModel',
    'ArticleModel', 
    'ChunkModel',
    'SitemapModel',
    'ModelFactory',
    'get_model_by_name',
    'validate_all_models'
]
