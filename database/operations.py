"""以 PostgreSQL 為基礎的資料庫操作"""

import logging
from typing import List, Optional
from datetime import datetime
from psycopg2.extras import execute_values

from .client import PostgresClient
from .models import (
    ArticleModel,
    ChunkModel,
    SitemapModel,
    DiscoveredURLModel,
    CrawlStatus,
)

logger = logging.getLogger(__name__)

class DatabaseOperations:
    """封裝常用的資料庫操作"""

    def __init__(self, client: PostgresClient):
        self.client = client
        if not self.client.connect():
            raise RuntimeError("無法連線到 PostgreSQL 資料庫")

    # --------- Sitemap 操作 ---------
    def create_sitemap(self, sitemap: SitemapModel) -> bool:
        """寫入 sitemap 紀錄"""
        sql = (
            """
            INSERT INTO sitemaps (id, url, domain, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            """
        )
        params = (
            sitemap.id,
            sitemap.url,
            sitemap.domain,
            sitemap.created_at,
            sitemap.updated_at,
        )
        try:
            self.client.execute_query(sql, params, fetch=False)
            return True
        except Exception as e:
            logger.error(f"寫入 sitemap 失敗: {e}")
            return False

    # --------- DiscoveredURL 操作 ---------
    def create_discovered_url(self, url_model: DiscoveredURLModel) -> bool:
        """新增單一待爬取 URL"""
        sql = (
            """
            INSERT INTO discovered_urls (
                id, url, domain, source_sitemap, priority,
                changefreq, lastmod, crawl_status, crawl_attempts,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            ) ON CONFLICT (url) DO NOTHING
            """
        )
        params = (
            url_model.id,
            url_model.url,
            url_model.domain,
            url_model.source_sitemap,
            url_model.priority,
            url_model.changefreq.value if url_model.changefreq else None,
            url_model.lastmod,
            url_model.crawl_status.value,
            url_model.crawl_attempts,
            url_model.created_at,
            url_model.updated_at,
        )
        try:
            self.client.execute_query(sql, params, fetch=False)
            return True
        except Exception as e:
            logger.error(f"新增 URL 失敗: {e}")
            return False

    def bulk_create_discovered_urls(self, url_models: List[DiscoveredURLModel]) -> int:
        """批次新增待爬取 URL"""
        count = 0
        for model in url_models:
            if self.create_discovered_url(model):
                count += 1
        return count

    def bulk_insert_discovered_urls(self, url_models: List[DiscoveredURLModel]) -> int:
        """使用 execute_values 一次插入多筆 URL"""
        sql = (
            """
            INSERT INTO discovered_urls (
                id, url, domain, source_sitemap, priority,
                changefreq, lastmod, crawl_status, crawl_attempts,
                created_at, updated_at
            ) VALUES %s
            ON CONFLICT (url) DO NOTHING
            """
        )
        values = [
            (
                m.id,
                m.url,
                m.domain,
                m.source_sitemap,
                m.priority,
                m.changefreq.value if m.changefreq else None,
                m.lastmod,
                m.crawl_status.value,
                m.crawl_attempts,
                m.created_at,
                m.updated_at,
            )
            for m in url_models
        ]
        try:
            with self.client.connection.cursor() as cur:
                execute_values(cur, sql, values)
                count = cur.rowcount
            self.client.connection.commit()
            return count
        except Exception as e:
            self.client.connection.rollback()
            logger.error(f"批次新增 URL 失敗: {e}")
            return 0

    def get_pending_urls(self, limit: Optional[int] = 100) -> List[DiscoveredURLModel]:
        """取得尚未處理的 URL"""
        sql = (
            # 依優先級與最後爬取時間排序，避免重複載入全量
            "SELECT * FROM discovered_urls WHERE crawl_status IS NULL OR crawl_status=%s "
            "ORDER BY priority DESC NULLS LAST, COALESCE(last_crawl_at, created_at) LIMIT %s"
        )
        rows = self.client.execute_query(sql, (CrawlStatus.PENDING.value, limit)) or []
        return [DiscoveredURLModel.from_dict(dict(r)) for r in rows]

    def update_crawl_status(
        self, url_id: str, status: CrawlStatus, error_message: str | None = None
    ) -> bool:
        """更新爬取狀態"""
        fields = ["crawl_status=%s", "updated_at=%s"]
        params = [status.value, datetime.now()]
        if status == CrawlStatus.CRAWLING:
            fields.append("crawl_attempts = crawl_attempts + 1")
        if status in (CrawlStatus.COMPLETED, CrawlStatus.ERROR):
            fields.append("last_crawl_at=%s")
            params.append(datetime.now())
        if error_message and status == CrawlStatus.ERROR:
            fields.append("error_message=%s")
            params.append(error_message)
        params.append(url_id)
        sql = f"UPDATE discovered_urls SET {', '.join(fields)} WHERE id=%s"
        try:
            self.client.execute_query(sql, tuple(params), fetch=False)
            return True
        except Exception as e:
            logger.error(f"更新 URL 狀態失敗: {e}")
            return False

    def url_exists(self, url: str) -> bool:
        """檢查 URL 是否已存在於 sitemaps 或 discovered_urls"""
        sql = (
            "SELECT 1 FROM sitemaps WHERE url=%s UNION ALL SELECT 1 FROM discovered_urls WHERE url=%s LIMIT 1"
        )
        rows = self.client.execute_query(sql, (url, url))
        return bool(rows)

    def get_table_count(self, table: str) -> int:
        """回傳指定表格的資料筆數"""
        try:
            sql = f"SELECT COUNT(*) AS count FROM {table}"
            rows = self.client.execute_query(sql)
            return rows[0]["count"] if rows else -1
        except Exception as e:
            logger.error(f"取得表格 {table} 筆數失敗: {e}")
            return -1

    # --------- Article 操作 ---------
    def create_article(self, article: ArticleModel) -> bool:
        """新增文章"""
        sql = (
            """
            INSERT INTO articles (id, url, title, content, metadata, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            """
        )
        params = (
            article.id,
            article.url,
            article.title,
            article.content,
            article.metadata,
            article.created_at,
            article.updated_at,
        )
        try:
            self.client.execute_query(sql, params, fetch=False)
            return True
        except Exception as e:
            logger.error(f"新增文章失敗: {e}")
            return False

    def get_article_by_url(self, url: str) -> Optional[ArticleModel]:
        """以 URL 查詢文章"""
        sql = "SELECT * FROM articles WHERE url=%s LIMIT 1"
        rows = self.client.execute_query(sql, (url,))
        if rows:
            return ArticleModel.from_dict(dict(rows[0]))
        return None

    # --------- Chunk 操作 ---------
    def create_chunks(self, chunks: List[ChunkModel]) -> int:
        """批量新增文章區塊"""
        sql = (
            """
            INSERT INTO article_chunks (
                id, article_id, content, embedding, chunk_index,
                chunk_type, metadata, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            """
        )
        count = 0
        for c in chunks:
            params = (
                c.id,
                c.article_id,
                c.content,
                c.embedding,
                c.chunk_index,
                c.chunk_type,
                c.metadata,
                c.created_at,
            )
            try:
                self.client.execute_query(sql, params, fetch=False)
                count += 1
            except Exception as e:
                logger.error(f"新增文章區塊失敗: {e}")
        return count

    def close(self):
        """關閉資料庫連線"""
        self.client.disconnect()


def get_database_operations() -> Optional[DatabaseOperations]:
    """建立並回傳 DatabaseOperations 實例"""
    try:
        client = PostgresClient()
        ops = DatabaseOperations(client)
        return ops
    except Exception as e:
        logger.error(f"初始化資料庫操作失敗: {e}")
        return None
