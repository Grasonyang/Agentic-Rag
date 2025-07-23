"""
Supabase 資料庫操作
負責 CRUD 操作和業務邏輯
支援 UUID 主鍵和 1024 維向量
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from supabase import Client
from .client import SupabaseClient
from .models import (
    ArticleModel, ChunkModel, SearchLogModel, EmbeddingCacheModel,
    SitemapModel, DiscoveredURLModel, RobotsTxtModel,
    CrawlStatus, SitemapType, URLType
)

logger = logging.getLogger(__name__)

class DatabaseOperations:
    """
    資料庫操作管理類別
    包含所有 CRUD 操作和高階查詢功能
    支援 UUID 主鍵和向量搜索
    """
    
    def __init__(self, client: Client):
        """
        初始化資料庫操作
        
        Args:
            client: Supabase 客戶端實例
        """
        self.client = client
    
    # ==================== 文章操作 ====================
    
    def create_article(self, article: ArticleModel) -> bool:
        """
        創建新文章
        
        Args:
            article: 文章模型實例
            
        Returns:
            bool: 創建成功返回 True，否則返回 False
        """
        try:
            if not article.validate():
                return False
            
            # 檢查 URL 是否已存在
            if self.article_exists(article.url):
                logger.warning(f"文章 URL 已存在: {article.url}")
                return False
            
            response = self.client.table("articles").insert(article.to_dict()).execute()
            
            if response.data:
                logger.info(f"成功創建文章: {article.title} (ID: {article.id})")
                return True
            else:
                logger.error("創建文章失敗")
                return False
                
        except Exception as e:
            logger.error(f"創建文章時發生錯誤: {e}")
            return False
    
    def get_article_by_id(self, article_id: str) -> Optional[ArticleModel]:
        """
        根據 UUID 獲取文章
        
        Args:
            article_id: 文章 UUID
            
        Returns:
            ArticleModel: 文章實例，未找到時返回 None
        """
        try:
            response = self.client.table("articles").select("*").eq("id", article_id).execute()
            
            if response.data:
                return ArticleModel.from_dict(response.data[0])
            else:
                logger.info(f"未找到文章: {article_id}")
                return None
                
        except Exception as e:
            logger.error(f"獲取文章時發生錯誤: {e}")
            return None
    
    def get_article_by_url(self, url: str) -> Optional[ArticleModel]:
        """
        根據 URL 獲取文章
        
        Args:
            url: 文章 URL
            
        Returns:
            ArticleModel: 文章實例，未找到時返回 None
        """
        try:
            response = self.client.table("articles").select("*").eq("url", url).execute()
            
            if response.data:
                return ArticleModel.from_dict(response.data[0])
            else:
                return None
                
        except Exception as e:
            logger.error(f"根據 URL 獲取文章時發生錯誤: {e}")
            return None
    
    def article_exists(self, url: str) -> bool:
        """
        檢查文章是否已存在
        
        Args:
            url: 文章 URL
            
        Returns:
            bool: 存在返回 True，否則返回 False
        """
        try:
            response = self.client.table("articles").select("id").eq("url", url).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"檢查文章是否存在時發生錯誤: {e}")
            return False
    
    def search_articles(self, query: str, limit: int = 10) -> List[ArticleModel]:
        """
        搜索文章
        
        Args:
            query: 搜索查詢
            limit: 結果數量限制
            
        Returns:
            List[ArticleModel]: 文章列表
        """
        try:
            # 使用全文搜索
            response = (self.client.table("articles")
                       .select("*")
                       .or_(f"title.ilike.%{query}%,content.ilike.%{query}%")
                       .limit(limit)
                       .execute())
            
            articles = [ArticleModel.from_dict(data) for data in response.data]
            logger.info(f"搜索到 {len(articles)} 篇文章")
            return articles
            
        except Exception as e:
            logger.error(f"搜索文章時發生錯誤: {e}")
            return []
    
    def update_article(self, article_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新文章
        
        Args:
            article_id: 文章 UUID
            updates: 更新的字段
            
        Returns:
            bool: 更新成功返回 True，否則返回 False
        """
        try:
            # 添加更新時間
            updates["updated_at"] = "now()"
            
            response = self.client.table("articles").update(updates).eq("id", article_id).execute()
            
            if response.data:
                logger.info(f"成功更新文章: {article_id}")
                return True
            else:
                logger.error(f"更新文章失敗: {article_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新文章時發生錯誤: {e}")
            return False
    
    def delete_article(self, article_id: str) -> bool:
        """
        刪除文章（會級聯刪除相關的文章塊）
        
        Args:
            article_id: 文章 UUID
            
        Returns:
            bool: 刪除成功返回 True，否則返回 False
        """
        try:
            response = self.client.table("articles").delete().eq("id", article_id).execute()
            
            if response.data:
                logger.info(f"成功刪除文章: {article_id}")
                return True
            else:
                logger.error(f"刪除文章失敗: {article_id}")
                return False
                
        except Exception as e:
            logger.error(f"刪除文章時發生錯誤: {e}")
            return False
    
    # ==================== 文章塊操作 ====================
    
    def create_chunks(self, chunks: List[ChunkModel]) -> bool:
        """
        批量創建文章塊
        
        Args:
            chunks: 文章塊列表
            
        Returns:
            bool: 創建成功返回 True，否則返回 False
        """
        try:
            # 驗證所有塊
            for chunk in chunks:
                if not chunk.validate():
                    return False
            
            chunk_data = [chunk.to_dict() for chunk in chunks]
            response = self.client.table("article_chunks").insert(chunk_data).execute()
            
            if response.data:
                logger.info(f"成功創建 {len(response.data)} 個文章塊")
                return True
            else:
                logger.error("創建文章塊失敗")
                return False
                
        except Exception as e:
            logger.error(f"創建文章塊時發生錯誤: {e}")
            return False
    
    def get_article_chunks(self, article_id: str, order_by: str = "chunk_index") -> List[ChunkModel]:
        """
        獲取文章的所有塊
        
        Args:
            article_id: 文章 UUID
            order_by: 排序字段
            
        Returns:
            List[ChunkModel]: 文章塊列表
        """
        try:
            response = (self.client.table("article_chunks")
                       .select("*")
                       .eq("article_id", article_id)
                       .order(order_by)
                       .execute())
            
            chunks = [ChunkModel.from_dict(data) for data in response.data]
            logger.info(f"獲取到 {len(chunks)} 個文章塊")
            return chunks
            
        except Exception as e:
            logger.error(f"獲取文章塊時發生錯誤: {e}")
            return []
    
    def update_chunk_embedding(self, chunk_id: str, embedding: List[float]) -> bool:
        """
        更新文章塊的嵌入向量
        
        Args:
            chunk_id: 文章塊 UUID
            embedding: 1024 維嵌入向量
            
        Returns:
            bool: 更新成功返回 True，否則返回 False
        """
        try:
            # 確保嵌入向量是正確的維度
            if len(embedding) != 1024:
                logger.error(f"嵌入向量維度錯誤: {len(embedding)}，應該是 1024")
                return False
            
            # 確保 embedding 是 Python list 而不是 numpy array
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            
            response = (self.client.table("article_chunks")
                       .update({"embedding": embedding})
                       .eq("id", chunk_id)
                       .execute())
            
            if response.data:
                logger.info(f"成功更新文章塊嵌入: {chunk_id}")
                return True
            else:
                logger.error(f"更新文章塊嵌入失敗: {chunk_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新文章塊嵌入時發生錯誤: {e}")
            return False
    
    def similarity_search(self, query_embedding: List[float], limit: int = 10, threshold: float = 0.8) -> List[Tuple[ChunkModel, float]]:
        """
        向量相似度搜索
        
        Args:
            query_embedding: 查詢向量
            limit: 結果數量限制
            threshold: 相似度閾值
            
        Returns:
            List[Tuple[ChunkModel, float]]: (文章塊, 相似度分數) 的列表
        """
        try:
            # 確保 query_embedding 是 Python list 而不是 numpy array
            if hasattr(query_embedding, 'tolist'):
                query_embedding = query_embedding.tolist()
            
            # 使用 RPC 函數進行向量搜索
            response = (self.client.rpc("match_chunks", {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": limit
            }).execute())
            
            results = []
            for data in response.data:
                chunk = ChunkModel.from_dict(data)
                similarity = data.get("similarity", 0.0)
                results.append((chunk, similarity))
            
            logger.info(f"向量搜索返回 {len(results)} 個結果")
            return results
            
        except Exception as e:
            logger.error(f"向量搜索時發生錯誤: {e}")
            return []
    
    # ==================== 搜索日誌操作 ====================
    
    def log_search(self, search_log: SearchLogModel) -> bool:
        """
        記錄搜索日誌
        
        Args:
            search_log: 搜索日誌實例
            
        Returns:
            bool: 記錄成功返回 True，否則返回 False
        """
        try:
            response = self.client.table("search_logs").insert(search_log.to_dict()).execute()
            
            if response.data:
                logger.debug(f"成功記錄搜索日誌: {search_log.query}")
                return True
            else:
                logger.error("記錄搜索日誌失敗")
                return False
                
        except Exception as e:
            logger.error(f"記錄搜索日誌時發生錯誤: {e}")
            return False
    
    # ==================== 統計和分析 ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        獲取資料庫統計信息
        
        Returns:
            Dict[str, Any]: 統計信息字典
        """
        try:
            stats = {}
            
            # 文章數量
            articles_response = self.client.table("articles").select("*", count="exact").limit(1).execute()
            stats["total_articles"] = articles_response.count
            
            # 文章塊數量
            chunks_response = self.client.table("article_chunks").select("*", count="exact").limit(1).execute()
            stats["total_chunks"] = chunks_response.count
            
            # 有嵌入向量的塊數量
            embedded_chunks_response = (self.client.table("article_chunks")
                                      .select("*", count="exact")
                                      .not_.is_("embedding", "null")
                                      .limit(1)
                                      .execute())
            stats["embedded_chunks"] = embedded_chunks_response.count
            
            # 搜索日誌數量
            logs_response = self.client.table("search_logs").select("*", count="exact").limit(1).execute()
            stats["total_searches"] = logs_response.count
            
            logger.info("成功獲取資料庫統計信息")
            return stats
            
        except Exception as e:
            logger.error(f"獲取統計信息時發生錯誤: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 30) -> bool:
        """
        清理舊資料
        
        Args:
            days: 保留天數
            
        Returns:
            bool: 清理成功返回 True，否則返回 False
        """
        try:
            # 清理舊的搜索日誌
            response = (self.client.table("search_logs")
                       .delete()
                       .lt("created_at", f"now() - interval '{days} days'")
                       .execute())
            
            if response.data:
                logger.info(f"成功清理 {len(response.data)} 條舊搜索日誌")
            
            return True
            
        except Exception as e:
            logger.error(f"清理舊資料時發生錯誤: {e}")
            return False
    
    # ==================== 語義搜索 ====================
    
    def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        語義搜索功能 - 使用向量相似度搜索
        
        Args:
            query: 搜索查詢字串
            limit: 返回結果數量限制
            threshold: 相似度閾值
            
        Returns:
            List[Dict]: 搜索結果列表，包含相似度分數
        """
        try:
            from embedding.embedding import EmbeddingManager
            
            # 生成查詢嵌入
            embedder = EmbeddingManager()
            query_embedding = embedder.get_embedding(query)
            
            if query_embedding is None:
                logger.error("無法生成查詢嵌入")
                # 降級到文本搜索
                return self._fallback_text_search(query, limit, threshold)
            
            # 使用向量相似度搜索
            vector_results = self.similarity_search(query_embedding, limit, threshold)
            
            # 轉換結果格式
            results = []
            for chunk, similarity in vector_results:
                # 獲取文章信息
                article = self.get_article_by_id(chunk.article_id)
                
                result = {
                    'id': chunk.id,
                    'content': chunk.content,
                    'similarity': similarity,
                    'article_id': chunk.article_id,
                    'chunk_index': chunk.chunk_index,
                    'article_title': article.title if article else '',
                    'article_url': article.url if article else ''
                }
                results.append(result)
            
            # 記錄搜索
            self._log_search(query, len(results))
            
            logger.info(f"向量語義搜索 '{query}' 返回 {len(results)} 個結果")
            return results
            
        except Exception as e:
            logger.error(f"向量語義搜索失敗: {e}")
            # 降級到文本搜索
            return self._fallback_text_search(query, limit, threshold)
    
    def _fallback_text_search(self, query: str, limit: int = 10, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        降級文本搜索（當向量搜索不可用時使用）
        
        Args:
            query: 搜索查詢字串
            limit: 返回結果數量限制
            threshold: 相似度閾值
            
        Returns:
            List[Dict]: 搜索結果列表
        """
        try:
            logger.info(f"使用降級文本搜索: '{query}'")
            
            # 使用全文搜索和模糊匹配
            response = (self.client.table("article_chunks")
                       .select("*, articles(title, url)")
                       .or_(f"content.ilike.%{query}%,articles.title.ilike.%{query}%")
                       .limit(limit * 2)  # 獲取更多結果進行過濾
                       .execute())
            
            if not response.data:
                logger.info(f"沒有找到與 '{query}' 相關的結果")
                return []
            
            # 處理結果並計算相似度
            results = []
            for chunk in response.data:
                content = chunk.get('content', '')
                similarity = self._calculate_text_similarity(query, content)
                
                if similarity >= threshold:
                    result = {
                        'id': chunk.get('id'),
                        'content': content,
                        'similarity': similarity,
                        'article_id': chunk.get('article_id'),
                        'chunk_index': chunk.get('chunk_index', 0),
                        'article_title': chunk.get('articles', {}).get('title', '') if chunk.get('articles') else '',
                        'article_url': chunk.get('articles', {}).get('url', '') if chunk.get('articles') else ''
                    }
                    results.append(result)
            
            # 按相似度排序
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # 記錄搜索
            self._log_search(query, len(results))
            
            logger.info(f"文本搜索 '{query}' 返回 {len(results)} 個結果")
            return results[:limit]
            
        except Exception as e:
            logger.error(f"文本搜索失敗: {e}")
            return []
    
    def _calculate_text_similarity(self, query: str, text: str) -> float:
        """
        簡化的文本相似度計算
        
        Args:
            query: 查詢字串
            text: 目標文本
            
        Returns:
            float: 相似度分數 (0-1)
        """
        try:
            query_lower = query.lower()
            text_lower = text.lower()
            
            # 簡單的關鍵字匹配計算相似度
            query_words = set(query_lower.split())
            text_words = set(text_lower.split())
            
            if not query_words:
                return 0.0
            
            # 計算交集比例
            intersection = query_words.intersection(text_words)
            similarity = len(intersection) / len(query_words)
            
            # 如果包含完整查詢字串，提高相似度
            if query_lower in text_lower:
                similarity = min(1.0, similarity + 0.3)
            
            return round(similarity, 3)
            
        except Exception as e:
            logger.error(f"計算文本相似度失敗: {e}")
            return 0.0
    
    # ==================== 嵌入快取操作 ====================
    
    def get_cached_embedding(self, content_hash: str) -> Optional[List[float]]:
        """
        從快取獲取嵌入向量
        
        Args:
            content_hash: 內容雜湊值
            
        Returns:
            Optional[List[float]]: 嵌入向量，如果不存在則返回 None
        """
        try:
            response = (self.client.table("embeddings_cache")
                       .select("embedding")
                       .eq("content_hash", content_hash)
                       .execute())
            
            if response.data:
                return response.data[0]["embedding"]
            else:
                return None
                
        except Exception as e:
            logger.error(f"獲取快取嵌入時發生錯誤: {e}")
            return None
    
    def cache_embedding(self, cache_model: EmbeddingCacheModel) -> bool:
        """
        快取嵌入向量
        
        Args:
            cache_model: 嵌入快取模型實例
            
        Returns:
            bool: 快取成功返回 True，否則返回 False
        """
        try:
            if not cache_model.validate():
                return False
            
            # 檢查是否已存在
            existing = self.get_cached_embedding(cache_model.content_hash)
            if existing:
                logger.debug(f"嵌入快取已存在: {cache_model.content_hash}")
                return True
            
            response = self.client.table("embeddings_cache").insert(cache_model.to_dict()).execute()
            
            if response.data:
                logger.debug(f"成功快取嵌入: {cache_model.content_hash}")
                return True
            else:
                logger.error("快取嵌入失敗")
                return False
                
        except Exception as e:
            logger.error(f"快取嵌入時發生錯誤: {e}")
            return False
    
    def cleanup_old_embeddings_cache(self, days: int = 90) -> bool:
        """
        清理舊的嵌入快取
        
        Args:
            days: 保留天數
            
        Returns:
            bool: 清理成功返回 True，否則返回 False
        """
        try:
            response = (self.client.table("embeddings_cache")
                       .delete()
                       .lt("created_at", f"now() - interval '{days} days'")
                       .execute())
            
            if response.data:
                logger.info(f"成功清理 {len(response.data)} 條舊嵌入快取")
            
            return True
            
        except Exception as e:
            logger.error(f"清理舊嵌入快取時發生錯誤: {e}")
            return False
    
    # ==================== 進階語義搜索 ====================
    
    def advanced_semantic_search(self, query: str, limit: int = 10, threshold: float = 0.75) -> List[Dict[str, Any]]:
        """
        進階語義搜索 - 使用新的 semantic_search RPC 函數
        
        Args:
            query: 搜索查詢字串
            limit: 返回結果數量限制
            threshold: 相似度閾值
            
        Returns:
            List[Dict]: 搜索結果列表
        """
        try:
            from embedding.embedding import EmbeddingManager
            
            # 生成查詢嵌入
            embedder = EmbeddingManager()
            query_embedding = embedder.get_embedding(query)
            
            # 確保嵌入向量是 Python list
            if query_embedding is not None and hasattr(query_embedding, 'tolist'):
                query_embedding = query_embedding.tolist()
            
            # 使用新的 semantic_search RPC 函數
            response = (self.client.rpc("semantic_search", {
                "query_text": query,
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": limit
            }).execute())
            
            results = []
            for data in response.data:
                result = {
                    'id': data.get('chunk_id'),
                    'content': data.get('content'),
                    'similarity': data.get('similarity', 0.0),
                    'article_id': data.get('article_id'),
                    'chunk_index': data.get('chunk_index', 0),
                    'article_title': data.get('article_title', ''),
                    'article_url': data.get('article_url', ''),
                    'search_type': data.get('search_type', 'unknown')
                }
                results.append(result)
            
            # 記錄搜索
            search_type = "vector" if query_embedding else "text"
            self._log_search_with_type(query, len(results), search_type)
            
            logger.info(f"進階語義搜索 '{query}' 返回 {len(results)} 個結果")
            return results
            
        except Exception as e:
            logger.error(f"進階語義搜索失敗: {e}")
            # 降級到基本語義搜索
            return self.semantic_search(query, limit, threshold)
    
    def _log_search_with_type(self, query: str, results_count: int, search_type: str) -> None:
        """
        記錄搜索操作（包含搜索類型）
        
        Args:
            query: 搜索查詢
            results_count: 結果數量
            search_type: 搜索類型
        """
        try:
            search_log = SearchLogModel(
                query=query,
                results_count=results_count,
                search_type=search_type
            )
            
            response = (self.client.table("search_logs")
                       .insert(search_log.to_dict())
                       .execute())
            
            if response.data:
                logger.debug(f"搜索日誌已記錄: {query} ({search_type})")
                
        except Exception as e:
            logger.warning(f"記錄搜索日誌失敗: {e}")

    # ==================== 統計和分析 (更新) ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        獲取資料庫統計信息
        
        Returns:
            Dict[str, Any]: 統計信息字典
        """
        try:
            stats = {}
            
            # 嘗試使用 RPC 函數獲取統計
            try:
                response = self.client.rpc("get_database_stats").execute()
                if response.data:
                    for row in response.data:
                        stats[row["table_name"]] = {
                            "count": row["row_count"],
                            "size": row["total_size"]
                        }
                    return stats
            except Exception:
                logger.warning("RPC 統計函數不可用，使用基本統計")
            
            # 基本統計（降級方案）
            # 文章數量
            articles_response = self.client.table("articles").select("*", count="exact").limit(1).execute()
            stats["total_articles"] = articles_response.count
            
            # 文章塊數量
            chunks_response = self.client.table("article_chunks").select("*", count="exact").limit(1).execute()
            stats["total_chunks"] = chunks_response.count
            
            # 有嵌入向量的塊數量
            embedded_chunks_response = (self.client.table("article_chunks")
                                      .select("*", count="exact")
                                      .not_.is_("embedding", "null")
                                      .limit(1)
                                      .execute())
            stats["embedded_chunks"] = embedded_chunks_response.count
            
            # 搜索日誌數量
            logs_response = self.client.table("search_logs").select("*", count="exact").limit(1).execute()
            stats["total_searches"] = logs_response.count
            
            # 嵌入快取數量
            try:
                cache_response = self.client.table("embeddings_cache").select("*", count="exact").limit(1).execute()
                stats["cached_embeddings"] = cache_response.count
            except Exception:
                stats["cached_embeddings"] = 0
            
            logger.info("成功獲取資料庫統計信息")
            return stats
            
        except Exception as e:
            logger.error(f"獲取統計信息時發生錯誤: {e}")
            return {}

    # ==================== SITEMAP 操作 ====================
    
    def create_sitemap(self, sitemap: SitemapModel) -> bool:
        """
        創建新 sitemap
        
        Args:
            sitemap: sitemap 模型實例
            
        Returns:
            bool: 創建成功返回 True，否則返回 False
        """
        try:
            if not sitemap.validate():
                return False
            
            # 檢查 URL 是否已存在
            if self.sitemap_exists(sitemap.url):
                logger.warning(f"Sitemap URL 已存在: {sitemap.url}")
                return True
            
            data = sitemap.to_dict()
            response = self.client.table("sitemaps").insert(data).execute()
            
            if response.data:
                logger.info(f"成功創建 sitemap: {sitemap.url}")
                return True
            
            logger.error("創建 sitemap 失敗: 未返回數據")
            return False
            
        except Exception as e:
            logger.error(f"創建 sitemap 時發生錯誤: {e}")
            return False
    
    def sitemap_exists(self, url: str) -> bool:
        """
        檢查 sitemap 是否存在
        
        Args:
            url: sitemap URL
            
        Returns:
            bool: 存在返回 True，否則返回 False
        """
        try:
            response = (self.client.table("sitemaps")
                       .select("id")
                       .eq("url", url)
                       .limit(1)
                       .execute())
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"檢查 sitemap 存在性時發生錯誤: {e}")
            return False
    
    def get_sitemap_by_url(self, url: str) -> Optional[SitemapModel]:
        """
        根據 URL 獲取 sitemap
        
        Args:
            url: sitemap URL
            
        Returns:
            Optional[SitemapModel]: sitemap 模型實例或 None
        """
        try:
            response = (self.client.table("sitemaps")
                       .select("*")
                       .eq("url", url)
                       .limit(1)
                       .execute())
            
            if response.data:
                return SitemapModel.from_dict(response.data[0])
            
            return None
            
        except Exception as e:
            logger.error(f"獲取 sitemap 時發生錯誤: {e}")
            return None
    
    def update_sitemap_status(self, sitemap_id: str, status: str, error_message: str = None) -> bool:
        """
        更新 sitemap 狀態
        
        Args:
            sitemap_id: sitemap ID
            status: 新狀態
            error_message: 錯誤訊息 (可選)
            
        Returns:
            bool: 更新成功返回 True，否則返回 False
        """
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            
            if status == CrawlStatus.COMPLETED.value:
                update_data["parsed_at"] = datetime.now().isoformat()
            
            if error_message:
                update_data["error_message"] = error_message
            
            response = (self.client.table("sitemaps")
                       .update(update_data)
                       .eq("id", sitemap_id)
                       .execute())
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"更新 sitemap 狀態時發生錯誤: {e}")
            return False
    
    def create_discovered_url(self, discovered_url: DiscoveredURLModel) -> bool:
        """
        創建發現的 URL
        
        Args:
            discovered_url: 發現的 URL 模型實例
            
        Returns:
            bool: 創建成功返回 True，否則返回 False
        """
        try:
            if not discovered_url.validate():
                return False
            
            # 檢查 URL 是否已存在
            if self.discovered_url_exists(discovered_url.url):
                logger.debug(f"發現的 URL 已存在: {discovered_url.url}")
                return True
            
            data = discovered_url.to_dict()
            response = self.client.table("discovered_urls").insert(data).execute()
            
            if response.data:
                logger.debug(f"成功創建發現的 URL: {discovered_url.url}")
                return True
            
            logger.error("創建發現的 URL 失敗: 未返回數據")
            return False
            
        except Exception as e:
            logger.error(f"創建發現的 URL 時發生錯誤: {e}")
            return False
    
    def discovered_url_exists(self, url: str) -> bool:
        """
        檢查發現的 URL 是否存在
        
        Args:
            url: URL
            
        Returns:
            bool: 存在返回 True，否則返回 False
        """
        try:
            response = (self.client.table("discovered_urls")
                       .select("id")
                       .eq("url", url)
                       .limit(1)
                       .execute())
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"檢查發現的 URL 存在性時發生錯誤: {e}")
            return False
    
    def get_pending_urls(self, limit: int = 100, url_type: str = "content") -> List[DiscoveredURLModel]:
        """
        獲取待爬取的 URL
        
        Args:
            limit: 限制數量
            url_type: URL 類型篩選
            
        Returns:
            List[DiscoveredURLModel]: 待爬取的 URL 列表
        """
        try:
            query = (self.client.table("discovered_urls")
                    .select("*")
                    .eq("crawl_status", CrawlStatus.PENDING.value))
            
            if url_type:
                query = query.eq("url_type", url_type)
            
            response = (query.order("priority", desc=True)
                           .order("created_at", desc=False)
                           .limit(limit)
                           .execute())
            
            return [DiscoveredURLModel.from_dict(data) for data in response.data]
            
        except Exception as e:
            logger.error(f"獲取待爬取 URL 時發生錯誤: {e}")
            return []
    
    def update_discovered_url_status(self, url_id: str, status: str, article_id: str = None, 
                                   error_message: str = None) -> bool:
        """
        更新發現的 URL 爬取狀態
        
        Args:
            url_id: URL ID
            status: 新狀態
            article_id: 文章 ID (如果爬取成功)
            error_message: 錯誤訊息 (可選)
            
        Returns:
            bool: 更新成功返回 True，否則返回 False
        """
        try:
            update_data = {
                "crawl_status": status,
                "last_crawl_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            if article_id:
                update_data["article_id"] = article_id
            
            if error_message:
                update_data["error_message"] = error_message
            
            # 增加嘗試次數
            response = (self.client.table("discovered_urls")
                       .select("crawl_attempts")
                       .eq("id", url_id)
                       .limit(1)
                       .execute())
            
            if response.data:
                current_attempts = response.data[0].get("crawl_attempts", 0)
                update_data["crawl_attempts"] = current_attempts + 1
            
            response = (self.client.table("discovered_urls")
                       .update(update_data)
                       .eq("id", url_id)
                       .execute())
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"更新發現的 URL 狀態時發生錯誤: {e}")
            return False
    
    def create_robots_txt(self, robots: RobotsTxtModel) -> bool:
        """
        創建 robots.txt 記錄
        
        Args:
            robots: robots.txt 模型實例
            
        Returns:
            bool: 創建成功返回 True，否則返回 False
        """
        try:
            if not robots.validate():
                return False
            
            # 檢查域名是否已存在，如果存在則更新
            existing = self.get_robots_txt_by_domain(robots.domain)
            if existing:
                # 更新現有記錄
                update_data = {
                    "content": robots.content,
                    "sitemaps_count": robots.sitemaps_count,
                    "rules_count": robots.rules_count,
                    "metadata": robots.metadata,
                    "parsed_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                response = (self.client.table("robots_txt")
                           .update(update_data)
                           .eq("domain", robots.domain)
                           .execute())
                
                return len(response.data) > 0
            else:
                # 創建新記錄
                data = robots.to_dict()
                response = self.client.table("robots_txt").insert(data).execute()
                
                if response.data:
                    logger.info(f"成功創建 robots.txt 記錄: {robots.domain}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"創建/更新 robots.txt 時發生錯誤: {e}")
            return False
    
    def get_robots_txt_by_domain(self, domain: str) -> Optional[RobotsTxtModel]:
        """
        根據域名獲取 robots.txt
        
        Args:
            domain: 域名
            
        Returns:
            Optional[RobotsTxtModel]: robots.txt 模型實例或 None
        """
        try:
            response = (self.client.table("robots_txt")
                       .select("*")
                       .eq("domain", domain)
                       .limit(1)
                       .execute())
            
            if response.data:
                return RobotsTxtModel.from_dict(response.data[0])
            
            return None
            
        except Exception as e:
            logger.error(f"獲取 robots.txt 時發生錯誤: {e}")
            return None
    
    def get_sitemap_hierarchy(self, root_id: str = None) -> List[Dict[str, Any]]:
        """
        獲取 sitemap 層級結構
        
        Args:
            root_id: 根 sitemap ID (可選)
            
        Returns:
            List[Dict[str, Any]]: 層級結構列表
        """
        try:
            if root_id:
                response = self.client.rpc("get_sitemap_hierarchy", {"root_sitemap_id": root_id}).execute()
            else:
                response = self.client.rpc("get_sitemap_hierarchy").execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"獲取 sitemap 層級結構時發生錯誤: {e}")
            return []
    
    def get_sitemap_stats(self) -> Dict[str, Any]:
        """
        獲取 sitemap 統計信息
        
        Returns:
            Dict[str, Any]: 統計信息字典
        """
        try:
            response = self.client.rpc("get_sitemap_stats").execute()
            
            # 轉換結果為更易讀的格式
            stats = {}
            if response.data:
                for item in response.data:
                    table_name = item.get("table_name", "unknown")
                    count = item.get("count", 0)
                    details = item.get("details", {})
                    
                    stats[table_name] = {
                        "count": count,
                        "details": details
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"獲取 sitemap 統計信息時發生錯誤: {e}")
            return {}
    
    def bulk_create_discovered_urls(self, urls: List[DiscoveredURLModel]) -> int:
        """
        批量創建發現的 URL
        
        Args:
            urls: 發現的 URL 列表
            
        Returns:
            int: 成功創建的數量
        """
        try:
            if not urls:
                return 0
            
            # 過濾掉已存在的 URL
            new_urls = []
            for url in urls:
                if url.validate() and not self.discovered_url_exists(url.url):
                    new_urls.append(url.to_dict())
            
            if not new_urls:
                logger.info("所有 URL 都已存在，無需創建")
                return 0
            
            # 批量插入
            response = self.client.table("discovered_urls").insert(new_urls).execute()
            
            success_count = len(response.data) if response.data else 0
            logger.info(f"批量創建 {success_count} 個發現的 URL")
            
            return success_count
            
        except Exception as e:
            logger.error(f"批量創建發現的 URL 時發生錯誤: {e}")
            return 0
