# Agentic-Rag

這是一個基於 RAG (Retrieval-Augmented Generation) 架構的專案，透過網頁爬蟲獲取外部知識，並將其整合到語言模型中，以提供更準確、更具上下文的回答。

## 專案架構

本專案主要包含以下幾個部分：

1.  **網頁爬蟲 (Web Crawler)**: 負責從指定的 URL 抓取網頁內容。
2.  **內容處理 (Content Processing)**: 清理和轉換抓取到的 HTML 內容，例如轉換為 Markdown 格式。
3.  **文本切塊 (Chunking)**: 將處理後的文本切割成較小的片段，以便於嵌入。
4.  **嵌入 (Embedding)**: 使用指定的模型將文本片段轉換為向量。
5.  **儲存 (Storage)**: 將嵌入向量和原始文本儲存在 Supabase (Postgres) 資料庫中。

## 環境設定

在開始之前，您需要設定必要的環境變數。

1.  **複製環境變數範本**

    將 `.env.template` 檔案複製為 `.env`。此檔案包含所有必要的設定選項。

    ```bash
    cp .env.template .env
    ```

    **重要提示**: `.env` 檔案包含敏感資訊，例如資料庫密碼和 API 金鑰。**切勿**將此檔案提交到任何版本控制系統（如 Git）。專案中已包含 `.gitignore` 檔案來防止這種情況。

2.  **填寫 `.env` 檔案**

    打開 `.env` 檔案並填寫您的實際配置值。

    ```shell
    # Supabase Postgres Configuration
    DB_USER=postgres
    DB_PASSWORD=your_db_password # <-- 填寫您的資料庫密碼
    DB_HOST=db
    DB_PORT=5432
    DB_NAME=postgres
    
    POSTGRES_PASSWORD=your_postgres_password # <-- 填寫您的 Postgres 密碼
    JWT_SECRET=your_jwt_secret # <-- 填寫您的 JWT Secret
    ANON_KEY=your_anon_key # <-- 填寫您的 Supabase Anon Key
    SERVICE_ROLE_KEY=your_service_role_key # <-- 填寫您的 Supabase Service Role Key
    ...
    ```

## 主要設定選項

您可以在 `.env` 檔案中調整以下設定：

### Supabase & 資料庫
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`: Postgres 資料庫連線資訊。
- `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY`: Supabase 認證金鑰。

### 嵌入模型
- `EMBEDDING_MODEL`: 用於將文本轉換為向量的 Hugging Face 模型。預設為 `BAAI/bge-large-zh-v1.5`。

### 文本切塊
- `CHUNK_WINDOW_SIZE`: 每個文本片段的大小。
- `CHUNK_STEP_SIZE`: 相鄰文本片段之間的移動步長。

### 網頁爬蟲
- `CRAWLER_HEADLESS`: 是否以無頭模式執行瀏覽器。
- `CRAWLER_DELAY`: 每個請求之間的延遲（秒）。
- `CRAWLER_TIMEOUT`: 請求超時時間（毫秒）。
- `CRAWLER_MAX_CONCURRENT`: 最大並行請求數。
- `TARGET_URL`: 爬蟲開始的目標網址。

### 內容處理
- `PREFERRED_CONTENT_FORMAT`: 偏好的內容輸出格式 (`html`, `markdown`, `plain_text`, `json`)。
- `PRESERVE_HTML_STRUCTURE`: 是否保留原始 HTML 結構。
- `CONVERT_TO_MARKDOWN`: 是否將 HTML 轉換為 Markdown。
- `CLEAN_WHITESPACE`: 是否清理多餘的空白字元。

### 輸出
- `RESULTS_DIR`: 儲存處理結果的目錄。
- `MAX_URLS_TO_PROCESS`: 限制爬蟲處理的 URL 數量。

## 如何執行

1.  **安裝依賴** (假設使用 Python)
    ```bash
    pip install -r requirements.txt
    ```

2.  **啟動服務** (如果使用 Docker)
    ```bash
    docker-compose up -d
    ```

3.  **執行主程式**
    ```bash
    python main.py
    ```
