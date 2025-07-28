-- =============================================
-- RAG系统完整数据库架构 - 整合版本
-- 版本: 2025.07.28
-- 描述: 包含核心表格、函数、视图和扩展功能
-- 
-- 🚀 使用方式:
-- 1. 直接執行此檔案即可建立完整的資料庫架構
-- 2. psql -d your_database -f schema.sql
-- 3. 或在 PostgreSQL 中執行: \i schema.sql
-- 
-- ⚠️ 注意: 此檔案包含所有功能，無需執行其他 SQL 檔案
-- =============================================

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================
-- 枚举类型定义
-- =============================================

-- 爬取状态
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'crawl_status_enum') THEN
        CREATE TYPE crawl_status_enum AS ENUM ('pending', 'crawling', 'completed', 'error', 'skipped');
    END IF;
END$$;

-- 变更频率
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'changefreq_enum') THEN
        CREATE TYPE changefreq_enum AS ENUM ('always', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'never');
    END IF;
END$$;

-- =============================================
-- 触发器函数
-- =============================================

-- 自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

-- 自动计算内容哈希和统计信息
CREATE OR REPLACE FUNCTION update_content_hash()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.content IS NOT NULL AND NEW.content != '' THEN
        NEW.content_hash = md5(NEW.content);
        
        IF TG_TABLE_NAME = 'articles' THEN
            NEW.word_count = array_length(string_to_array(NEW.content, ' '), 1);
        ELSIF TG_TABLE_NAME = 'article_chunks' THEN
            NEW.chunk_size = length(NEW.content);
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

-- =============================================
-- 核心表格
-- =============================================

-- 1. 发现的URLs表 (从sitemap解析的URL)
CREATE TABLE IF NOT EXISTS discovered_urls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    source_sitemap TEXT,                -- 来源sitemap URL
    priority DECIMAL(2,1) CHECK (priority >= 0.0 AND priority <= 1.0),
    changefreq changefreq_enum,
    lastmod TIMESTAMP WITH TIME ZONE,
    crawl_status crawl_status_enum DEFAULT 'pending',
    crawl_attempts INTEGER DEFAULT 0,
    last_crawl_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 文章表 (爬取的网页内容)
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    content_hash TEXT,                   -- 自动计算
    word_count INTEGER DEFAULT 0,       -- 自动计算
    crawled_from_url_id UUID REFERENCES discovered_urls(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 文章分块表 (文章内容的分块)
CREATE TABLE IF NOT EXISTS article_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    content_hash TEXT,                   -- 自动计算
    embedding VECTOR(1024),              -- 向量嵌入
    chunk_index INTEGER NOT NULL,       -- 在文章中的顺序
    chunk_size INTEGER DEFAULT 0,       -- 自动计算
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Sitemap表 (sitemap文件记录)
CREATE TABLE IF NOT EXISTS sitemaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    status crawl_status_enum DEFAULT 'pending',
    urls_count INTEGER DEFAULT 0,
    parsed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- 索引优化
-- =============================================

-- discovered_urls 索引
CREATE INDEX IF NOT EXISTS idx_discovered_urls_url ON discovered_urls(url);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_domain ON discovered_urls(domain);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_status ON discovered_urls(crawl_status);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_created_at ON discovered_urls(created_at);
CREATE INDEX IF NOT EXISTS idx_discovered_urls_source ON discovered_urls(source_sitemap);

-- articles 索引
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);
CREATE INDEX IF NOT EXISTS idx_articles_crawled_from ON articles(crawled_from_url_id);

