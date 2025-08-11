# 資料庫初始化報告
初始化時間: 2025-08-11 19:16:36

## 初始化前狀態
- 總記錄數: 0
- 自定義函數: 5/5 存在
- 資料庫用戶: postgres
- discovered_urls: 0 筆記錄
- articles: 0 筆記錄
- article_chunks: 0 筆記錄
- sitemaps: 0 筆記錄

## 數據清理結果
- 無需清理數據

## Schema 執行結果
- 狀態: ⚠️ partial
- 成功語句: 58
- 失敗語句: 16
- 錯誤:
  - ❌ 語句 47 執行失敗: policy "Enable read access for all users" for table "discovered_urls" already exists

  - ❌ 語句 48 執行失敗: policy "Enable insert for authenticated users" for table "discovered_urls" already exists

  - ❌ 語句 49 執行失敗: policy "Enable update for authenticated users" for table "discovered_urls" already exists

  - ❌ 語句 50 執行失敗: policy "Enable delete for authenticated users" for table "discovered_urls" already exists

  - ❌ 語句 51 執行失敗: policy "Enable read access for all users" for table "articles" already exists


## 基本數據初始化
- 狀態: ✅ success
  - ✅ 擴展 uuid-ossp 已確保啟用
  - ✅ 擴展 vector 已確保啟用
  - ✅ 表格 discovered_urls RLS 已啟用
  - ✅ 表格 articles RLS 已啟用
  - ✅ 表格 article_chunks RLS 已啟用
  - ✅ 表格 sitemaps RLS 已啟用
  - ✅ 統計信息已更新

## 初始化驗證
- 整體健康: 🟢 healthy
- 表格狀態:
  - ✅ discovered_urls: 0 筆記錄
  - ✅ articles: 0 筆記錄
  - ✅ article_chunks: 0 筆記錄
  - ✅ sitemaps: 0 筆記錄
- 函數狀態:
  - ✅ get_crawl_progress
  - ✅ get_domain_stats
  - ✅ search_similar_content
  - ✅ cleanup_duplicate_articles
  - ✅ check_data_integrity

## 錯誤記錄
- ❌ 語句 47 執行失敗: policy "Enable read access for all users" for table "discovered_urls" already exists

- ❌ 語句 48 執行失敗: policy "Enable insert for authenticated users" for table "discovered_urls" already exists

- ❌ 語句 49 執行失敗: policy "Enable update for authenticated users" for table "discovered_urls" already exists

- ❌ 語句 50 執行失敗: policy "Enable delete for authenticated users" for table "discovered_urls" already exists

- ❌ 語句 51 執行失敗: policy "Enable read access for all users" for table "articles" already exists

- ❌ 語句 52 執行失敗: policy "Enable insert for authenticated users" for table "articles" already exists

- ❌ 語句 53 執行失敗: policy "Enable update for authenticated users" for table "articles" already exists

- ❌ 語句 54 執行失敗: policy "Enable delete for authenticated users" for table "articles" already exists

- ❌ 語句 55 執行失敗: policy "Enable read access for all users" for table "article_chunks" already exists

- ❌ 語句 56 執行失敗: policy "Enable insert for authenticated users" for table "article_chunks" already exists
