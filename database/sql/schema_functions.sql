-- =============================================
-- 資料庫函數集合 - 所有資料庫管理和查詢函數
-- =============================================

-- =============================================
-- 基礎資料管理函數
-- =============================================

-- 1. 清除所有資料
CREATE OR REPLACE FUNCTION clear_all_data()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    -- 清除所有表格資料（保留表格結構）
    TRUNCATE TABLE article_chunks CASCADE;
    TRUNCATE TABLE search_logs CASCADE;
    TRUNCATE TABLE embeddings_cache CASCADE;
    TRUNCATE TABLE discovered_urls CASCADE;
    TRUNCATE TABLE sitemap_hierarchy CASCADE;
    TRUNCATE TABLE sitemaps CASCADE;
    TRUNCATE TABLE robots_txt CASCADE;
    TRUNCATE TABLE articles CASCADE;
    
    RAISE NOTICE '所有表格資料已清除';
END;
$$;

-- 2. 獲取所有資料表
CREATE OR REPLACE FUNCTION get_all_tables()
RETURNS TABLE (
    table_name TEXT,
    table_type TEXT,
    row_count BIGINT,
    table_size TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.tablename::TEXT as table_name,
        'table'::TEXT as table_type,
        COALESCE(s.n_tup_ins - s.n_tup_del, 0)::BIGINT as row_count,
        pg_size_pretty(pg_total_relation_size(quote_ident(t.tablename)::regclass))::TEXT as table_size
    FROM pg_tables t
    LEFT JOIN pg_stat_user_tables s ON t.tablename = s.relname
    WHERE t.schemaname = 'public'
    AND t.tablename NOT LIKE 'pg_%'
    AND t.tablename NOT LIKE 'sql_%'
    ORDER BY t.tablename;
END;
$$;

-- 3. 獲取特定資料表的欄位
CREATE OR REPLACE FUNCTION get_table_columns(table_name_param TEXT)
RETURNS TABLE (
    column_name TEXT,
    data_type TEXT,
    is_nullable TEXT,
    column_default TEXT,
    is_primary_key BOOLEAN,
    is_foreign_key BOOLEAN,
    foreign_table TEXT,
    foreign_column TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.column_name::TEXT,
        CASE 
            WHEN c.data_type = 'USER-DEFINED' THEN c.udt_name::TEXT
            ELSE c.data_type::TEXT
        END as data_type,
        c.is_nullable::TEXT,
        c.column_default::TEXT,
        -- 檢查是否為主鍵
        CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END as is_primary_key,
        -- 檢查是否為外鍵
        CASE WHEN fk.column_name IS NOT NULL THEN TRUE ELSE FALSE END as is_foreign_key,
        fk.foreign_table_name::TEXT as foreign_table,
        fk.foreign_column_name::TEXT as foreign_column
    FROM information_schema.columns c
    -- 主鍵資訊
    LEFT JOIN (
        SELECT 
            kcu.column_name,
            kcu.table_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_schema = 'public'
    ) pk ON c.column_name = pk.column_name AND c.table_name = pk.table_name
    -- 外鍵資訊
    LEFT JOIN (
        SELECT 
            kcu.column_name,
            kcu.table_name,
            ccu.table_name as foreign_table_name,
            ccu.column_name as foreign_column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu 
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
    ) fk ON c.column_name = fk.column_name AND c.table_name = fk.table_name
    WHERE c.table_schema = 'public'
    AND c.table_name = table_name_param
    ORDER BY c.ordinal_position;
END;
$$;

-- =============================================
-- 向量搜尋函數
-- =============================================

-- 向量搜索函數
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

-- 語義搜索函數 (結合向量和文本搜索)
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

-- =============================================
-- Sitemap 管理函數
-- =============================================

-- 獲取 sitemap 層級結構
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
                s.type::TEXT,
                0 as level,
                NULL::UUID as parent_id,
                s.urls_count,
                s.status::TEXT
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
                s.type::TEXT,
                st.level + 1 as level,
                sh.parent_sitemap_id as parent_id,
                s.urls_count,
                s.status::TEXT
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
                s.type::TEXT,
                0 as level,
                NULL::UUID as parent_id,
                s.urls_count,
                s.status::TEXT
            FROM sitemaps s
            WHERE s.id = root_sitemap_id
            
            UNION ALL
            
            -- 子級節點
            SELECT 
                s.id as sitemap_id,
                s.url,
                s.type::TEXT,
                st.level + 1 as level,
                sh.parent_sitemap_id as parent_id,
                s.urls_count,
                s.status::TEXT
            FROM sitemaps s
            JOIN sitemap_hierarchy sh ON s.id = sh.child_sitemap_id
            JOIN sitemap_tree st ON sh.parent_sitemap_id = st.sitemap_id
        )
        SELECT * FROM sitemap_tree ORDER BY level, url;
    END IF;
END;
$$;

-- 獲取待爬取的 URL (按優先級排序)
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
    AND (url_type_filter IS NULL OR du.url_type::TEXT = url_type_filter)
    ORDER BY 
        COALESCE(du.priority, 0.5) DESC,
        du.lastmod DESC NULLS LAST,
        du.crawl_attempts ASC,
        du.created_at ASC
    LIMIT limit_count;
END;
$$;

-- 更新爬取狀態
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
        crawl_status = new_status::crawl_status_enum,
        last_crawl_at = NOW(),
        crawl_attempts = crawl_attempts + 1,
        article_id = COALESCE(article_id_param, article_id),
        error_message = error_msg,
        updated_at = NOW()
    WHERE id = url_id;
END;
$$;

-- =============================================
-- 統計和報告函數
-- =============================================

-- 獲取資料庫統計
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

-- 獲取 sitemap 統計信息
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
            'by_type', jsonb_object_agg(COALESCE(type::TEXT, 'unknown'), count),
            'by_status', jsonb_object_agg(COALESCE(status::TEXT, 'unknown'), count)
        ) as details
    FROM (
        SELECT type, COUNT(*) as count FROM sitemaps GROUP BY type
        UNION ALL
        SELECT status::TEXT, COUNT(*) as count FROM sitemaps GROUP BY status
    ) t;
    
    RETURN QUERY
    SELECT 
        'discovered_urls'::TEXT as table_name,
        COUNT(*)::BIGINT as count,
        jsonb_build_object(
            'by_type', jsonb_object_agg(COALESCE(url_type::TEXT, 'unknown'), count),
            'by_status', jsonb_object_agg(COALESCE(crawl_status::TEXT, 'unknown'), count),
            'with_articles', (SELECT COUNT(*) FROM discovered_urls WHERE article_id IS NOT NULL)
        ) as details
    FROM (
        SELECT url_type::TEXT, COUNT(*) as count FROM discovered_urls GROUP BY url_type
        UNION ALL
        SELECT crawl_status::TEXT, COUNT(*) as count FROM discovered_urls GROUP BY crawl_status
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