-- article_chunks 索引
CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON article_chunks(article_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON article_chunks(chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON article_chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON article_chunks(created_at);

-- 向量搜索索引 (HNSW算法，用于相似性搜索)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON article_chunks 
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- sitemaps 索引
CREATE INDEX IF NOT EXISTS idx_sitemaps_url ON sitemaps(url);
CREATE INDEX IF NOT EXISTS idx_sitemaps_domain ON sitemaps(domain);
CREATE INDEX IF NOT EXISTS idx_sitemaps_status ON sitemaps(status);
CREATE INDEX IF NOT EXISTS idx_sitemaps_created_at ON sitemaps(created_at);

-- =============================================
-- 触发器设置
-- =============================================

-- discovered_urls 表触发器
DROP TRIGGER IF EXISTS trigger_discovered_urls_updated_at ON discovered_urls;
CREATE TRIGGER trigger_discovered_urls_updated_at
    BEFORE UPDATE ON discovered_urls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- articles 表触发器
DROP TRIGGER IF EXISTS trigger_articles_updated_at ON articles;
CREATE TRIGGER trigger_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_articles_content_hash ON articles;
CREATE TRIGGER trigger_articles_content_hash
    BEFORE INSERT OR UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_content_hash();

-- article_chunks 表触发器
DROP TRIGGER IF EXISTS trigger_chunks_content_hash ON article_chunks;
CREATE TRIGGER trigger_chunks_content_hash
    BEFORE INSERT OR UPDATE ON article_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_content_hash();

-- sitemaps 表触发器
DROP TRIGGER IF EXISTS trigger_sitemaps_updated_at ON sitemaps;
CREATE TRIGGER trigger_sitemaps_updated_at
    BEFORE UPDATE ON sitemaps
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- 权限设置和 RLS 政策
-- =============================================

-- 为所有角色授予必要权限
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, service_role;

-- =============================================
-- RLS (Row Level Security) 政策設定
-- =============================================

-- 啟用 RLS 對所有表格
ALTER TABLE discovered_urls ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE sitemaps ENABLE ROW LEVEL SECURITY;

-- discovered_urls 表的 RLS 政策
CREATE POLICY "Enable read access for all users" ON discovered_urls
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for authenticated users" ON discovered_urls
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for authenticated users" ON discovered_urls
    FOR UPDATE USING (true);

CREATE POLICY "Enable delete for authenticated users" ON discovered_urls
    FOR DELETE USING (true);

-- articles 表的 RLS 政策
CREATE POLICY "Enable read access for all users" ON articles
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for authenticated users" ON articles
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for authenticated users" ON articles
    FOR UPDATE USING (true);

CREATE POLICY "Enable delete for authenticated users" ON articles
    FOR DELETE USING (true);

-- article_chunks 表的 RLS 政策
CREATE POLICY "Enable read access for all users" ON article_chunks
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for authenticated users" ON article_chunks
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for authenticated users" ON article_chunks
    FOR UPDATE USING (true);

CREATE POLICY "Enable delete for authenticated users" ON article_chunks
    FOR DELETE USING (true);

-- sitemaps 表的 RLS 政策
CREATE POLICY "Enable read access for all users" ON sitemaps
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for authenticated users" ON sitemaps
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for authenticated users" ON sitemaps
    FOR UPDATE USING (true);

CREATE POLICY "Enable delete for authenticated users" ON sitemaps
    FOR DELETE USING (true);

-- =============================================
-- 实用查询函数
-- =============================================

-- 获取数据库统计信息
CREATE OR REPLACE FUNCTION get_db_stats()
RETURNS TABLE (
    table_name TEXT,
    row_count BIGINT,
    table_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.table_name::TEXT,
        COALESCE(s.n_tup_ins - s.n_tup_del, 0)::BIGINT as row_count,
        pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name)::regclass))::TEXT as table_size
    FROM information_schema.tables t
    LEFT JOIN pg_stat_user_tables s ON t.table_name = s.relname
    WHERE t.table_schema = 'public'
    AND t.table_name IN ('discovered_urls', 'articles', 'article_chunks', 'sitemaps')
    ORDER BY t.table_name;
END;
$$ LANGUAGE plpgsql;

-- 清理所有数据
CREATE OR REPLACE FUNCTION clear_all_data()
RETURNS VOID AS $$
BEGIN
    TRUNCATE TABLE article_chunks CASCADE;
    TRUNCATE TABLE articles CASCADE;
    TRUNCATE TABLE discovered_urls CASCADE;
    TRUNCATE TABLE sitemaps CASCADE;
    
    RAISE NOTICE '所有表格数据已清除';
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- 完成信息
-- =============================================

DO $$
BEGIN
    RAISE NOTICE '=== RAG系统数据库架构部署完成 ===';
    RAISE NOTICE '核心表格: discovered_urls, articles, article_chunks, sitemaps';
    RAISE NOTICE '使用 SELECT * FROM get_db_stats(); 查看统计信息';
    RAISE NOTICE '使用 SELECT clear_all_data(); 清空所有数据';
END
$$;

-- =============================================
-- 擴展功能 - 額外的實用函數和視圖
-- =============================================

