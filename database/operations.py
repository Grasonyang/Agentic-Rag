"""
Supabase 資料庫操作 - 精簡版
只支援核心的 4 個表格操作
對應 schema.sql 和 models.py
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from supabase import Client
from .client import SupabaseClient
from .models import (
    ArticleModel, ChunkModel, SitemapModel, DiscoveredURLModel,
    CrawlStatus, ChangeFreq, ModelFactory
)

logger = logging.getLogger(__name__)

class DatabaseOperations:
    """
    精簡版資料庫操作管理類別
    只包含核心 4 個表格的 CRUD 操作
    """
    
    def __init__(self, client: Client):
        """
        初始化資料庫操作
        
        Args:
            client: Supabase 客戶端實例
        """
        self.client = client
    
    # ==================== DiscoveredURL 操作 ====================
    
    def create_discovered_url(self, url_model: DiscoveredURLModel) -> bool:
        """創建發現的 URL 記錄"""
        try:
            if not url_model.validate():
                return False
            
            response = self.client.table("discovered_urls").insert(url_model.to_dict()).execute()
            
            if response.data:
                logger.info(f"成功創建 URL 記錄: {url_model.url}")
                return True
            else:
                logger.error("創建 URL 記錄失敗")
                return False
                
        except Exception as e:
            logger.error(f"創建 URL 記錄時發生錯誤: {e}")
            return False
    
    def bulk_create_discovered_urls(self, url_models: List[DiscoveredURLModel]) -> int:
        """批量創建發現的 URL 記錄"""
        try:
            if not url_models:
                return 0
            
            # 驗證所有模型
            valid_urls = [url for url in url_models if url.validate()]
            if not valid_urls:
                logger.warning("沒有有效的 URL 模型")
                return 0
            
            # 轉換為字典格式
            urls_data = [url.to_dict() for url in valid_urls]
            
            response = self.client.table("discovered_urls").insert(urls_data).execute()
            
            if response.data:
                count = len(response.data)
                logger.info(f"成功批量創建 {count} 個 URL 記錄")
                return count
            else:
                logger.error("批量創建 URL 記錄失敗")
                return 0
                
        except Exception as e:
            logger.error(f"批量創建 URL 記錄時發生錯誤: {e}")
            return 0
    
    def get_pending_urls(self, limit: Optional[int] = 100) -> List[DiscoveredURLModel]:
        """獲取待爬取的 URL (狀態為 pending 或 null)"""
        try:
            # 同時查詢 'pending' 狀態或 crawl_status 為 NULL 的記錄
            # 這能確保新發現的 URL (預設為 NULL) 也會被處理
            filter_query = f"""crawl_status.eq.{CrawlStatus.PENDING.value},crawl_status.is.null"""
            query = (self.client.table("discovered_urls")
                       .select("*")
                       .or_(filter_query))

            if limit is not None:
                query = query.limit(limit)

            response = query.execute()

            if response.data:
                return [DiscoveredURLModel.from_dict(data) for data in response.data]
            else:
                return []

        except Exception as e:
            logger.error(f"獲取待爬取 URL 時發生錯誤: {e}")
            return []
    
    def update_crawl_status(self, url_id: str, status: CrawlStatus, error_message: str = None) -> bool:
        """更新爬取狀態"""
        try:
            update_data = {
                "crawl_status": status.value,
                "updated_at": datetime.now().isoformat()
            }
            
            if status == CrawlStatus.CRAWLING:
                update_data["crawl_attempts"] = self.client.table("discovered_urls").select("crawl_attempts").eq("id", url_id).execute().data[0]["crawl_attempts"] + 1
            elif status in [CrawlStatus.COMPLETED, CrawlStatus.ERROR]:
                update_data["last_crawl_at"] = datetime.now().isoformat()
            
            if error_message and status == CrawlStatus.ERROR:
                update_data["error_message"] = error_message
            
            response = (self.client.table("discovered_urls")
                       .update(update_data)
                       .eq("id", url_id)
                       .execute())
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"更新爬取狀態時發生錯誤: {e}")
            return False
    
    # ==================== Article 操作 ====================
    
    def create_article(self, article: ArticleModel) -> bool:
        """創建新文章"""
        try:
            if not article.validate():
                return False
            
            # 檢查 URL 是否已存在
            existing = self.client.table("articles").select("id").eq("url", article.url).execute()
            if existing.data:
                logger.warning(f"文章 URL 已存在: {article.url}")
                return False
            
            response = self.client.table("articles").insert(article.to_dict()).execute()
            
            if response.data:
                logger.info(f"成功創建文章: {article.title}")
                return True
            else:
                logger.error("創建文章失敗")
                return False
                
        except Exception as e:
            logger.error(f"創建文章時發生錯誤: {e}")
            return False
    
    def get_article_by_url(self, url: str) -> Optional[ArticleModel]:
        """根據 URL 獲取文章"""
        try:
            response = (self.client.table("articles")
                       .select("*")
                       .eq("url", url)
                       .execute())
            
            if response.data:
                return ArticleModel.from_dict(response.data[0])
            else:
                return None
                
        except Exception as e:
            logger.error(f"獲取文章時發生錯誤: {e}")
            return None
    
    # ==================== Chunk 操作 ====================
    
    def create_chunks(self, chunks: List[ChunkModel]) -> int:
        """批量創建文章塊"""
        try:
            if not chunks:
                return 0
            
            # 驗證所有塊
            valid_chunks = [chunk for chunk in chunks if chunk.validate()]
            if not valid_chunks:
                logger.warning("沒有有效的文章塊")
                return 0
            
            # 轉換為字典格式
            chunks_data = [chunk.to_dict() for chunk in valid_chunks]
            
            response = self.client.table("article_chunks").insert(chunks_data).execute()
            
            if response.data:
                count = len(response.data)
                logger.info(f"成功創建 {count} 個文章塊")
                return count
            else:
                logger.error("創建文章塊失敗")
                return 0
                
        except Exception as e:
            logger.error(f"創建文章塊時發生錯誤: {e}")
            return 0
    
    def search_similar_chunks(self, embedding: List[float], limit: int = 10, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        try:
            # 使用 SQL 函數進行向量搜索
            query = f"""
            SELECT * FROM search_similar_content(
                '{embedding}'::vector(1024),
                {threshold},
                {limit}
            )
            """
            
            response = self.client.rpc("search_similar_content", {
                "query_embedding": embedding,
                "similarity_threshold": threshold,
                "limit_count": limit
            }).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"向量搜索時發生錯誤: {e}")
            return []
    
    # ==================== Sitemap 操作 ====================
    
    def create_sitemap(self, sitemap: SitemapModel) -> bool:
        """創建 Sitemap 記錄"""
        try:
            if not sitemap.validate():
                return False
            
            response = self.client.table("sitemaps").insert(sitemap.to_dict()).execute()
            
            if response.data:
                logger.info(f"成功創建 Sitemap 記錄: {sitemap.url}")
                return True
            else:
                logger.error("創建 Sitemap 記錄失敗")
                return False
                
        except Exception as e:
            logger.error(f"創建 Sitemap 記錄時發生錯誤: {e}")
            return False
    
    def update_sitemap_status(self, sitemap_id: str, status: CrawlStatus, 
                             urls_count: int = None, error_message: str = None) -> bool:
        """更新 Sitemap 狀態"""
        try:
            update_data = {
                "status": status.value,
                "updated_at": datetime.now().isoformat()
            }
            
            if status == CrawlStatus.COMPLETED:
                update_data["parsed_at"] = datetime.now().isoformat()
            
            if urls_count is not None:
                update_data["urls_count"] = urls_count
            
            if error_message and status == CrawlStatus.ERROR:
                update_data["error_message"] = error_message
            
            response = (self.client.table("sitemaps")
                       .update(update_data)
                       .eq("id", sitemap_id)
                       .execute())
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"更新 Sitemap 狀態時發生錯誤: {e}")
            return False
    
    # ==================== 統計和監控 ====================
    
    def get_crawl_progress(self) -> Dict[str, Any]:
        """獲取爬取進度統計"""
        try:
            response = self.client.rpc("get_crawl_progress").execute()
            
            if response.data:
                return response.data[0]
            else:
                return {}
                
        except Exception as e:
            logger.error(f"獲取爬取進度時發生錯誤: {e}")
            return {}
    
    def get_domain_stats(self) -> List[Dict[str, Any]]:
        """獲取域名統計"""
        try:
            response = self.client.rpc("get_domain_stats").execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"獲取域名統計時發生錯誤: {e}")
            return []
    
    def check_data_integrity(self) -> List[Dict[str, Any]]:
        """檢查數據完整性"""
        try:
            response = self.client.rpc("check_data_integrity").execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"檢查數據完整性時發生錯誤: {e}")
            return []
    
    def cleanup_duplicate_articles(self) -> Dict[str, int]:
        """清理重複文章"""
        try:
            response = self.client.rpc("cleanup_duplicate_articles").execute()
            
            if response.data:
                result = response.data[0]
                return {
                    "deleted_articles": result.get("deleted_articles", 0),
                    "deleted_chunks": result.get("deleted_chunks", 0)
                }
            else:
                return {"deleted_articles": 0, "deleted_chunks": 0}
                
        except Exception as e:
            logger.error(f"清理重複文章時發生錯誤: {e}")
            return {"deleted_articles": 0, "deleted_chunks": 0}
    
    # ==================== 實用方法 ====================
    
    def clear_all_data(self) -> bool:
        """清空所有數據"""
        try:
            # 按依賴順序刪除
            tables = ["article_chunks", "articles", "discovered_urls", "sitemaps"]
            
            for table in tables:
                response = self.client.table(table).delete().neq("id", "").execute()
                logger.info(f"已清空表格: {table}")
            
            return True
            
        except Exception as e:
            logger.error(f"清空數據時發生錯誤: {e}")
            return False
    
    def get_table_count(self, table_name: str) -> int:
        """獲取表格記錄數"""
        try:
            response = self.client.table(table_name).select("id", count="exact").execute()
            return response.count if response.count is not None else 0
            
        except Exception as e:
            logger.error(f"獲取表格記錄數時發生錯誤: {e}")
            return 0

# 便捷函數
def get_database_operations() -> Optional[DatabaseOperations]:
    """獲取資料庫操作實例"""
    try:
        db_client = SupabaseClient()
        client = db_client.get_client()
        if client:
            return DatabaseOperations(client)
        else:
            return None
    except Exception as e:
        logger.error(f"初始化資料庫操作時發生錯誤: {e}")
        return None
