#!/usr/bin/env python3
"""
更新資料庫 Schema - 添加 Sitemap 相關表格
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from database.client import SupabaseClient

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def update_schema():
    """更新資料庫 schema 以包含 sitemap 相關表格"""
    
    # 讀取 sitemap schema
    schema_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                               'database', 'schema_sitemap.sql')
    
    if not os.path.exists(schema_file):
        logger.error(f"找不到 schema 文件: {schema_file}")
        return False
    
    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        logger.info("📡 連接到 Supabase...")
        client = SupabaseClient()
        supabase = client.get_client()
        
        logger.info("🔧 執行 schema 更新...")
        
        # 分割 SQL 語句並逐一執行
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        for i, statement in enumerate(statements):
            if statement:
                try:
                    logger.info(f"執行語句 {i+1}/{len(statements)}")
                    # 使用 rpc 來執行 SQL
                    supabase.rpc('exec_sql', {'sql': statement}).execute()
                    logger.debug(f"✅ 語句執行成功: {statement[:50]}...")
                except Exception as e:
                    logger.warning(f"語句執行失敗 (可能已存在): {statement[:50]}... - {e}")
                    continue
        
        logger.info("✅ Schema 更新完成!")
        
        # 驗證新表格是否創建成功
        logger.info("🔍 驗證新表格...")
        try:
            supabase.table("sitemaps").select("*").limit(1).execute()
            logger.info("✅ sitemaps 表格創建成功")
        except Exception as e:
            logger.error(f"❌ sitemaps 表格驗證失敗: {e}")
        
        try:
            supabase.table("discovered_urls").select("*").limit(1).execute()
            logger.info("✅ discovered_urls 表格創建成功")
        except Exception as e:
            logger.error(f"❌ discovered_urls 表格驗證失敗: {e}")
        
        try:
            supabase.table("robots_txt").select("*").limit(1).execute()
            logger.info("✅ robots_txt 表格創建成功")
        except Exception as e:
            logger.error(f"❌ robots_txt 表格驗證失敗: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Schema 更新失敗: {e}")
        return False

if __name__ == "__main__":
    print("🔧 更新資料庫 Schema - 添加 Sitemap 表格")
    print("=" * 50)
    
    if update_schema():
        print("✅ Schema 更新成功!")
    else:
        print("❌ Schema 更新失敗!")
        sys.exit(1)
