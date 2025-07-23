-- =============================================
-- 爬取管理 Schema - Sitemap 和 URL 爬取相關表格
-- =============================================

-- 創建 sitemaps 表格
CREATE TABLE IF NOT EXISTS sitemaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    type sitemap_type_enum NOT NULL DEFAULT 'sitemap',
    status crawl_status_enum DEFAULT 'pending',
    title TEXT,
    description TEXT,
    lastmod TIMESTAMP WITH TIME ZONE,
    changefreq changefreq_enum,
    priority DECIMAL(2,1) CHECK (priority >= 0.0 AND priority <= 1.0),
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
    url_type url_type_enum DEFAULT 'content',
    priority DECIMAL(2,1) CHECK (priority >= 0.0 AND priority <= 1.0),
    changefreq changefreq_enum,
    lastmod TIMESTAMP WITH TIME ZONE,
    crawl_status crawl_status_enum DEFAULT 'pending',
    crawl_attempts INTEGER DEFAULT 0,
    last_crawl_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
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
