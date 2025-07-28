# Scripts 工作流程說明

這個目錄包含用於 RAG 系統完整爬蟲流程的腳本，按順序執行可建立完整的知識庫。

## 工作流程腳本

### 1. getSiteMap.py - 網站地圖發現
**目的：** 發現和分析目標網站的 sitemap 結構

```bash
python scripts/getSiteMap.py --url https://example.com --output sitemaps.txt
```

**功能：**
- 從 robots.txt 自動發現 sitemap
- 解析多層級 sitemap 結構  
- 分析 URL 優先級和更新頻率
- 保存 sitemap 層級結構到資料庫
- 生成 sitemap 清單文件

### 2. getUrls.py - URL 提取和排序
**目的：** 從 sitemap 中提取所有 URL 並按優先級排序

```bash
python scripts/getUrls.py --sitemap-list sitemaps.txt --output urls.txt
```

**功能：**
- 解析 sitemap 清單中所有 sitemap
- 提取 URL 並保留元數據（優先級、更新時間等）
- 去重和按優先級排序
- 分類 URL 類型（文章、產品、頁面等）
- 生成待爬取的 URL 清單

### 3. getChunking.py - 內容爬取和分塊  
**目的：** 爬取網頁內容並進行智能分塊

```bash
python scripts/getChunking.py --url-list urls.txt --output chunks.txt
```

**功能：**
- 批量爬取 URL 清單中的網頁
- 提取和清理網頁內容
- 使用可配置分塊策略（sliding_window、sentence、semantic）
- 保存文章和分塊到資料庫
- 生成待嵌入的分塊清單

### 4. getEmbedding.py - 向量嵌入生成
**目的：** 為分塊內容生成向量嵌入並存儲

```bash
python scripts/getEmbedding.py --chunk-list chunks.txt
```

**功能：**
- 批量生成文本向量嵌入
- 更新資料庫中的向量數據
- 驗證嵌入完整性
- 記錄處理日誌
- 準備語義搜索功能

## 完整工作流程

```bash
# 1. 發現網站地圖
python scripts/getSiteMap.py --url https://example.com --output sitemaps.txt

# 2. 提取 URL 清單
python scripts/getUrls.py --sitemap-list sitemaps.txt --output urls.txt

# 3. 爬取和分塊內容
python scripts/getChunking.py --url-list urls.txt --output chunks.txt

# 4. 生成向量嵌入
python scripts/getEmbedding.py --chunk-list chunks.txt
```

## Makefile 整合

可以通過 Makefile 執行完整流程：

```bash
make get-sitemap URL=https://example.com
make get-urls SITEMAP_LIST=sitemaps.txt  
make get-chunking URL_LIST=urls.txt
make get-embedding CHUNK_LIST=chunks.txt
```

## 配置選項

每個腳本都支援多種配置選項：

- **並發控制：** `--max-workers`, `--batch-size`
- **分塊策略：** `--chunker sliding_window|sentence|semantic`
- **分塊參數：** `--chunk-size`, `--overlap`
- **計算設備：** `--device auto|cuda|cpu`（嵌入階段）
- **輸出控制：** `--output`, `--no-db-update`

## 監控和除錯

每個腳本都提供詳細的進度報告和錯誤追蹤：

- 即時進度顯示
- 成功率統計
- 性能指標
- 錯誤摘要
- 處理日誌

## 資料庫整合

所有腳本都與 Supabase 資料庫完全整合：

- **sitemaps** 表：儲存網站地圖結構
- **discovered_urls** 表：儲存發現的 URL 列表
- **articles** 表：儲存爬取的文章內容
- **article_chunks** 表：儲存分塊和向量嵌入
- **search_logs** 表：記錄處理和搜索日誌

完成所有步驟後，RAG 系統即可進行語義搜索。
