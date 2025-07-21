-- Sitemap 相關表格擴展
-- 需要在現有 schema.sql 基礎上添加這些表格

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

-- 創建索引
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

-- 創建觸發器
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

-- 創建 sitemap 管理函數

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
            'by_type', jsonb_object_agg(type, type_count),
            'by_status', jsonb_object_agg(status, status_count)
        ) as details
    FROM (
        SELECT 
            type,
            status,
            COUNT(*) as type_count,
            COUNT(*) as status_count
        FROM sitemaps 
        GROUP BY GROUPING SETS ((type), (status))
    ) t
    WHERE type IS NOT NULL OR status IS NOT NULL;
    
    RETURN QUERY
    SELECT 
        'discovered_urls'::TEXT as table_name,
        COUNT(*)::BIGINT as count,
        jsonb_build_object(
            'by_type', jsonb_object_agg(url_type, type_count),
            'by_status', jsonb_object_agg(crawl_status, status_count),
            'with_articles', (SELECT COUNT(*) FROM discovered_urls WHERE article_id IS NOT NULL)
        ) as details
    FROM (
        SELECT 
            url_type,
            crawl_status,
            COUNT(*) as type_count,
            COUNT(*) as status_count
        FROM discovered_urls 
        GROUP BY GROUPING SETS ((url_type), (crawl_status))
    ) t
    WHERE url_type IS NOT NULL OR crawl_status IS NOT NULL;
    
    RETURN QUERY
    SELECT 
        'robots_txt'::TEXT as table_name,
        COUNT(*)::BIGINT as count,
        jsonb_build_object(
            'total_sitemaps', SUM(sitemaps_count),
            'total_rules', SUM(rules_count)
        ) as details
    FROM robots_txt;
END;
$$;

-- 5. 清理舊數據
CREATE OR REPLACE FUNCTION cleanup_old_sitemap_data(days_old INTEGER DEFAULT 30)
RETURNS TABLE (
    cleaned_table TEXT,
    rows_deleted BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count BIGINT;
BEGIN
    -- 清理舊的錯誤爬取記錄
    DELETE FROM discovered_urls 
    WHERE crawl_status = 'error' 
    AND updated_at < NOW() - INTERVAL '1 day' * days_old;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN QUERY SELECT 'discovered_urls (errors)'::TEXT, deleted_count;
    
    -- 清理舊的 robots.txt 記錄
    DELETE FROM robots_txt 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_old;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN QUERY SELECT 'robots_txt'::TEXT, deleted_count;
END;
$$;
