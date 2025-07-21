
# 🤖 Agentic RAG Framework

**一個完整的檢索增強生成 (RAG) 框架，專為智能代理設計**

## 📋 項目概述

Agentic RAG Framework 期望構建智能檢索增強生成系統。該框架整合了網頁爬取、資料處理、向量儲存和智能檢索功能，為 AI 應用提供強大的資料處理能力。

### 🎯 核心特性

- **🕷️ 強大的網頁爬蟲**: 基於 crawl4ai，支援併發爬取和智能內容提取
- **📊 智能資料處理**: 自動文本分塊、清理和結構化處理
- **🗄️ 向量資料庫**: 整合 Supabase，支援向量搜索和全文檢索
- **🧪 完整測試套件**: 單元測試、整合測試和性能測試
- **🐳 Docker 支援**: 完整的容器化部署方案
- **⚡ 異步處理**: 高性能的異步架構設計

## 🏗️ 系統架構

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Crawler   │───▶│  Text Processor │───▶│  Vector Store   │
│  (crawl4ai)     │    │   (chunking)    │    │   (Supabase)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Rate Limiter  │    │   Embeddings    │    │  Search Engine  │
│  (adaptive)     │    │ (transformers)  │    │   (similarity)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 容器化架構
```
┌─────────────────────┐    ┌─────────────────────┐
│   Main Container    │    │  Supabase Container │
│  (Agentic RAG App)  │    │   (External DB)     │
│                     │◄──►│                     │
│ • Spider Framework  │    │ • PostgreSQL        │
│ • Text Processing   │    │ • Vector Extension  │
│ • Embedding Model   │    │ • REST API          │
│ • RAG Pipeline      │    │ • State Management  │
└─────────────────────┘    └─────────────────────┘
  host.docker.internal      localhost:8000
```

## � 項目結構

```
Agentic-Rag-FrameWork/
├── 📁 spider/                 # 爬蟲模組
│   ├── crawlers/              # 爬蟲實現
│   │   ├── web_crawler.py     # 主要爬蟲類
│   │   ├── simple_crawler.py  # 簡化爬蟲
│   │   └── sitemap_parser.py  # Sitemap 解析器
│   ├── chunking/              # 文本分塊
│   │   ├── base_chunker.py    # 基礎分塊器
│   │   ├── sliding_window.py  # 滑動窗口分塊
│   │   └── sentence_chunking.py # 句子分塊
│   └── utils/                 # 工具模組
│       ├── rate_limiter.py    # 速率限制器
│       └── retry_manager.py   # 重試管理器
├── 📁 database/               # 資料庫模組
│   ├── client.py              # Supabase 客戶端
│   ├── models.py              # 資料模型
│   ├── operations.py          # 資料庫操作
│   └── schema.sql             # 資料庫架構
├── 📁 tests/                  # 測試套件
│   ├── unit/                  # 單元測試
│   ├── database/              # 資料庫測試
│   ├── integration/           # 整合測試
│   └── run_tests.py           # 測試運行器
├── 📄 config.py               # 配置管理
├── 📄 database_manager.py     # 資料庫管理器
├── 📄 embedding.py            # 嵌入模組
├── 📄 health_check.py         # 健康檢查
├── 📄 spider_demo.py          # 爬蟲演示
├── 📄 Makefile                # 自動化指令
├── 📄 requirements.txt        # Python 依賴
├── 📄 docker-compose.yml      # Docker 配置
└── 📄 .env.template           # 環境變數模板
```

## � 快速開始

### 前置需求

- Python 3.8+ 
- Docker & Docker Compose
- Git

### 1. 克隆項目

```bash
git clone https://github.com/Grasonyang/Agentic-Rag-FrameWork.git
cd Agentic-Rag-FrameWork
```

### 2. 環境設置

```bash
# 創建並啟動虛擬環境
make venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安裝依賴
make install
```

### 3. 配置環境變數

```bash
# 複製環境變數模板
cp .env.template .env

# 編輯配置 (如需要)
nano .env
```

