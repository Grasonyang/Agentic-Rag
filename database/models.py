"""
資料庫模型定義
定義所有資料表的結構和相關操作
統一使用 UUID 作為主鍵，向量維度為 1024
"""

import uuid
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)

class CrawlStatus(Enum):
    """爬取狀態枚舉"""
    PENDING = "pending"          # 待爬取
    CRAWLING = "crawling"        # 爬取中
    COMPLETED = "completed"      # 成功
    ERROR = "error"              # 失敗
    SKIPPED = "skipped"          # 跳過

class SitemapType(Enum):
    """Sitemap 類型枚舉"""
    SITEMAP = "sitemap"              # 普通 sitemap
    SITEMAPINDEX = "sitemapindex"    # sitemap 索引
    URLSET = "urlset"                # URL 集合

class URLType(Enum):
    """URL 類型枚舉"""
    CONTENT = "content"      # 內容頁面
    SITEMAP = "sitemap"      # sitemap 文件
    OTHER = "other"          # 其他類型

class BaseModel:
    """基礎模型類別"""
    
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "id": self.id,
            "created_at": self.created_at
        }

class ArticleModel(BaseModel):
    """文章模型 (使用 UUID)"""
    
    def __init__(self, url: str, title: str = "", content: str = "", metadata: Dict[str, Any] = None):
        super().__init__()
        self.url = url
        self.title = title
        self.content = content
        self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest() if content else ""
        self.word_count = len(content.split()) if content else 0
        self.metadata = metadata or {}
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = super().to_dict()
        data.update({
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "content_hash": self.content_hash,
            "word_count": self.word_count,
            "metadata": self.metadata,
            "updated_at": self.updated_at
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArticleModel':
        """從字典創建實例"""
        article = cls(
            url=data["url"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            metadata=data.get("metadata", {})
        )
        if "id" in data:
            article.id = data["id"]
        if "created_at" in data:
            article.created_at = data["created_at"]
        if "updated_at" in data:
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

class SitemapModel(BaseModel):
    """Sitemap 模型"""
    
    def __init__(self, url: str, sitemap_type: SitemapType = SitemapType.SITEMAP, 
                 status: CrawlStatus = CrawlStatus.PENDING, title: str = "", 
                 description: str = "", lastmod: datetime = None, 
                 changefreq: str = None, priority: float = None, 
                 urls_count: int = 0, metadata: Dict[str, Any] = None):
        super().__init__()
        self.url = url
        self.type = sitemap_type.value if isinstance(sitemap_type, SitemapType) else sitemap_type
        self.status = status.value if isinstance(status, CrawlStatus) else status
        self.title = title
        self.description = description
        self.lastmod = lastmod.isoformat() if lastmod else None
        self.changefreq = changefreq
        self.priority = priority
        self.urls_count = urls_count
        self.parsed_at = None
        self.error_message = None
        self.metadata = metadata or {}
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = super().to_dict()
        data.update({
            "url": self.url,
            "type": self.type,
            "status": self.status,
            "title": self.title,
            "description": self.description,
            "lastmod": self.lastmod,
            "changefreq": self.changefreq,
            "priority": self.priority,
            "urls_count": self.urls_count,
            "parsed_at": self.parsed_at,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "updated_at": self.updated_at
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SitemapModel':
        """從字典創建實例"""
        lastmod = None
        if data.get("lastmod"):
            if isinstance(data["lastmod"], str):
                lastmod = datetime.fromisoformat(data["lastmod"].replace('Z', '+00:00'))
            else:
                lastmod = data["lastmod"]
        
        sitemap = cls(
            url=data["url"],
            sitemap_type=data.get("type", "sitemap"),
            status=data.get("status", "pending"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            lastmod=lastmod,
            changefreq=data.get("changefreq"),
            priority=data.get("priority"),
            urls_count=data.get("urls_count", 0),
            metadata=data.get("metadata", {})
        )
        if "id" in data:
            sitemap.id = data["id"]
        if "created_at" in data:
            sitemap.created_at = data["created_at"]
        if "updated_at" in data:
            sitemap.updated_at = data["updated_at"]
        if "parsed_at" in data:
            sitemap.parsed_at = data["parsed_at"]
        if "error_message" in data:
            sitemap.error_message = data["error_message"]
        return sitemap
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.url:
            logger.error("Sitemap URL 不能為空")
            return False
        if not self.url.startswith(('http://', 'https://')):
            logger.error("Sitemap URL 格式不正確")
            return False
        if self.priority is not None and (self.priority < 0.0 or self.priority > 1.0):
            logger.error("優先級必須在 0.0 到 1.0 之間")
            return False
        return True

class DiscoveredURLModel(BaseModel):
    """發現的 URL 模型"""
    
    def __init__(self, url: str, source_sitemap_id: str, url_type: URLType = URLType.CONTENT,
                 priority: float = None, changefreq: str = None, lastmod: datetime = None,
                 crawl_status: CrawlStatus = CrawlStatus.PENDING, metadata: Dict[str, Any] = None):
        super().__init__()
        self.url = url
        self.source_sitemap_id = source_sitemap_id
        self.url_type = url_type.value if isinstance(url_type, URLType) else url_type
        self.priority = priority
        self.changefreq = changefreq
        self.lastmod = lastmod.isoformat() if lastmod else None
        self.crawl_status = crawl_status.value if isinstance(crawl_status, CrawlStatus) else crawl_status
        self.crawl_attempts = 0
        self.last_crawl_at = None
        self.error_message = None
        self.article_id = None
        self.metadata = metadata or {}
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = super().to_dict()
        data.update({
            "url": self.url,
            "source_sitemap_id": self.source_sitemap_id,
            "url_type": self.url_type,
            "priority": self.priority,
            "changefreq": self.changefreq,
            "lastmod": self.lastmod,
            "crawl_status": self.crawl_status,
            "crawl_attempts": self.crawl_attempts,
            "last_crawl_at": self.last_crawl_at,
            "error_message": self.error_message,
            "article_id": self.article_id,
            "metadata": self.metadata,
            "updated_at": self.updated_at
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiscoveredURLModel':
        """從字典創建實例"""
        lastmod = None
        if data.get("lastmod"):
            if isinstance(data["lastmod"], str):
                lastmod = datetime.fromisoformat(data["lastmod"].replace('Z', '+00:00'))
            else:
                lastmod = data["lastmod"]
        
        url_model = cls(
            url=data["url"],
            source_sitemap_id=data["source_sitemap_id"],
            url_type=data.get("url_type", "content"),
            priority=data.get("priority"),
            changefreq=data.get("changefreq"),
            lastmod=lastmod,
            crawl_status=data.get("crawl_status", "pending"),
            metadata=data.get("metadata", {})
        )
        if "id" in data:
            url_model.id = data["id"]
        if "created_at" in data:
            url_model.created_at = data["created_at"]
        if "updated_at" in data:
            url_model.updated_at = data["updated_at"]
        if "crawl_attempts" in data:
            url_model.crawl_attempts = data["crawl_attempts"]
        if "last_crawl_at" in data:
            url_model.last_crawl_at = data["last_crawl_at"]
        if "error_message" in data:
            url_model.error_message = data["error_message"]
        if "article_id" in data:
            url_model.article_id = data["article_id"]
        return url_model
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.url:
            logger.error("URL 不能為空")
            return False
        if not self.url.startswith(('http://', 'https://')):
            logger.error("URL 格式不正確")
            return False
        if not self.source_sitemap_id:
            logger.error("來源 Sitemap ID 不能為空")
            return False
        if self.priority is not None and (self.priority < 0.0 or self.priority > 1.0):
            logger.error("優先級必須在 0.0 到 1.0 之間")
            return False
        return True

class RobotsTxtModel(BaseModel):
    """robots.txt 模型"""
    
    def __init__(self, domain: str, robots_url: str, content: str, 
                 sitemaps_count: int = 0, rules_count: int = 0, 
                 metadata: Dict[str, Any] = None):
        super().__init__()
        self.domain = domain
        self.robots_url = robots_url
        self.content = content
        self.parsed_at = self.created_at
        self.sitemaps_count = sitemaps_count
        self.rules_count = rules_count
        self.metadata = metadata or {}
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = super().to_dict()
        data.update({
            "domain": self.domain,
            "robots_url": self.robots_url,
            "content": self.content,
            "parsed_at": self.parsed_at,
            "sitemaps_count": self.sitemaps_count,
            "rules_count": self.rules_count,
            "metadata": self.metadata,
            "updated_at": self.updated_at
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RobotsTxtModel':
        """從字典創建實例"""
        robots = cls(
            domain=data["domain"],
            robots_url=data["robots_url"],
            content=data["content"],
            sitemaps_count=data.get("sitemaps_count", 0),
            rules_count=data.get("rules_count", 0),
            metadata=data.get("metadata", {})
        )
        if "id" in data:
            robots.id = data["id"]
        if "created_at" in data:
            robots.created_at = data["created_at"]
        if "updated_at" in data:
            robots.updated_at = data["updated_at"]
        if "parsed_at" in data:
            robots.parsed_at = data["parsed_at"]
        return robots
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.domain:
            logger.error("域名不能為空")
            return False
        if not self.robots_url:
            logger.error("robots.txt URL 不能為空")
            return False
        if not self.content:
            logger.error("robots.txt 內容不能為空")
            return False
        return True

class ChunkModel(BaseModel):
    """文章塊模型 (使用 UUID)"""
    
    def __init__(self, article_id: str, content: str, chunk_index: int, 
                 embedding: List[float] = None, metadata: Dict[str, Any] = None,
                 start_position: int = 0, end_position: int = 0):
        super().__init__()
        self.article_id = article_id
        self.content = content
        self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        self.chunk_index = chunk_index
        self.chunk_size = len(content)
        self.start_position = start_position
        self.end_position = end_position
        self.embedding = embedding
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = super().to_dict()
        data.update({
            "article_id": self.article_id,
            "content": self.content,
            "content_hash": self.content_hash,
            "chunk_index": self.chunk_index,
            "chunk_size": self.chunk_size,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "embedding": self.embedding,
            "metadata": self.metadata
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkModel':
        """從字典創建實例"""
        chunk = cls(
            article_id=data["article_id"],
            content=data["content"],
            chunk_index=data["chunk_index"],
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            start_position=data.get("start_position", 0),
            end_position=data.get("end_position", 0)
        )
        if "id" in data:
            chunk.id = data["id"]
        if "created_at" in data:
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

class SearchLogModel(BaseModel):
    """搜索日誌模型 (使用 UUID)"""
    
    def __init__(self, query: str, results_count: int = 0, response_time_ms: int = 0, 
                 search_type: str = "semantic", user_agent: str = "", ip_address: str = "",
                 session_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__()
        self.query = query
        self.query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
        self.results_count = results_count
        self.response_time_ms = response_time_ms
        self.search_type = search_type
        self.user_agent = user_agent
        self.ip_address = ip_address
        self.session_id = session_id or str(uuid.uuid4())
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = super().to_dict()
        data.update({
            "query": self.query,
            "query_hash": self.query_hash,
            "results_count": self.results_count,
            "response_time_ms": self.response_time_ms,
            "search_type": self.search_type,
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "metadata": self.metadata
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchLogModel':
        """從字典創建實例"""
        log = cls(
            query=data["query"],
            results_count=data.get("results_count", 0),
            response_time_ms=data.get("response_time_ms", 0),
            search_type=data.get("search_type", "semantic"),
            user_agent=data.get("user_agent", ""),
            ip_address=data.get("ip_address", ""),
            session_id=data.get("session_id"),
            metadata=data.get("metadata", {})
        )
        if "id" in data:
            log.id = data["id"]
        if "created_at" in data:
            log.created_at = data["created_at"]
        if "query_hash" in data:
            log.query_hash = data["query_hash"]
        return log

class EmbeddingCacheModel(BaseModel):
    """嵌入快取模型 (新增)"""
    
    def __init__(self, content_hash: str, embedding: List[float], model_name: str,
                 content_preview: str = "", model_version: str = ""):
        super().__init__()
        self.content_hash = content_hash
        self.content_preview = content_preview[:200] + "..." if len(content_preview) > 200 else content_preview
        self.embedding = embedding
        self.model_name = model_name
        self.model_version = model_version
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        data = super().to_dict()
        data.update({
            "content_hash": self.content_hash,
            "content_preview": self.content_preview,
            "embedding": self.embedding,
            "model_name": self.model_name,
            "model_version": self.model_version
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmbeddingCacheModel':
        """從字典創建實例"""
        cache = cls(
            content_hash=data["content_hash"],
            embedding=data["embedding"],
            model_name=data["model_name"],
            content_preview=data.get("content_preview", ""),
            model_version=data.get("model_version", "")
        )
        if "id" in data:
            cache.id = data["id"]
        if "created_at" in data:
            cache.created_at = data["created_at"]
        return cache
    
    def validate(self) -> bool:
        """驗證模型數據"""
        if not self.content_hash:
            logger.error("內容雜湊不能為空")
            return False
        if not self.embedding:
            logger.error("嵌入向量不能為空")
            return False
        if len(self.embedding) != 1024:
            logger.error("嵌入向量維度必須為 1024")
            return False
        if not self.model_name:
            logger.error("模型名稱不能為空")
            return False
        return True
