# 🧪 測試文檔

## 概述

本項目包含完整的測試套件，用於驗證 Agentic RAG Framework 的各個功能模組。測試分為三個主要類別：

- **單元測試** (`tests/unit/`) - 測試個別組件功能
- **資料庫測試** (`tests/database/`) - 測試資料庫操作
- **整合測試** (`tests/integration/`) - 測試完整工作流程

## 📁 測試結構

```
tests/
├── __init__.py                 # 測試配置和共用工具
├── run_tests.py               # 統一測試運行器
├── README.md                  # 本文檔
├── unit/
│   └── test_crawler.py        # 爬蟲功能單元測試
├── database/
│   └── test_database_operations.py  # 資料庫操作測試
└── integration/
    └── test_full_system.py    # 完整系統整合測試
```

## 🚀 快速開始

### 1. 環境準備

確保以下服務正在運行：
- Supabase 容器 (localhost:8000 或 host.docker.internal:8000)
- 網絡連接正常

### 2. 運行測試

```bash
# 進入測試目錄
cd tests

# 運行所有測試
python run_tests.py all

# 運行特定測試
python run_tests.py quick       # 快速測試
python run_tests.py unit        # 單元測試
python run_tests.py database    # 資料庫測試
python run_tests.py integration # 整合測試

# 查看幫助
python run_tests.py help
```

## 📋 測試類型說明

### 1. 快速測試 (`quick`)

**用途**: 快速驗證系統基本功能
**時間**: ~30 秒
**內容**:
- 資料庫連接測試
- 單個 URL 爬取測試
- 基本資料儲存測試

**適用場景**: 開發過程中的快速驗證

### 2. 單元測試 (`unit`)

**用途**: 測試爬蟲組件的各項功能
**時間**: ~2-3 分鐘
**內容**:
- 單個 URL 爬取
- 批量 URL 爬取
- 錯誤處理機制
- 內容提取驗證
- 性能測試

**覆蓋範圍**:
- `spider.crawlers.simple_crawler.SimpleWebCrawler`
- 爬蟲併發處理
- 異常情況處理

### 3. 資料庫測試 (`database`)

**用途**: 驗證資料庫操作的正確性
**時間**: ~1-2 分鐘
**內容**:
- 資料庫連接測試
- 表格訪問驗證
- 直接插入操作
- DatabaseOperations 類別測試
- 批量操作測試

**覆蓋範圍**:
- `database.SupabaseClient`
- `database.DatabaseOperations`
- `database.ArticleModel`

### 4. 整合測試 (`integration`)

**用途**: 測試完整的工作流程
**時間**: ~3-5 分鐘
**內容**:
- 爬取並儲存流程
- 批量爬取並儲存
- 資料一致性驗證
- 重複資料處理

**覆蓋範圍**:
- 爬蟲 + 資料庫完整流程
- 資料完整性
- 業務邏輯驗證

### 5. 完整測試 (`all`)

**用途**: 運行所有測試套件
**時間**: ~5-8 分鐘
**內容**: 按順序執行上述所有測試

## 📊 測試結果解讀

### 成功標準

- **快速測試**: 3/3 基本功能正常
- **單元測試**: ≥80% 測試通過
- **資料庫測試**: 所有操作正常
- **整合測試**: ≥75% 工作流程成功

### 常見問題

#### 1. 資料庫連接失敗
```
❌ 資料庫連接失敗
```
**解決方案**:
- 檢查 Supabase 容器是否運行
- 確認配置中的 URL 正確 (host.docker.internal:8000)
- 驗證網絡連接

#### 2. 爬蟲測試失敗
```
❌ 單 URL 爬取 FAIL
```
**解決方案**:
- 檢查網絡連接
- 確認測試 URL 可訪問
- 檢查防火牆設置

#### 3. 資料庫寫入失敗
```
❌ DatabaseOperations 寫入失敗
```
**解決方案**:
- 確認資料庫表格已創建
- 檢查權限設置
- 運行 `python init_database.py`

## 🔧 自定義測試

### 添加新的測試 URL

編輯 `tests/__init__.py`:
```python
TEST_URLS = [
    "https://your-test-url.com",
    # ... 其他 URL
]
```

### 修改測試配置

編輯 `tests/__init__.py`:
```python
TEST_CONFIG = {
    "max_concurrent": 5,        # 併發數
    "timeout": 60,              # 超時時間
    "retry_attempts": 3,        # 重試次數
    "test_batch_size": 10       # 批量大小
}
```

### 創建新的測試文件

1. 在適當的子目錄創建 `.py` 文件
2. 繼承測試基類或使用共用工具
3. 使用 `print_test_result()` 報告結果
4. 在 `run_tests.py` 中註冊新測試

## 📈 持續整合

### 在 CI/CD 中使用

```bash
# 只運行快速測試
python tests/run_tests.py quick

# 運行完整測試套件
python tests/run_tests.py all
```

### 測試覆蓋率

建議定期運行完整測試套件以確保：
- 所有功能模組正常工作
- 新的代碼變更不破壞現有功能
- 系統在不同環境下的穩定性

## 🛠️ 故障排除

### 調試模式

設置環境變數以獲得更詳細的日誌：
```bash
export PYTHONPATH=.
export LOG_LEVEL=DEBUG
python tests/run_tests.py [test_type]
```

### 手動測試步驟

如果自動測試失敗，可以手動驗證：

1. **資料庫連接**:
   ```python
   from database import SupabaseClient
   client = SupabaseClient()
   print(client.connect())
   ```

2. **爬蟲功能**:
   ```python
   import asyncio
   from spider.crawlers.simple_crawler import SimpleWebCrawler
   
   async def test():
       async with SimpleWebCrawler() as crawler:
           result = await crawler.crawl_url("https://example.com")
           print(result.success, result.title)
   
   asyncio.run(test())
   ```

3. **資料庫操作**:
   ```python
   from database import DatabaseOperations, ArticleModel
   
   client = SupabaseClient()
   client.connect()
   ops = DatabaseOperations(client)
   
   article = ArticleModel(url="test", title="test", content="test")
   print(ops.create_article(article))
   ```

## 📞 支援

如果遇到測試問題：
1. 檢查本文檔的故障排除部分
2. 確認環境配置正確
3. 查看詳細的錯誤日誌
4. 嘗試手動測試步驟
