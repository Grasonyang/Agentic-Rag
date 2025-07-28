-- =============================================
-- 修复 Supabase 权限问题
-- 为 service_role 角色添加完整权限
-- =============================================

-- 授予 service_role 角色对所有表格的完整权限
GRANT ALL PRIVILEGES ON TABLE articles TO service_role;
GRANT ALL PRIVILEGES ON TABLE article_chunks TO service_role;
GRANT ALL PRIVILEGES ON TABLE embeddings_cache TO service_role;
GRANT ALL PRIVILEGES ON TABLE sitemaps TO service_role;
GRANT ALL PRIVILEGES ON TABLE sitemap_hierarchy TO service_role;
GRANT ALL PRIVILEGES ON TABLE discovered_urls TO service_role;
GRANT ALL PRIVILEGES ON TABLE robots_txt TO service_role;
GRANT ALL PRIVILEGES ON TABLE search_logs TO service_role;
GRANT ALL PRIVILEGES ON TABLE task_execution_logs TO service_role;

-- 授予对所有序列的权限
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- 授予对所有函数的执行权限
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- 确保 service_role 可以绕过 RLS (如果启用了的话)
ALTER ROLE service_role SET row_security = off;

-- 显示成功消息
DO $$
BEGIN
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Service Role 权限修复完成！';
    RAISE NOTICE '======================================';
END;
$$;
