-- =============================================
-- 內容管理 Schema - 文章和分塊相關表格
-- =============================================

-- 創建 articles 表格 (使用 UUID)
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    content_hash TEXT,
    word_count INTEGER DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 創建 articles 索引
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_word_count ON articles(word_count);

-- 創建 article_chunks 表格 (使用 UUID)
CREATE TABLE IF NOT EXISTS article_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    content_hash TEXT,
    embedding VECTOR(1024),
    chunk_index INTEGER NOT NULL,
    chunk_size INTEGER DEFAULT 0,
    start_position INTEGER DEFAULT 0,
    end_position INTEGER DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 創建 article_chunks 索引
CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON article_chunks(article_id);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON article_chunks(created_at);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON article_chunks(chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON article_chunks(content_hash);
-- 向量索引 (HNSW for better performance)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON article_chunks 
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- 創建 embeddings_cache 表格 (嵌入向量快取)
CREATE TABLE IF NOT EXISTS embeddings_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_hash TEXT UNIQUE NOT NULL,
    content_preview TEXT,
    embedding VECTOR(1024) NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 創建 embeddings_cache 索引
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_content_hash ON embeddings_cache(content_hash);
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_model ON embeddings_cache(model_name);
CREATE INDEX IF NOT EXISTS idx_embeddings_cache_created_at ON embeddings_cache(created_at);

-- 為 articles 表創建觸發器
DROP TRIGGER IF EXISTS update_articles_updated_at ON articles;
CREATE TRIGGER update_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_articles_content_hash ON articles;
CREATE TRIGGER update_articles_content_hash
    BEFORE INSERT OR UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_content_hash();

-- 為 article_chunks 表創建觸發器
DROP TRIGGER IF EXISTS update_chunks_content_hash ON article_chunks;
CREATE TRIGGER update_chunks_content_hash
    BEFORE INSERT OR UPDATE ON article_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_content_hash();
