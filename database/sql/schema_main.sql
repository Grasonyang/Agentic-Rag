-- =============================================
-- 主要 Schema 檔案 - 引入所有子 schema
-- =============================================
-- 
-- 使用方式：
-- 1. 先執行此檔案來建立完整的資料庫結構
-- 2. 或者根據需要單獨執行各個子檔案
--
-- 檔案結構：
-- - schema_core.sql: 基礎類型和觸發器函數
-- - schema_content.sql: 內容管理相關表格
-- - schema_crawl.sql: 爬取管理相關表格  
-- - schema_logs.sql: 搜尋和日誌相關表格
-- - schema_functions.sql: 所有資料庫函數
-- =============================================

-- 1. 載入基礎核心 Schema (ENUM 類型和基礎函數)
\i schema_core.sql

-- 2. 載入內容管理 Schema (文章和分塊)
\i schema_content.sql

-- 3. 載入爬取管理 Schema (Sitemap 和 URL 管理)
\i schema_crawl.sql

-- 4. 載入搜尋和日誌 Schema
\i schema_logs.sql

-- 5. 載入所有資料庫函數
\i schema_functions.sql

-- 完成訊息
DO $$
BEGIN
    RAISE NOTICE '======================================';
    RAISE NOTICE '資料庫 Schema 初始化完成';
    RAISE NOTICE '======================================';
    RAISE NOTICE '已創建的表格：';
    RAISE NOTICE '- articles (文章)';
    RAISE NOTICE '- article_chunks (文章分塊)';
    RAISE NOTICE '- embeddings_cache (向量快取)';
    RAISE NOTICE '- sitemaps (網站地圖)';
    RAISE NOTICE '- sitemap_hierarchy (地圖層級)';
    RAISE NOTICE '- discovered_urls (發現的URL)';
    RAISE NOTICE '- robots_txt (機器人協議)';
    RAISE NOTICE '- search_logs (搜尋日誌)';
    RAISE NOTICE '======================================';
    RAISE NOTICE '可用的主要函數：';
    RAISE NOTICE '- clear_all_data(): 清除所有資料';
    RAISE NOTICE '- get_all_tables(): 獲取所有表格資訊';
    RAISE NOTICE '- get_table_columns(table_name): 獲取表格欄位';
    RAISE NOTICE '- semantic_search(): 語義搜尋';
    RAISE NOTICE '- get_sitemap_hierarchy(): 獲取地圖層級';
    RAISE NOTICE '- get_crawl_queue(): 獲取爬取佇列';
    RAISE NOTICE '======================================';
END;
$$;
