

### 資料庫架構
- ![alt text](image.png)
- article 原始資料
    -   | 欄位名稱         | 類型        | 說明                   |
        | -------------- | ---------- | ---------------------- |
        | `id`           | UUID (PK)  | 主鍵，自動生成              |
        | `url`          | TEXT       | 原始網址                   |
        | `title`        | TEXT       | 頁面標題                   |
        | `content_md`   | TEXT       | 原始 markdown 內容         |
        | `metadata`     | JSONB      | 額外資訊（作者/時間等）     |
        | `created_at`   | TIMESTAMP  | 爬取時間                   |
- article_chunks chunked資料
    -   | 欄位名稱         | 類型        | 說明               |
        | ------------ | --------- | ---------------- |
        | `id`         | UUID (PK) | 主鍵               |
        | `article_id` | UUID (FK) | 對應 `articles.id` |
        | `chunk_idx`  | INTEGER   | 第幾段              |
        | `chunk_text` | TEXT      | 分段內容             |
        | `created_at` | TIMESTAMP | 插入時間             |
        | `embedding` | TIMESTAMP | 1024維BAAI/bge-large-zh  |
