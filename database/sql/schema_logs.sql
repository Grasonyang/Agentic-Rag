-- =============================================
-- 搜尋和日誌 Schema - 搜尋記錄和系統日誌表格
-- =============================================

-- 創建 search_logs 表格
CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    query_hash TEXT,
    results_count INTEGER DEFAULT 0,
    response_time_ms INTEGER DEFAULT 0,
    search_type search_type_enum DEFAULT 'semantic',
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