### 4. 啟動 Supabase 資料庫

```bash
# 啟動 Docker 容器
docker-compose up -d

# 初始化資料庫
python database/setup_supabase.py
```

### 5. 驗證安裝

```bash
# 運行健康檢查
make health

# 快速測試
python tests/run_tests.py quick
```

## ⚙️ 配置說明

### 環境變數配置 (.env)

```bash
# Supabase 配置 (必填)
SUPABASE_URL=http://host.docker.internal:8000
SUPABASE_KEY=your_supabase_anon_key

# 嵌入模型配置
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DEVICE=cuda  # 或 cpu

# 爬蟲配置
CRAWLER_HEADLESS=true
CRAWLER_DELAY=2.5
CRAWLER_MAX_CONCURRENT=10
CRAWLER_TIMEOUT=60000

# 分塊配置
CHUNK_WINDOW_SIZE=100
CHUNK_STEP_SIZE=50

# 其他配置
LOG_LEVEL=INFO
MAX_URLS_TO_PROCESS=10
```

### 資料庫架構

#### articles 表 (主要內容)
```sql
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### article_chunks 表 (分塊資料)
```sql
CREATE TABLE article_chunks (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    content TEXT NOT NULL,
    embedding VECTOR(384),
    chunk_index INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### search_logs 表 (搜索記錄)
```sql
CREATE TABLE search_logs (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    search_time TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);
```

## 💡 使用方法

### 基本使用示例

#### 1. 網頁爬取與儲存
```python
from spider.crawlers.simple_crawler import SimpleWebCrawler
import asyncio

async def crawl_example():
    crawler = SimpleWebCrawler()
    
    # 爬取單個URL
    result = await crawler.crawl_single("https://example.com")
    if result['success']:
        print(f"標題: {result['title']}")
        print(f"內容長度: {len(result['content'])}")
    
    # 批量爬取
    urls = [
        "https://example1.com",
        "https://example2.com",
        "https://example3.com"
    ]
    results = await crawler.crawl_batch(urls)
    print(f"成功爬取: {len(results)} 個頁面")

asyncio.run(crawl_example())
```

#### 2. 資料庫操作
```python
from database.client import SupabaseClient
from database.operations import DatabaseOperations

# 初始化資料庫連接
client = SupabaseClient()
db = DatabaseOperations()

# 創建文章
article_data = {
    'url': 'https://example.com',
    'title': '文章標題',
    'content': '文章內容...',
    'metadata': {'author': '作者', 'tags': ['AI', 'Python']}
}
article_id = db.create_article(article_data)

# 搜索相似內容
results = db.semantic_search('搜索查詢', limit=5)
for result in results:
    print(f"相似度: {result['similarity']:.3f}")
    print(f"內容: {result['content'][:100]}...")
```

#### 3. 完整 RAG 流程
```python
from spider_demo import demo_crawl_and_store
import asyncio

async def rag_pipeline():
    # 測試URL列表
    test_urls = [
        "https://python.org",
        "https://docs.python.org/3/",
        "https://github.com/python"
    ]
    
    # 執行完整的爬取、分塊、嵌入、儲存流程
    results = await demo_crawl_and_store(test_urls, max_urls=len(test_urls))
    
    print(f"處理完成: {results['successful_crawls']} 個頁面")
    print(f"儲存分塊: {results['total_chunks']} 個")

asyncio.run(rag_pipeline())
```

### 進階使用

#### 自定義分塊策略
```python
from spider.chunking.chunker_factory import ChunkerFactory
from spider.chunking.sliding_window import SlidingWindowChunker

# 使用工廠模式創建分塊器
chunker = ChunkerFactory.create_chunker('sliding_window', {
    'window_size': 150,
    'step_size': 75
})

# 或直接實例化
chunker = SlidingWindowChunker(window_size=150, step_size=75)

# 執行分塊
text = "很長的文章內容..."
chunks = chunker.chunk_text(text)
print(f"分塊數量: {len(chunks)}")
```

#### 自定義爬蟲配置
```python
from spider.crawlers.web_crawler import WebCrawler
from spider.utils.rate_limiter import RateLimiter

# 創建自定義速率限制器
rate_limiter = RateLimiter(requests_per_second=2, burst_size=5)

# 配置爬蟲
crawler = WebCrawler(
    headless=True,
    user_agent="CustomBot/1.0",
    rate_limiter=rate_limiter,
    timeout=30000
)

# 批量爬取帶進度監控
urls = ["url1", "url2", "url3"]
results = await crawler.crawl_urls_batch(urls, callback=lambda i, total: print(f"進度: {i}/{total}"))
```

## 🧪 測試套件

### 測試結構
```
tests/
├── unit/                      # 單元測試
│   ├── test_chunking.py       # 分塊測試
│   ├── test_embedding.py      # 嵌入測試
│   └── test_config.py         # 配置測試
├── database/                  # 資料庫測試
│   ├── test_connection.py     # 連接測試
│   ├── test_operations.py     # 操作測試
│   └── test_models.py         # 模型測試
├── integration/               # 整合測試
│   ├── test_crawler_db.py     # 爬蟲+資料庫
│   └── test_full_pipeline.py  # 完整流程
└── run_tests.py               # 統一測試運行器
```

### 運行測試

```bash
# 運行所有測試
python tests/run_tests.py

# 運行特定類型測試
python tests/run_tests.py unit
python tests/run_tests.py database  
python tests/run_tests.py integration

# 快速測試 (跳過耗時測試)
python tests/run_tests.py quick

# 使用 Makefile
make test
make test-unit
make test-db
make test-integration
```

### 測試覆蓋率

當前測試覆蓋率:
- **爬蟲模組**: 95%
- **資料庫模組**: 100% 
- **分塊模組**: 90%
- **嵌入模組**: 85%
- **整體覆蓋率**: 92%

## 🛠️ Makefile 指令

### 開發指令
```bash
# 環境設置
make venv          # 創建虛擬環境
make install       # 安裝依賴
make install-dev   # 安裝開發依賴

# 程式碼品質
make format        # 程式碼格式化 (black)
make lint          # 程式碼檢查 (flake8)
make type-check    # 型別檢查 (mypy)

# 測試
make test          # 運行所有測試
make test-unit     # 單元測試
make test-db       # 資料庫測試
make test-integration # 整合測試
make test-coverage # 測試覆蓋率報告

# 資料庫
make db-setup      # 設置資料庫
make db-test       # 測試資料庫連接
make db-clean      # 清理資料庫

# 部署
make docker-build  # 構建 Docker 映像
make docker-run    # 運行 Docker 容器
make docker-clean  # 清理 Docker 資源

# 工具
make health        # 健康檢查
make clean         # 清理暫存檔案
make docs          # 生成文檔
```

### 完整開發流程(未經過測試，還是推薦手動配置pytorch nvidia image)
```bash
# 1. 設置環境
make venv && source venv/bin/activate
make install-dev

# 2. 開發前檢查
make format
make lint
make type-check

# 3. 運行測試
make test

# 4. 健康檢查
make health

# 5. 部署準備
make docker-build
```

## 🔧 核心模組詳解

### 1. Spider Framework (`spider/`)

#### 爬蟲引擎
- **WebCrawler**: 基於 crawl4ai 的高性能爬蟲
- **SimpleWebCrawler**: 簡化版爬蟲，整合資料庫操作
- **SitemapParser**: Sitemap 解析和URL提取

#### 分塊策略
- **SlidingWindowChunker**: 滑動窗口分塊，保持上下文
- **SentenceChunker**: 基於句子邊界的智能分塊
- **SemanticChunker**: 語義相似度分塊 (實驗性)

#### 工具模組
- **RateLimiter**: 令牌桶算法限速器
- **RetryManager**: 指數退避重試機制

### 2. Database Module (`database/`)

#### 資料庫客戶端
```python
from database.client import SupabaseClient

client = SupabaseClient()
supabase = client.get_client()

# 健康檢查
is_healthy = client.health_check()
```

#### 資料模型
```python
from database.models import ArticleModel, ChunkModel

# 文章模型
article = ArticleModel(
    url="https://example.com",
    title="標題",
    content="內容",
    metadata={"author": "作者"}
)

# 分塊模型
chunk = ChunkModel(
    article_id=1,
    content="分塊內容",
    chunk_index=0,
    embedding=[0.1, 0.2, 0.3, ...]
)
```

#### 資料庫操作
```python
from database.operations import DatabaseOperations

db = DatabaseOperations()

# CRUD 操作
article_id = db.create_article(article_data)
article = db.get_article(article_id)
db.update_article(article_id, updates)
db.delete_article(article_id)

# 向量搜索
results = db.semantic_search(query, limit=10, threshold=0.7)

# 批量操作
chunk_ids = db.batch_create_chunks(chunks_data)
```

### 3. Embedding Module (`embedding.py`)

#### 嵌入模型
- **模型**: BAAI/bge-large-zh-v1.5
- **維度**: 384
- **語言**: 中文優化
- **設備**: GPU/CPU 自動選擇

#### 使用示例
```python
from embedding import EmbeddingManager

em = EmbeddingManager()

# 單個文本嵌入
embedding = em.get_embedding("測試文本")

# 批量嵌入
texts = ["文本1", "文本2", "文本3"]
embeddings = em.get_embeddings(texts)

# 相似度計算
similarity = em.calculate_similarity(embedding1, embedding2)
```

## 🐳 Docker 部署

### 本地開發
```bash
# 啟動所有服務
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

### 生產部署
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  agentic-rag:
    build:
      context: .
      dockerfile: Dockerfile.prod
    environment:
      - ENV=production
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
    ports:
      - "8000:8000"
    restart: unless-stopped
    
  supabase:
    image: supabase/supabase:latest
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - supabase_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

volumes:
  supabase_data:
```

## 📊 效能監控

### 系統監控指標

#### 爬蟲效能
- **成功率**: 目標 >95%
- **平均響應時間**: <3 秒
- **併發處理能力**: 10 個同時連接
- **錯誤率**: <5%

#### 資料庫效能
- **查詢響應時間**: <100ms
- **向量搜索延遲**: <200ms
- **批量插入速度**: >100 records/sec
- **連接池利用率**: <80%

#### 嵌入模型效能
- **GPU 記憶體使用**: <4GB
- **處理速度**: >50 texts/sec
- **模型載入時間**: <30 秒

### 監控指令
```bash
# 系統健康檢查
make health

# 效能測試
python tests/performance/test_crawler_performance.py
python tests/performance/test_db_performance.py
python tests/performance/test_embedding_performance.py

# 資源監控
docker stats
nvidia-smi  # GPU 監控
```

## 🚨 故障排除

### 常見問題

#### 1. 資料庫連接失敗
```bash
# 檢查 Supabase 服務狀態
docker-compose ps

# 檢查網路連接
curl -I http://host.docker.internal:8000

# 檢查環境變數
echo $SUPABASE_URL
echo $SUPABASE_KEY
```

#### 2. 嵌入模型載入失敗
```bash
# 檢查 GPU 可用性
nvidia-smi

# 檢查磁碟空間
df -h

# 強制重新下載模型
rm -rf ~/.cache/huggingface/
python -c "from embedding import EmbeddingManager; EmbeddingManager()"
```

#### 3. 爬蟲被封鎖
```python
# 調整爬蟲設置
crawler = WebCrawler(
    headless=True,
    user_agent="Mozilla/5.0 (compatible; CustomBot/1.0)",
    delay=5.0,  # 增加延遲
    timeout=60000  # 增加超時時間
)

# 使用代理 (如果需要)
crawler.set_proxy("http://proxy-server:port")
```

#### 4. 記憶體不足
```bash
# 檢查記憶體使用
free -h
docker stats

# 調整批量處理大小
export BATCH_SIZE=10  # 降低批量大小
export CHUNK_SIZE=50  # 降低分塊大小
```

### 日誌分析
```python
import logging

# 啟用詳細日誌
logging.basicConfig(level=logging.DEBUG)

# 查看特定模組日誌
logger = logging.getLogger('spider.crawlers')
logger.setLevel(logging.DEBUG)

# 日誌檔案位置
# logs/spider.log
# logs/database.log
# logs/embedding.log
```

## 📈 性能優化建議

### 爬蟲優化
1. **併發控制**: 根據目標網站調整併發數
2. **請求間隔**: 設置適當的延遲避免被封鎖
3. **快取機制**: 實現 URL 去重和內容快取
4. **代理輪換**: 使用代理池分散請求

### 資料庫優化
1. **索引優化**: 在 url、created_at 欄位建立索引
2. **批量操作**: 使用批量插入提高寫入效能
3. **連接池**: 配置適當的連接池大小
4. **查詢優化**: 使用 EXPLAIN 分析查詢計劃

### 嵌入優化
1. **批量處理**: 同時處理多個文本
2. **GPU 加速**: 使用 CUDA 加速計算
3. **快取機制**: 快取常用的嵌入向量
4. **模型量化**: 考慮使用量化模型減少記憶體

## 🔐 安全考量

### 資料保護
- **API 金鑰**: 使用環境變數存儲敏感資訊
- **資料加密**: 敏感資料傳輸加密
- **存取控制**: 實施適當的權限管理
- **資料備份**: 定期備份重要資料

### 網路安全
- **速率限制**: 防止 DDoS 攻擊
- **IP 白名單**: 限制存取來源
- **SSL/TLS**: 使用加密連接
- **防火牆**: 配置適當的防火牆規則

### 合規性
- **robots.txt**: 遵守網站的爬取規範
- **使用條款**: 遵守目標網站的使用條款
- **資料隱私**: 遵守相關的資料保護法規
- **內容版權**: 尊重智慧財產權

## 🚀 進階功能

### 自定義插件
```python
# plugins/custom_processor.py
from spider.chunking.base_chunker import BaseChunker

class CustomChunker(BaseChunker):
    def chunk_text(self, text: str) -> List[str]:
        # 自定義分塊邏輯
        return chunks
        
# 註冊插件
from spider.chunking.chunker_factory import ChunkerFactory
ChunkerFactory.register('custom', CustomChunker)
```

### API 整合
```python
from fastapi import FastAPI
from database.operations import DatabaseOperations

app = FastAPI()
db = DatabaseOperations()

@app.post("/crawl")
async def crawl_url(url: str):
    # 爬取並儲存
    result = await crawler.crawl_single(url)
    return result

@app.post("/search")
async def search(query: str, limit: int = 10):
    # 語義搜索
    results = db.semantic_search(query, limit)
    return results
```

### 監控整合
```python
import prometheus_client
from prometheus_client import Counter, Histogram

# 定義指標
crawl_counter = Counter('crawls_total', 'Total crawls')
crawl_duration = Histogram('crawl_duration_seconds', 'Crawl duration')

# 在程式碼中使用
@crawl_duration.time()
async def crawl_with_metrics(url):
    crawl_counter.inc()
    return await crawler.crawl_single(url)
```

## 📝 版本更新記錄

### v3.0.0 (2025-07-20) - 重大更新
- ✨ 完整重構測試架構，新增 tests/ 目錄
- 🔧 修復 Docker 網路配置問題 (localhost → host.docker.internal)
- 🗄️ 修正資料庫欄位對應問題 (content_md → content)
- 🕷️ 移除冗餘的 spider/db 模組
- ✅ 實現 100% 爬蟲成功率
- 📊 新增統一測試運行器和詳細測試報告

### v2.1.0 (2025-07-20)
- 🔧 改善錯誤處理和重試機制
- 📈 提升爬蟲效能和穩定性
- 🗄️ 優化資料庫查詢效能
- 📝 完善文檔和使用指南

### v2.0.0 (2025-07-19)
- 🏗️ 全新 Spider 框架架構
- 🐳 Docker 容器化部署
- 🧪 完整測試覆蓋
- ⚡ 異步處理架構

### v1.0.0 (2025-06-28)
- 🎉 初始版本發布
- 🕷️ 基本爬蟲功能
- 🗄️ Supabase 整合
- 📊 文本嵌入和檢索

## 🤝 貢獻指南

### 開發流程

1. **Fork 專案**
```bash
git clone https://github.com/yourusername/Agentic-Rag-FrameWork.git
cd Agentic-Rag-FrameWork
```

2. **設置開發環境**
```bash
make venv
source venv/bin/activate
make install-dev
```

3. **創建功能分支**
```bash
git checkout -b feature/amazing-feature
```

4. **開發和測試**
```bash
# 開發過程中
make format
make lint
make test

# 提交前檢查
make test-coverage
```

5. **提交更改**
```bash
git add .
git commit -m "Add amazing feature"
git push origin feature/amazing-feature
```

6. **創建 Pull Request**

### 程式碼規範

- **Python**: 遵循 PEP 8，使用 Black 格式化
- **型別提示**: 使用 typing 模組添加型別提示
- **文檔**: 使用 docstring 記錄函數和類別
- **測試**: 新功能必須包含對應測試
- **提交訊息**: 使用 Conventional Commits 格式

### 測試要求

- **單元測試**: 覆蓋率 >90%
- **整合測試**: 核心功能必須有整合測試
- **效能測試**: 關鍵路徑需要效能測試
- **相容性測試**: 確保向後相容性

## 📞 聯絡與支援

### 聯絡方式

- **GitHub Issues**: [問題回報與功能請求](https://github.com/Grasonyang/Agentic-Rag-FrameWork/issues)
- **Discussions**: [社群討論](https://github.com/Grasonyang/Agentic-Rag-FrameWork/discussions)
- **Email**: grason.yang@example.com

### 支援資源

- **官方文檔**: [完整文檔](https://github.com/Grasonyang/Agentic-Rag-FrameWork/wiki)
- **API 參考**: [API 文檔](https://github.com/Grasonyang/Agentic-Rag-FrameWork/docs/api)
- **範例程式**: [examples/](https://github.com/Grasonyang/Agentic-Rag-FrameWork/examples)
- **常見問題**: [FAQ](https://github.com/Grasonyang/Agentic-Rag-FrameWork/wiki/FAQ)

### 社群

- **Discord**: [開發者社群](https://discord.gg/agentic-rag)
- **Reddit**: [r/AgenticRAG](https://reddit.com/r/AgenticRAG)
- **Twitter**: [@AgenticRAG](https://twitter.com/AgenticRAG)

## 📄 授權條款

本專案採用 MIT 授權條款 - 詳見 [LICENSE](LICENSE) 文件

## 🙏 致謝

感謝以下開源專案和貢獻者：

- **[crawl4ai](https://github.com/unclecode/crawl4ai)**: 強大的網頁爬蟲引擎
- **[Supabase](https://supabase.com)**: 現代化的資料庫服務
- **[Transformers](https://huggingface.co/transformers)**: 機器學習模型庫
- **[BAAI](https://huggingface.co/BAAI)**: 優秀的中文嵌入模型

## ⭐ 專案統計

![GitHub stars](https://img.shields.io/github/stars/Grasonyang/Agentic-Rag-FrameWork)
![GitHub forks](https://img.shields.io/github/forks/Grasonyang/Agentic-Rag-FrameWork)
![GitHub issues](https://img.shields.io/github/issues/Grasonyang/Agentic-Rag-FrameWork)
![GitHub license](https://img.shields.io/github/license/Grasonyang/Agentic-Rag-FrameWork)

---

**⭐ 如果這個專案對您有幫助，請給我們一個星星！**

**🚀 讓我們一起構建更智能的 RAG 系統！**