-- 獲取域名統計信息
CREATE OR REPLACE FUNCTION get_domain_stats()
RETURNS TABLE (
    domain TEXT,
    total_urls BIGINT,
    crawled_urls BIGINT,
    pending_urls BIGINT,
    error_urls BIGINT,
    total_articles BIGINT,
    total_chunks BIGINT,
    crawl_success_rate DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.domain::TEXT,
        COUNT(d.id)::BIGINT as total_urls,
        COUNT(CASE WHEN d.crawl_status = 'completed' THEN 1 END)::BIGINT as crawled_urls,
        COUNT(CASE WHEN d.crawl_status = 'pending' THEN 1 END)::BIGINT as pending_urls,
        COUNT(CASE WHEN d.crawl_status = 'error' THEN 1 END)::BIGINT as error_urls,
        COUNT(a.id)::BIGINT as total_articles,
        COUNT(c.id)::BIGINT as total_chunks,
        CASE 
            WHEN COUNT(d.id) > 0 THEN 
                ROUND((COUNT(CASE WHEN d.crawl_status = 'completed' THEN 1 END) * 100.0 / COUNT(d.id)), 2)
            ELSE 0.00
        END as crawl_success_rate
    FROM discovered_urls d
    LEFT JOIN articles a ON d.id = a.crawled_from_url_id
    LEFT JOIN article_chunks c ON a.id = c.article_id
    GROUP BY d.domain
    ORDER BY total_urls DESC;
END;
$$ LANGUAGE plpgsql;

-- 獲取爬取進度信息
CREATE OR REPLACE FUNCTION get_crawl_progress()
RETURNS TABLE (
    total_discovered BIGINT,
    total_crawled BIGINT,
    total_pending BIGINT,
    total_errors BIGINT,
    total_articles BIGINT,
    total_chunks BIGINT,
    avg_chunks_per_article DECIMAL(10,2),
    progress_percentage DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(d.id)::BIGINT as total_discovered,
        COUNT(CASE WHEN d.crawl_status = 'completed' THEN 1 END)::BIGINT as total_crawled,
        COUNT(CASE WHEN d.crawl_status = 'pending' THEN 1 END)::BIGINT as total_pending,
        COUNT(CASE WHEN d.crawl_status = 'error' THEN 1 END)::BIGINT as total_errors,
        (SELECT COUNT(*) FROM articles)::BIGINT as total_articles,
        (SELECT COUNT(*) FROM article_chunks)::BIGINT as total_chunks,
        CASE 
            WHEN (SELECT COUNT(*) FROM articles) > 0 THEN
                ROUND((SELECT COUNT(*) FROM article_chunks)::DECIMAL / (SELECT COUNT(*) FROM articles), 2)
            ELSE 0.00
        END as avg_chunks_per_article,
        CASE 
            WHEN COUNT(d.id) > 0 THEN
                ROUND((COUNT(CASE WHEN d.crawl_status = 'completed' THEN 1 END) * 100.0 / COUNT(d.id)), 2)
            ELSE 0.00
        END as progress_percentage
    FROM discovered_urls d;
END;
$$ LANGUAGE plpgsql;

-- 搜索相似內容（使用向量相似度）
CREATE OR REPLACE FUNCTION search_similar_content(
    query_embedding VECTOR(1024),
    similarity_threshold REAL DEFAULT 0.7,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    chunk_id UUID,
    article_id UUID,
    article_url TEXT,
    article_title TEXT,
    chunk_content TEXT,
    similarity_score REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id as chunk_id,
        c.article_id,
        a.url as article_url,
        a.title as article_title,
        c.content as chunk_content,
        (1 - (c.embedding <=> query_embedding)) as similarity_score
    FROM article_chunks c
    JOIN articles a ON c.article_id = a.id
    WHERE c.embedding IS NOT NULL
    AND (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- 清理重複內容（基於 content_hash）
CREATE OR REPLACE FUNCTION cleanup_duplicate_articles()
RETURNS TABLE (
    deleted_articles INTEGER,
    deleted_chunks INTEGER
) AS $$
DECLARE
    deleted_articles_count INTEGER := 0;
    deleted_chunks_count INTEGER := 0;
BEGIN
    -- 刪除重複文章的塊
    WITH duplicate_articles AS (
        SELECT id, content_hash, 
               ROW_NUMBER() OVER (PARTITION BY content_hash ORDER BY created_at) as rn
        FROM articles 
        WHERE content_hash IS NOT NULL AND content_hash != ''
    ),
    articles_to_delete AS (
        SELECT id FROM duplicate_articles WHERE rn > 1
    )
    DELETE FROM article_chunks 
    WHERE article_id IN (SELECT id FROM articles_to_delete);
    
    GET DIAGNOSTICS deleted_chunks_count = ROW_COUNT;
    
    -- 刪除重複文章
    WITH duplicate_articles AS (
        SELECT id, content_hash, 
               ROW_NUMBER() OVER (PARTITION BY content_hash ORDER BY created_at) as rn
        FROM articles 
        WHERE content_hash IS NOT NULL AND content_hash != ''
    )
    DELETE FROM articles 
    WHERE id IN (SELECT id FROM duplicate_articles WHERE rn > 1);
    
    GET DIAGNOSTICS deleted_articles_count = ROW_COUNT;
    
    RETURN QUERY SELECT deleted_articles_count, deleted_chunks_count;
END;
$$ LANGUAGE plpgsql;

-- 獲取最近的錯誤信息
CREATE OR REPLACE FUNCTION get_recent_errors(limit_count INTEGER DEFAULT 50)
RETURNS TABLE (
    error_type TEXT,
    url TEXT,
    error_message TEXT,
    error_time TIMESTAMP WITH TIME ZONE,
    crawl_attempts INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'url_crawl'::TEXT as error_type,
        d.url::TEXT,
        d.error_message::TEXT,
        d.updated_at as error_time,
        d.crawl_attempts
    FROM discovered_urls d
    WHERE d.crawl_status = 'error' AND d.error_message IS NOT NULL
    
    UNION ALL
    
    SELECT 
        'sitemap_parse'::TEXT as error_type,
        s.url::TEXT,
        s.error_message::TEXT,
        s.updated_at as error_time,
        0 as crawl_attempts
    FROM sitemaps s
    WHERE s.status = 'error' AND s.error_message IS NOT NULL
    
    ORDER BY error_time DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- 檢查數據完整性
CREATE OR REPLACE FUNCTION check_data_integrity()
RETURNS TABLE (
    check_name TEXT,
    status TEXT,
    issue_count BIGINT,
    description TEXT
) AS $$
BEGIN
    -- 檢查孤立的文章塊
    RETURN QUERY
    SELECT 
        'orphaned_chunks'::TEXT as check_name,
        CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'WARNING' END as status,
        COUNT(*)::BIGINT as issue_count,
        '存在沒有對應文章的文章塊'::TEXT as description
    FROM article_chunks c
    LEFT JOIN articles a ON c.article_id = a.id
    WHERE a.id IS NULL;
    
    -- 檢查沒有塊的文章
    RETURN QUERY
    SELECT 
        'articles_without_chunks'::TEXT as check_name,
        CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'INFO' END as status,
        COUNT(*)::BIGINT as issue_count,
        '存在沒有分塊的文章'::TEXT as description
    FROM articles a
    LEFT JOIN article_chunks c ON a.id = c.article_id
    WHERE c.id IS NULL;
    
    -- 檢查重複的 URL
    RETURN QUERY
    SELECT 
        'duplicate_urls'::TEXT as check_name,
        CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'WARNING' END as status,
        COUNT(*)::BIGINT as issue_count,
        '存在重複的 URL'::TEXT as description
    FROM (
        SELECT url, COUNT(*) as cnt
        FROM discovered_urls
        GROUP BY url
        HAVING COUNT(*) > 1
    ) duplicates;
    
    -- 檢查缺失嵌入向量的塊
    RETURN QUERY
    SELECT 
        'chunks_without_embeddings'::TEXT as check_name,
        CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'INFO' END as status,
        COUNT(*)::BIGINT as issue_count,
        '存在沒有嵌入向量的文章塊'::TEXT as description
    FROM article_chunks
    WHERE embedding IS NULL;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- 實用視圖
-- =============================================

-- 文章統計視圖
CREATE OR REPLACE VIEW article_stats AS
SELECT 
    a.id,
    a.url,
    a.title,
    a.word_count,
    COUNT(c.id) as chunk_count,
    AVG(c.chunk_size) as avg_chunk_size,
    a.created_at,
    a.updated_at
FROM articles a
LEFT JOIN article_chunks c ON a.id = c.article_id
GROUP BY a.id, a.url, a.title, a.word_count, a.created_at, a.updated_at;

-- 域名統計視圖
CREATE OR REPLACE VIEW domain_summary AS
SELECT 
    d.domain,
    COUNT(DISTINCT d.id) as total_urls,
    COUNT(DISTINCT CASE WHEN d.crawl_status = 'completed' THEN d.id END) as completed_urls,
    COUNT(DISTINCT CASE WHEN d.crawl_status = 'pending' THEN d.id END) as pending_urls,
    COUNT(DISTINCT CASE WHEN d.crawl_status = 'error' THEN d.id END) as error_urls,
    COUNT(DISTINCT a.id) as total_articles,
    SUM(a.word_count) as total_words,
    COUNT(DISTINCT c.id) as total_chunks,
    MIN(d.created_at) as first_discovered,
    MAX(d.updated_at) as last_updated
FROM discovered_urls d
LEFT JOIN articles a ON d.id = a.crawled_from_url_id
LEFT JOIN article_chunks c ON a.id = c.article_id
GROUP BY d.domain;

-- =============================================
-- 最終完成信息
-- =============================================

DO $$
BEGIN
    RAISE NOTICE '=== RAG系統完整數據庫架構部署完成 ===';
    RAISE NOTICE '核心表格: discovered_urls, articles, article_chunks, sitemaps';
    RAISE NOTICE '擴展功能: get_domain_stats(), get_crawl_progress(), search_similar_content()';
    RAISE NOTICE '實用視圖: article_stats, domain_summary';
    RAISE NOTICE '使用 SELECT * FROM get_crawl_progress(); 查看爬取進度';
    RAISE NOTICE '使用 SELECT * FROM check_data_integrity(); 檢查數據完整性';
END
$$;
