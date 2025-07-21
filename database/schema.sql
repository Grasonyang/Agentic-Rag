-- 啟用所需的擴展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

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

-- 創建 search_logs 表格 (使用 UUID)
CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    query_hash TEXT,
    results_count INTEGER DEFAULT 0,
    response_time_ms INTEGER DEFAULT 0,
    search_type TEXT DEFAULT 'semantic',
    user_agent TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    session_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 創建 search_logs 索引
CREATE INDEX IF NOT EXISTS idx_search_logs_query ON search_logs(query);
CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_search_logs_query_hash ON search_logs(query_hash);
CREATE INDEX IF NOT EXISTS idx_search_logs_search_type ON search_logs(search_type);
CREATE INDEX IF NOT EXISTS idx_search_logs_session_id ON search_logs(session_id);

-- 創建 embeddings_cache 表格 (新增，用於快取嵌入結果)
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

-- 創建更新時間觸發器函數
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

-- 創建內容雜湊觸發器函數
CREATE OR REPLACE FUNCTION update_content_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_hash = md5(NEW.content);
    IF TG_TABLE_NAME = 'articles' THEN
        NEW.word_count = array_length(string_to_array(NEW.content, ' '), 1);
    ELSIF TG_TABLE_NAME = 'article_chunks' THEN
        NEW.chunk_size = length(NEW.content);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

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

-- 創建向量搜索函數 (更新為使用 UUID)
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding VECTOR(1024),
    match_threshold FLOAT DEFAULT 0.78,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    article_id UUID,
    content TEXT,
    embedding VECTOR(1024),
    chunk_index INTEGER,
    chunk_size INTEGER,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        article_chunks.id,
        article_chunks.article_id,
        article_chunks.content,
        article_chunks.embedding,
        article_chunks.chunk_index,
        article_chunks.chunk_size,
        article_chunks.metadata,
        article_chunks.created_at,
        1 - (article_chunks.embedding <=> query_embedding) as similarity
    FROM article_chunks
    WHERE article_chunks.embedding IS NOT NULL
    AND 1 - (article_chunks.embedding <=> query_embedding) > match_threshold
    ORDER BY article_chunks.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 創建語義搜索函數 (結合向量和文本搜索)
