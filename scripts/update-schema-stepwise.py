#!/usr/bin/env python3
"""
更新資料庫 Schema - 逐步添加 Sitemap 相關表格
由於 Supabase 的限制，我們需要逐步執行 SQL 語句
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from database.client import SupabaseClient

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 定義要執行的 SQL 語句（分步執行）
SQL_STATEMENTS = [
    # 1. 創建 sitemaps 表格
    """
    CREATE TABLE IF NOT EXISTS sitemaps (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        url TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL DEFAULT 'sitemap',
        status TEXT DEFAULT 'pending',
        title TEXT,
        description TEXT,
        lastmod TIMESTAMP WITH TIME ZONE,
        changefreq TEXT,
        priority DECIMAL(2,1),
        urls_count INTEGER DEFAULT 0,
        parsed_at TIMESTAMP WITH TIME ZONE,
        error_message TEXT,
        metadata JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    
    # 2. 創建 robots_txt 表格
    """
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
    """,
    
    # 3. 創建 discovered_urls 表格 (需要在 sitemaps 之後)
    """
    CREATE TABLE IF NOT EXISTS discovered_urls (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        url TEXT UNIQUE NOT NULL,
        source_sitemap_id UUID REFERENCES sitemaps(id) ON DELETE CASCADE,
        url_type TEXT DEFAULT 'content',
        priority DECIMAL(2,1),
        changefreq TEXT,
        lastmod TIMESTAMP WITH TIME ZONE,
        crawl_status TEXT DEFAULT 'pending',
        crawl_attempts INTEGER DEFAULT 0,
        last_crawl_at TIMESTAMP WITH TIME ZONE,
        error_message TEXT,
        article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
        metadata JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    
    # 4. 創建 sitemap_hierarchy 表格
    """
    CREATE TABLE IF NOT EXISTS sitemap_hierarchy (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        parent_sitemap_id UUID REFERENCES sitemaps(id) ON DELETE CASCADE,
        child_sitemap_id UUID REFERENCES sitemaps(id) ON DELETE CASCADE,
        level INTEGER DEFAULT 0,
        discovery_order INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE(parent_sitemap_id, child_sitemap_id)
    );
    """,
]

# 索引語句
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_sitemaps_url ON sitemaps(url);",
    "CREATE INDEX IF NOT EXISTS idx_sitemaps_type ON sitemaps(type);",
    "CREATE INDEX IF NOT EXISTS idx_sitemaps_status ON sitemaps(status);",
    "CREATE INDEX IF NOT EXISTS idx_discovered_urls_url ON discovered_urls(url);",
    "CREATE INDEX IF NOT EXISTS idx_discovered_urls_status ON discovered_urls(crawl_status);",
    "CREATE INDEX IF NOT EXISTS idx_robots_txt_domain ON robots_txt(domain);",
]

def execute_sql_via_function(client, sql: str) -> bool:
    """通過 RPC 函數執行 SQL"""
    try:
        # 創建一個臨時函數來執行 SQL
        create_temp_func = f"""
        CREATE OR REPLACE FUNCTION temp_execute_sql()
        RETURNS TEXT
        LANGUAGE plpgsql
        AS $$
        BEGIN
            {sql}
            RETURN 'SUCCESS';
        EXCEPTION
            WHEN OTHERS THEN
                RETURN 'ERROR: ' || SQLERRM;
        END;
        $$;
        """
        
        # 先創建函數
        result = client.rpc('query', {'query': create_temp_func}).execute()
        
        # 然後執行函數
        result = client.rpc('temp_execute_sql').execute()
        
        if result.data and 'SUCCESS' in str(result.data):
            return True
        else:
            logger.warning(f"SQL 執行結果: {result.data}")
            return False
            
    except Exception as e:
        logger.warning(f"SQL 執行失敗: {e}")
        return False

def update_schema_step_by_step():
    """逐步更新資料庫 schema"""
    
    try:
        logger.info("📡 連接到 Supabase...")
        client = SupabaseClient()
        supabase = client.get_client()
        
        logger.info("🔧 開始逐步執行 schema 更新...")
        
        # 執行表格創建語句
        for i, sql in enumerate(SQL_STATEMENTS, 1):
            logger.info(f"📝 執行表格創建語句 {i}/{len(SQL_STATEMENTS)}")
            try:
                # 嘗試直接創建表格 (使用 Python 代碼)
                if "sitemaps" in sql and "CREATE TABLE" in sql:
                    # 使用模型創建的方式測試表格是否存在
                    try:
                        supabase.table("sitemaps").select("*").limit(1).execute()
                        logger.info("✅ sitemaps 表格已存在")
                        continue
                    except:
                        logger.info("❌ sitemaps 表格不存在，需要創建")
                
                elif "robots_txt" in sql and "CREATE TABLE" in sql:
                    try:
                        supabase.table("robots_txt").select("*").limit(1).execute()
                        logger.info("✅ robots_txt 表格已存在")
                        continue
                    except:
                        logger.info("❌ robots_txt 表格不存在，需要創建")
                
                elif "discovered_urls" in sql and "CREATE TABLE" in sql:
                    try:
                        supabase.table("discovered_urls").select("*").limit(1).execute()
                        logger.info("✅ discovered_urls 表格已存在")
                        continue
                    except:
                        logger.info("❌ discovered_urls 表格不存在，需要創建")
                
                elif "sitemap_hierarchy" in sql and "CREATE TABLE" in sql:
                    try:
                        supabase.table("sitemap_hierarchy").select("*").limit(1).execute()
                        logger.info("✅ sitemap_hierarchy 表格已存在")
                        continue
                    except:
                        logger.info("❌ sitemap_hierarchy 表格不存在，需要創建")
                
                # 嘗試使用 RPC 執行 SQL
                if execute_sql_via_function(supabase, sql.strip()):
                    logger.info(f"✅ 語句 {i} 執行成功")
                else:
                    logger.warning(f"⚠️ 語句 {i} 執行失敗或表格已存在")
                    
            except Exception as e:
                logger.warning(f"⚠️ 語句 {i} 執行異常: {e}")
                continue
        
        # 執行索引創建語句
        logger.info("📊 創建索引...")
        for i, sql in enumerate(INDEX_STATEMENTS, 1):
            try:
                if execute_sql_via_function(supabase, sql.strip()):
                    logger.info(f"✅ 索引 {i} 創建成功")
                else:
                    logger.warning(f"⚠️ 索引 {i} 創建失敗或已存在")
            except Exception as e:
                logger.warning(f"⚠️ 索引 {i} 創建異常: {e}")
                continue
        
        logger.info("🔍 驗證表格創建結果...")
        
        # 驗證表格是否創建成功
        tables_to_check = ["sitemaps", "discovered_urls", "robots_txt", "sitemap_hierarchy"]
        success_count = 0
        
        for table in tables_to_check:
            try:
                result = supabase.table(table).select("*").limit(1).execute()
                logger.info(f"✅ {table} 表格驗證成功")
                success_count += 1
            except Exception as e:
                logger.error(f"❌ {table} 表格驗證失敗: {e}")
        
        if success_count == len(tables_to_check):
            logger.info("🎉 所有表格創建成功!")
            return True
        else:
            logger.warning(f"⚠️ 部分表格創建成功 ({success_count}/{len(tables_to_check)})")
            return False
        
    except Exception as e:
        logger.error(f"Schema 更新失敗: {e}")
        return False

if __name__ == "__main__":
    print("🔧 更新資料庫 Schema - 添加 Sitemap 表格")
    print("=" * 50)
    
    if update_schema_step_by_step():
        print("✅ Schema 更新成功!")
    else:
        print("⚠️ Schema 更新部分完成，請檢查日誌")
