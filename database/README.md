# 📊 Database 模組使用指南

這個模組提供了完整的資料庫操作功能，包括連接管理、模型定義、以及各種資料庫操作。

## 🏗️ 資料庫架構

### 核心表結構

#### 1. `articles` 表 - 文章主體
```sql
-- 使用 UUID 作為主鍵以支援分散式系統
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    metadata JSONB DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引優化
CREATE INDEX idx_articles_url ON articles(url);
CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_articles_created_at ON articles(created_at);
```

#### 2. `article_chunks` 表 - 文章分塊與向量儲存
```sql
-- 高效向量相似搜索的核心表
CREATE TABLE article_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(384),  -- BGE-large-zh-v1.5 維度
    chunk_index INTEGER DEFAULT 0,
    chunk_type TEXT DEFAULT 'sentence',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW 索引用於高效向量搜索 (Supabase 推薦)
CREATE INDEX idx_article_chunks_embedding ON article_chunks 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- 傳統索引
CREATE INDEX idx_article_chunks_article_id ON article_chunks(article_id);
CREATE INDEX idx_article_chunks_chunk_index ON article_chunks(chunk_index);
```

#### 3. `crawl_logs` 表 - 爬取記錄與狀態追蹤
```sql
CREATE TABLE crawl_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    response_time_ms INTEGER,
    http_status_code INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 監控與分析索引
CREATE INDEX idx_crawl_logs_url ON crawl_logs(url);
CREATE INDEX idx_crawl_logs_status ON crawl_logs(status);
CREATE INDEX idx_crawl_logs_success ON crawl_logs(success);
```

#### 4. `search_logs` 表 - 搜索行為分析
```sql
CREATE TABLE search_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    query_embedding VECTOR(384),
    results_count INTEGER DEFAULT 0,
    search_duration_ms INTEGER,
    threshold FLOAT DEFAULT 0.7,
    user_id TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 分析與優化索引
CREATE INDEX idx_search_logs_query ON search_logs(query);
CREATE INDEX idx_search_logs_created_at ON search_logs(created_at);
CREATE INDEX idx_search_logs_user_id ON search_logs(user_id);
```

### 其他支援表