CREATE OR REPLACE FUNCTION semantic_search(
    query_text TEXT,
    query_embedding VECTOR(1024) DEFAULT NULL,
    match_threshold FLOAT DEFAULT 0.75,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    chunk_id UUID,
    article_id UUID,
    article_title TEXT,
    article_url TEXT,
    content TEXT,
    chunk_index INTEGER,
    similarity FLOAT,
    search_type TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- 如果有向量，使用向量搜索
    IF query_embedding IS NOT NULL THEN
        RETURN QUERY
        SELECT
            ac.id as chunk_id,
            ac.article_id,
            a.title as article_title,
            a.url as article_url,
            ac.content,
            ac.chunk_index,
            1 - (ac.embedding <=> query_embedding) as similarity,
            'vector'::TEXT as search_type
        FROM article_chunks ac
        JOIN articles a ON ac.article_id = a.id
        WHERE ac.embedding IS NOT NULL
        AND 1 - (ac.embedding <=> query_embedding) > match_threshold
        ORDER BY ac.embedding <=> query_embedding
        LIMIT match_count;
    ELSE
        -- 使用全文搜索
        RETURN QUERY
        SELECT
            ac.id as chunk_id,
            ac.article_id,
            a.title as article_title,
            a.url as article_url,
            ac.content,
            ac.chunk_index,
            ts_rank(to_tsvector('chinese', ac.content), plainto_tsquery('chinese', query_text)) as similarity,
            'text'::TEXT as search_type
        FROM article_chunks ac
        JOIN articles a ON ac.article_id = a.id
        WHERE to_tsvector('chinese', ac.content) @@ plainto_tsquery('chinese', query_text)
        ORDER BY ts_rank(to_tsvector('chinese', ac.content), plainto_tsquery('chinese', query_text)) DESC
        LIMIT match_count;
    END IF;
END;
$$;

-- 創建資料庫管理函數
CREATE OR REPLACE FUNCTION drop_all_user_tables()
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    table_name TEXT;
BEGIN
    FOR table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename NOT LIKE 'pg_%'
        AND tablename NOT LIKE 'sql_%'
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(table_name) || ' CASCADE';
    END LOOP;
END;
$$;

-- =============================================
-- SITEMAP 相關表格和函數
-- =============================================

-- 創建 sitemaps 表格 (存儲所有 sitemap 條目)
CREATE TABLE IF NOT EXISTS sitemaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL DEFAULT 'sitemap', -- 'sitemap', 'sitemapindex', 'urlset'
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'error'
    title TEXT,
    description TEXT,
    lastmod TIMESTAMP WITH TIME ZONE,
    changefreq TEXT, -- 'always', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'never'
    priority DECIMAL(2,1), -- 0.0 to 1.0
    urls_count INTEGER DEFAULT 0,
    parsed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 創建 sitemap_hierarchy 表格 (管理 sitemap 之間的層級關係)
CREATE TABLE IF NOT EXISTS sitemap_hierarchy (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_sitemap_id UUID REFERENCES sitemaps(id) ON DELETE CASCADE,
    child_sitemap_id UUID REFERENCES sitemaps(id) ON DELETE CASCADE,
    level INTEGER DEFAULT 0, -- 從根開始的層級
    discovery_order INTEGER DEFAULT 0, -- 在父級中的發現順序
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(parent_sitemap_id, child_sitemap_id)
);

-- 創建 discovered_urls 表格 (存儲從 sitemap 發現的 URL)
CREATE TABLE IF NOT EXISTS discovered_urls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    source_sitemap_id UUID REFERENCES sitemaps(id) ON DELETE CASCADE,
    url_type TEXT DEFAULT 'content', -- 'content', 'sitemap', 'other'
    priority DECIMAL(2,1), -- 從 sitemap 獲取的優先級
    changefreq TEXT,
    lastmod TIMESTAMP WITH TIME ZONE,
    crawl_status TEXT DEFAULT 'pending', -- 'pending', 'crawling', 'completed', 'error', 'skipped'
    crawl_attempts INTEGER DEFAULT 0,
    last_crawl_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    article_id UUID REFERENCES articles(id) ON DELETE SET NULL, -- 如果已爬取為文章，關聯到 articles
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 創建 robots_txt 表格 (存儲 robots.txt 分析結果)
CREATE TABLE IF NOT EXISTS robots_txt (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain TEXT UNIQUE NOT NULL,
    robots_url TEXT NOT NULL,
    content TEXT NOT NULL,
    parsed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sitemaps_count INTEGER DEFAULT 0,
    rules_count INTEGER DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 創建 sitemap 相關索引
CREATE INDEX IF NOT EXISTS idx_sitemaps_url ON sitemaps(url);
CREATE INDEX IF NOT EXISTS idx_sitemaps_type ON sitemaps(type);
CREATE INDEX IF NOT EXISTS idx_sitemaps_status ON sitemaps(status);
CREATE INDEX IF NOT EXISTS idx_sitemaps_created_at ON sitemaps(created_at);
CREATE INDEX IF NOT EXISTS idx_sitemaps_lastmod ON sitemaps(lastmod);
CREATE INDEX IF NOT EXISTS idx_sitemaps_priority ON sitemaps(priority);

CREATE INDEX IF NOT EXISTS idx_sitemap_hierarchy_parent ON sitemap_hierarchy(parent_sitemap_id);
CREATE INDEX IF NOT EXISTS idx_sitemap_hierarchy_child ON sitemap_hierarchy(child_sitemap_id);
CREATE INDEX IF NOT EXISTS idx_sitemap_hierarchy_level ON sitemap_hierarchy(level);

CREATE INDEX IF NOT EXISTS idx_discovered_urls_url ON discovered_urls(url);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_source ON discovered_urls(source_sitemap_id);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_type ON discovered_urls(url_type);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_status ON discovered_urls(crawl_status);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_priority ON discovered_urls(priority);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_lastmod ON discovered_urls(lastmod);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_article ON discovered_urls(article_id);

CREATE INDEX IF NOT EXISTS idx_robots_txt_domain ON robots_txt(domain);
CREATE INDEX IF NOT EXISTS idx_robots_txt_created_at ON robots_txt(created_at);

-- 創建 sitemap 相關觸發器
DROP TRIGGER IF EXISTS update_sitemaps_updated_at ON sitemaps;
CREATE TRIGGER update_sitemaps_updated_at
    BEFORE UPDATE ON sitemaps
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_discovered_urls_updated_at ON discovered_urls;
CREATE TRIGGER update_discovered_urls_updated_at
    BEFORE UPDATE ON discovered_urls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_robots_txt_updated_at ON robots_txt;
CREATE TRIGGER update_robots_txt_updated_at
    BEFORE UPDATE ON robots_txt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- SITEMAP 管理函數
-- =============================================

-- 1. 獲取 sitemap 層級結構
CREATE OR REPLACE FUNCTION get_sitemap_hierarchy(root_sitemap_id UUID DEFAULT NULL)
RETURNS TABLE (
    sitemap_id UUID,
    url TEXT,
    type TEXT,
    level INTEGER,
    parent_id UUID,
    urls_count INTEGER,
    status TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF root_sitemap_id IS NULL THEN
        -- 返回所有根級 sitemap (沒有父級的)
        RETURN QUERY
        WITH RECURSIVE sitemap_tree AS (
            -- 根級節點
            SELECT 
                s.id as sitemap_id,
                s.url,
                s.type,
                0 as level,
                NULL::UUID as parent_id,
                s.urls_count,
                s.status
            FROM sitemaps s
            WHERE NOT EXISTS (
                SELECT 1 FROM sitemap_hierarchy sh 
                WHERE sh.child_sitemap_id = s.id
            )
            
            UNION ALL
            
            -- 子級節點
            SELECT 
                s.id as sitemap_id,
                s.url,
                s.type,
                st.level + 1 as level,
                sh.parent_sitemap_id as parent_id,
                s.urls_count,
                s.status
            FROM sitemaps s
            JOIN sitemap_hierarchy sh ON s.id = sh.child_sitemap_id
            JOIN sitemap_tree st ON sh.parent_sitemap_id = st.sitemap_id
        )
        SELECT * FROM sitemap_tree ORDER BY level, url;
    ELSE
        -- 返回指定根節點的層級結構
        RETURN QUERY
        WITH RECURSIVE sitemap_tree AS (
            -- 指定的根節點
            SELECT 
                s.id as sitemap_id,
                s.url,
                s.type,
                0 as level,
                NULL::UUID as parent_id,
                s.urls_count,
                s.status
            FROM sitemaps s
            WHERE s.id = root_sitemap_id
            
            UNION ALL
            
            -- 子級節點
            SELECT 
                s.id as sitemap_id,
                s.url,
                s.type,
                st.level + 1 as level,
                sh.parent_sitemap_id as parent_id,
                s.urls_count,
                s.status
            FROM sitemaps s
            JOIN sitemap_hierarchy sh ON s.id = sh.child_sitemap_id
            JOIN sitemap_tree st ON sh.parent_sitemap_id = st.sitemap_id
        )
        SELECT * FROM sitemap_tree ORDER BY level, url;
    END IF;
END;
$$;

-- 2. 獲取待爬取的 URL (按優先級排序)
CREATE OR REPLACE FUNCTION get_crawl_queue(
    limit_count INTEGER DEFAULT 100,
    url_type_filter TEXT DEFAULT 'content'
)
RETURNS TABLE (
    url_id UUID,
    url TEXT,
    priority DECIMAL(2,1),
    source_sitemap_url TEXT,
    lastmod TIMESTAMP WITH TIME ZONE,
    crawl_attempts INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        du.id as url_id,
        du.url,
        du.priority,
        s.url as source_sitemap_url,
        du.lastmod,
        du.crawl_attempts
    FROM discovered_urls du
    JOIN sitemaps s ON du.source_sitemap_id = s.id
    WHERE du.crawl_status = 'pending'
    AND (url_type_filter IS NULL OR du.url_type = url_type_filter)
    ORDER BY 
        COALESCE(du.priority, 0.5) DESC,
        du.lastmod DESC NULLS LAST,
        du.crawl_attempts ASC,
        du.created_at ASC
    LIMIT limit_count;
END;
$$;

-- 3. 更新爬取狀態
CREATE OR REPLACE FUNCTION update_crawl_status(
    url_id UUID,
    new_status TEXT,
    article_id_param UUID DEFAULT NULL,
    error_msg TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE discovered_urls 
    SET 
        crawl_status = new_status,
        last_crawl_at = NOW(),
        crawl_attempts = crawl_attempts + 1,
        article_id = COALESCE(article_id_param, article_id),
        error_message = error_msg,
        updated_at = NOW()
    WHERE id = url_id;
END;
$$;

-- 4. 獲取 sitemap 統計信息
CREATE OR REPLACE FUNCTION get_sitemap_stats()
RETURNS TABLE (
    table_name TEXT,
    count BIGINT,
    details JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'sitemaps'::TEXT as table_name,
        COUNT(*)::BIGINT as count,
        jsonb_build_object(
            'by_type', jsonb_object_agg(COALESCE(type, 'unknown'), count),
            'by_status', jsonb_object_agg(COALESCE(status, 'unknown'), count)
        ) as details
    FROM (
        SELECT type, COUNT(*) as count FROM sitemaps GROUP BY type
        UNION ALL
        SELECT status, COUNT(*) as count FROM sitemaps GROUP BY status
    ) t;
    
    RETURN QUERY
    SELECT 
        'discovered_urls'::TEXT as table_name,
        COUNT(*)::BIGINT as count,
        jsonb_build_object(
            'by_type', jsonb_object_agg(COALESCE(url_type, 'unknown'), count),
            'by_status', jsonb_object_agg(COALESCE(crawl_status, 'unknown'), count),
            'with_articles', (SELECT COUNT(*) FROM discovered_urls WHERE article_id IS NOT NULL)
        ) as details
    FROM (
        SELECT url_type, COUNT(*) as count FROM discovered_urls GROUP BY url_type
        UNION ALL
        SELECT crawl_status, COUNT(*) as count FROM discovered_urls GROUP BY crawl_status
    ) t;
    
    RETURN QUERY
    SELECT 
        'robots_txt'::TEXT as table_name,
        COUNT(*)::BIGINT as count,
        jsonb_build_object(
            'total_sitemaps', COALESCE(SUM(sitemaps_count), 0),
            'total_rules', COALESCE(SUM(rules_count), 0)
        ) as details
    FROM robots_txt;
END;
$$;

-- =============================================
-- 更新後的資料庫統計函數
-- =============================================

-- 創建資料庫統計函數 (包含新的 sitemap 表格)
CREATE OR REPLACE FUNCTION get_database_stats()
RETURNS TABLE (
    table_name TEXT,
    row_count BIGINT,
    total_size TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.table_name::TEXT,
        t.row_count,
        pg_size_pretty(pg_total_relation_size(t.table_name::regclass))::TEXT as total_size
    FROM (
        SELECT 'articles'::TEXT as table_name, COUNT(*)::BIGINT as row_count FROM articles
        UNION ALL
        SELECT 'article_chunks'::TEXT, COUNT(*)::BIGINT FROM article_chunks
        UNION ALL
        SELECT 'search_logs'::TEXT, COUNT(*)::BIGINT FROM search_logs
        UNION ALL
        SELECT 'embeddings_cache'::TEXT, COUNT(*)::BIGINT FROM embeddings_cache
        UNION ALL
        SELECT 'sitemaps'::TEXT, COUNT(*)::BIGINT FROM sitemaps
        UNION ALL
        SELECT 'sitemap_hierarchy'::TEXT, COUNT(*)::BIGINT FROM sitemap_hierarchy
        UNION ALL
        SELECT 'discovered_urls'::TEXT, COUNT(*)::BIGINT FROM discovered_urls
        UNION ALL
        SELECT 'robots_txt'::TEXT, COUNT(*)::BIGINT FROM robots_txt
    ) t;
END;
$$;
