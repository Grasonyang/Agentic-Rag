-- =============================================
-- 核心資料庫 Schema - 基礎表格和類型
-- =============================================

-- 啟用所需的擴展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================
-- 基礎 ENUM 類型定義
-- =============================================

-- 爬取狀態枚舉
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'crawl_status_enum') THEN
        CREATE TYPE crawl_status_enum AS ENUM ('pending', 'crawling', 'completed', 'error', 'skipped');
    END IF;
END$$;

-- Sitemap 類型枚舉
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sitemap_type_enum') THEN
        CREATE TYPE sitemap_type_enum AS ENUM ('sitemap', 'sitemapindex', 'urlset');
    END IF;
END$$;

-- URL 類型枚舉
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'url_type_enum') THEN
        CREATE TYPE url_type_enum AS ENUM ('content', 'sitemap', 'other');
    END IF;
END$$;

-- 搜尋類型枚舉
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'search_type_enum') THEN
        CREATE TYPE search_type_enum AS ENUM ('semantic', 'text', 'hybrid');
    END IF;
END$$;

-- 變更頻率枚舉
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'changefreq_enum') THEN
        CREATE TYPE changefreq_enum AS ENUM ('always', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'never');
    END IF;
END$$;

-- =============================================
-- 基礎觸發器函數
-- =============================================

-- 更新時間觸發器函數
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

-- 內容雜湊觸發器函數
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