#### 5. `sitemaps` 表 - Sitemap 記錄
```sql
CREATE TABLE sitemaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT UNIQUE NOT NULL,
    type TEXT DEFAULT 'sitemap',
    status TEXT DEFAULT 'pending',
    title TEXT,
    description TEXT,
    lastmod TIMESTAMPTZ,
    changefreq TEXT,
    priority FLOAT,
    urls_count INTEGER DEFAULT 0,
    parsed_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 6. `discovered_urls` 表 - 發現的 URL
```sql
CREATE TABLE discovered_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    source_sitemap_id UUID REFERENCES sitemaps(id),
    url_type TEXT DEFAULT 'content',
    priority FLOAT,
    changefreq TEXT,
    lastmod TIMESTAMPTZ,
    crawl_status TEXT DEFAULT 'pending',
    crawl_attempts INTEGER DEFAULT 0,
    last_crawl_at TIMESTAMPTZ,
    error_message TEXT,
    article_id UUID REFERENCES articles(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 📋 模型說明

### 核心模型類別

| 模型類別 | 用途 | 主要欄位 |
|---------|------|---------|
| `ArticleModel` | 文章內容存儲 | id, url, title, content, metadata |
| `ChunkModel` | 文章分塊與向量 | article_id, content, embedding, chunk_index |
| `SitemapModel` | Sitemap 管理 | url, type, status, urls_count |
| `DiscoveredURLModel` | URL 發現記錄 | url, source_sitemap_id, crawl_status |
| `SearchLogModel` | 搜索記錄 | query, results_count, response_time_ms |

### 狀態枚舉

```python
class CrawlStatus(Enum):
    PENDING = "pending"      # 待處理
    CRAWLING = "crawling"    # 處理中
    COMPLETED = "completed"  # 已完成
    ERROR = "error"          # 錯誤
    SKIPPED = "skipped"      # 已跳過

class SitemapType(Enum):
    SITEMAP = "sitemap"              # 普通 sitemap
    SITEMAPINDEX = "sitemapindex"    # sitemap 索引
    URLSET = "urlset"                # URL 集合
```

## 🔧 基本使用

### 1. 資料庫連接

```python
from database.client import SupabaseClient
from database.operations import DatabaseOperations

# 初始化資料庫連接
client = SupabaseClient()
db = DatabaseOperations()

# 測試連接
if client.test_connection():
    print("資料庫連接成功！")
```

### 2. 文章操作

```python
from database.models import ArticleModel

# 創建文章
article = ArticleModel(
    url="https://example.com/article",
    title="範例文章",
    content="這是文章內容...",
    metadata={"author": "作者", "tags": ["AI", "Python"]}
)

# 儲存到資料庫
article_id = db.create_article(article.to_dict())
print(f"文章已儲存，ID: {article_id}")

# 讀取文章
retrieved_article = db.get_article_by_url("https://example.com/article")
if retrieved_article:
    article_obj = ArticleModel.from_dict(retrieved_article)
    print(f"文章標題: {article_obj.title}")
```

### 3. 分塊操作

```python
from database.models import ChunkModel

# 創建文章分塊
chunk = ChunkModel(
    article_id=article_id,
    content="這是文章的第一個分塊...",
    chunk_index=0,
    embedding=[0.1, 0.2, 0.3, ...],  # 384 維向量
    metadata={"chunk_type": "paragraph"}
)

# 儲存分塊
chunk_id = db.create_chunk(chunk.to_dict())
print(f"分塊已儲存，ID: {chunk_id}")
```

### 4. 語義搜索

```python
from embedding.embedding import embed_text

# 執行語義搜索
query = "什麼是人工智慧？"
query_embedding = embed_text(query)

results = db.semantic_search(
    query_text=query,
    query_embedding=query_embedding,
    match_threshold=0.75,
    match_count=5
)

for result in results:
    print(f"相似度: {result['similarity']:.3f}")
    print(f"內容: {result['content'][:100]}...")
    print(f"來源: {result['article_url']}")
    print("-" * 50)
```

### 5. Sitemap 管理

```python
from database.models import SitemapModel, SitemapType, CrawlStatus

# 創建 Sitemap 記錄
sitemap = SitemapModel(
    url="https://example.com/sitemap.xml",
    sitemap_type=SitemapType.SITEMAP,
    status=CrawlStatus.PENDING,
    urls_count=100
)

# 儲存 Sitemap
sitemap_id = db.create_sitemap(sitemap.to_dict())

# 更新狀態
db.update_sitemap_status(sitemap_id, CrawlStatus.COMPLETED)
```

## 📊 RPC 函數使用

### 1. 語義搜索函數

```python
# 直接調用 RPC 函數
search_params = {
    'query_text': '人工智慧',
    'query_embedding': query_embedding,
    'match_threshold': 0.7,
    'match_count': 10
}

results = client.supabase.rpc('semantic_search', search_params).execute()
print("搜索結果:", results.data)
```

### 2. 系統統計函數

```python
# 獲取系統統計
stats = client.supabase.rpc('get_system_stats').execute()
print(f"總文章數: {stats.data['total_articles']}")
print(f"總分塊數: {stats.data['total_chunks']}")
print(f"成功爬取: {stats.data['successful_crawls']}")
print(f"失敗爬取: {stats.data['failed_crawls']}")
print(f"資料庫大小: {stats.data['database_size_mb']} MB")
```

### 3. 表格資訊查詢

```python
# 獲取所有表格資訊
tables = client.supabase.rpc('get_all_tables').execute()
for table in tables.data:
    print(f"表格: {table['table_name']}, 記錄數: {table['row_count']}")
```

## 🔍 進階查詢

### 1. 複雜條件查詢

```python
# 查詢特定狀態的文章
articles = client.supabase.from_('articles')\
    .select('*')\
    .eq('status', 'completed')\
    .order('created_at', desc=True)\
    .limit(10)\
    .execute()

print(f"找到 {len(articles.data)} 篇已完成的文章")
```

### 2. 聚合查詢

```python
# 統計每個域名的文章數量
from urllib.parse import urlparse

domain_stats = {}
articles = client.supabase.from_('articles').select('url').execute()

for article in articles.data:
    domain = urlparse(article['url']).netloc
    domain_stats[domain] = domain_stats.get(domain, 0) + 1

print("各域名文章統計:")
for domain, count in sorted(domain_stats.items(), key=lambda x: x[1], reverse=True):
    print(f"{domain}: {count} 篇")
```

### 3. 時間範圍查詢

```python
from datetime import datetime, timedelta

# 查詢最近 7 天的搜索記錄
week_ago = (datetime.now() - timedelta(days=7)).isoformat()

recent_searches = client.supabase.from_('search_logs')\
    .select('query, results_count, created_at')\
    .gte('created_at', week_ago)\
    .order('created_at', desc=True)\
    .execute()

print(f"最近 7 天共有 {len(recent_searches.data)} 次搜索")
```

## 🛠️ 管理工具

### 1. 資料庫清理

```python
# 清理失敗的爬取記錄 (超過 30 天)
cleanup_date = (datetime.now() - timedelta(days=30)).isoformat()

cleanup_result = client.supabase.from_('crawl_logs')\
    .delete()\
    .eq('success', False)\
    .lt('created_at', cleanup_date)\
    .execute()

print(f"清理了 {len(cleanup_result.data)} 條失敗記錄")
```

### 2. 重新計算統計

```python
# 更新文章的字數統計
articles = client.supabase.from_('articles').select('id, content').execute()

for article in articles.data:
    word_count = len(article['content'].split())
    
    client.supabase.from_('articles')\
        .update({'word_count': word_count})\
        .eq('id', article['id'])\
        .execute()

print(f"更新了 {len(articles.data)} 篇文章的字數統計")
```

### 3. 索引優化

```python
# 檢查索引使用情況
index_stats = client.supabase.rpc('get_index_usage').execute()
for stat in index_stats.data:
    print(f"索引 {stat['indexname']}: 使用次數 {stat['idx_scan']}")
```

## 📈 性能監控

### 1. 查詢性能分析

```python
import time

# 測試搜索性能
start_time = time.time()

results = db.semantic_search(
    query_text="測試查詢",
    query_embedding=test_embedding,
    match_count=100
)

end_time = time.time()
duration_ms = (end_time - start_time) * 1000

print(f"搜索耗時: {duration_ms:.2f} ms")
print(f"結果數量: {len(results)}")
print(f"平均每結果耗時: {duration_ms/len(results):.2f} ms")
```

### 2. 資料庫大小監控

```python
# 監控各表的大小
table_sizes = client.supabase.rpc('get_table_sizes').execute()

for table in table_sizes.data:
    print(f"{table['table_name']}: {table['size_mb']} MB")
```

## 🔒 權限與安全

### Supabase 權限設定

```sql
-- 為 anon 角色提供讀取權限 (公開 API)
GRANT SELECT ON articles TO anon;
GRANT SELECT ON article_chunks TO anon;
GRANT SELECT ON search_logs TO anon;
GRANT SELECT ON crawl_logs TO anon;

-- 為 authenticated 角色提供完整權限
GRANT ALL ON articles TO authenticated;
GRANT ALL ON article_chunks TO authenticated;
GRANT ALL ON search_logs TO authenticated;
GRANT ALL ON crawl_logs TO authenticated;

-- RPC 函數權限
GRANT EXECUTE ON FUNCTION semantic_search TO anon;
GRANT EXECUTE ON FUNCTION get_system_stats TO anon;
GRANT EXECUTE ON FUNCTION get_all_tables TO anon;
```

### 安全最佳實踐

1. **使用環境變數**: 敏感資訊如資料庫密鑰應存放在 `.env` 檔案中
2. **限制 API 權限**: 公開 API 僅提供必要的讀取權限
3. **輸入驗證**: 所有模型都包含 `validate()` 方法進行資料驗證
4. **SQL 注入防護**: 使用參數化查詢避免 SQL 注入

## 🐛 故障排除

### 常見問題

1. **連接失敗**
   ```python
   # 檢查環境變數
   import os
   print("SUPABASE_URL:", os.getenv('SUPABASE_URL'))
   print("SUPABASE_KEY:", os.getenv('SUPABASE_KEY'))
   ```

2. **向量維度錯誤**
   ```python
   # 確認向量維度為 384 (BGE-large-zh-v1.5)
   if len(embedding) != 384:
       print(f"錯誤: 向量維度為 {len(embedding)}，應為 384")
   ```

3. **權限錯誤**
   ```python
   # 檢查是否使用正確的 API 金鑰
   try:
       result = client.supabase.from_('articles').select('count').execute()
       print("權限正常")
   except Exception as e:
       print(f"權限錯誤: {e}")
   ```

## 📚 相關資源

- [Supabase 官方文件](https://supabase.com/docs)
- [pgvector 使用指南](https://github.com/pgvector/pgvector)
- [PostgreSQL UUID 最佳實踐](https://www.postgresql.org/docs/current/datatype-uuid.html)
- [HNSW 索引優化](https://github.com/pgvector/pgvector#hnsw)

---

**💡 提示**: 如果遇到問題，請先檢查資料庫連接和權限設定，大部分問題都與配置相關。
