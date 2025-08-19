# 🕷️ Spider 模組使用指南

Spider 模組是 Agentic RAG 框架的核心爬蟲引擎，提供了高效、可擴展的網頁爬取和文本處理功能。

## 🏗️ 模組架構

```
spider/
├── __init__.py                 # 模組初始化
├── crawlers/                   # 爬蟲實現
│   ├── __init__.py
│   ├── web_crawler.py          # 基於 crawl4ai 的高性能爬蟲
│   ├── sitemap_parser.py       # Sitemap 解析和 URL 提取
│   ├── url_scheduler.py        # URL 排程器
│   └── progressive_crawler.py  # 漸進式爬蟲
├── chunking/                   # 文本分塊策略
│   ├── __init__.py
│   ├── base_chunker.py         # 基礎分塊器抽象類
│   ├── chunker_factory.py      # 分塊器工廠模式
│   ├── semantic_chunking.py    # 語義相似度分塊 (實驗性)
│   ├── sentence_chunking.py    # 基於句子邊界的智能分塊
│   └── sliding_window.py       # 滑動窗口分塊，保持上下文
└── utils/                      # 工具模組
    ├── __init__.py
    ├── rate_limiter.py         # 令牌桶算法限速器
    └── retry_manager.py        # 指數退避重試機制
```

## 🔄 爬蟲流程

讀取 `robots.txt` → `stream_discover` → `URLScheduler` → `ProgressiveCrawler`

## 🚀 核心功能

### 1. 爬蟲引擎 (`crawlers/`)

#### WebCrawler - 高性能爬蟲
基於 `crawl4ai` 的現代化爬蟲，支援 JavaScript 渲染和複雜頁面處理。

**特點:**
- 🌐 支援 JavaScript 執行和 SPA 應用
- 🔄 自動重試機制和錯誤處理
- ⚡ 異步併發處理
- 🛡️ 內建反反爬蟲機制
- 📊 詳細的性能監控

#### SitemapParser - Sitemap 解析器
專門處理 Sitemap 文件的解析和URL發現。

**特點:**
- 🗺️ 支援 XML Sitemap 和 Sitemap Index
- 🔍 遞歸解析多層 Sitemap
- 📅 支援 lastmod、changefreq、priority 屬性
- 🤖 遵循 robots.txt 規範

#### URLScheduler - URL 排程器
負責管理待處理 URL 的佇列與狀態。

**特點:**
- 🧮 優先級排程與去重
- 📋 支援資料庫或外部儲存
- 🔄 與爬蟲流程緊密整合

#### ProgressiveCrawler - 漸進式爬蟲
從 URLScheduler 取得批次 URL，漸進式擴展爬取範圍。

**特點:**
- ⛓️ 透過 `stream_discover` 鏈式發現
- 📶 可調整批次與併發
- 📈 持續更新爬取狀態

### 2. 文本分塊 (`chunking/`)

#### 分塊策略概覽

| 分塊器 | 適用場景 | 特點 | 推薦用途 |
|--------|----------|------|----------|
| `SlidingWindowChunker` | 保持上下文連續性 | 重疊分塊，避免語義割裂 | 長文章、技術文檔 |
| `SentenceChunker` | 自然語言邊界 | 基於句子邊界，語義完整 | 新聞文章、部落格 |
| `SemanticChunker` | 語義相關性 | 基於語義相似度分組 | 學術論文、研究報告 |

#### 工廠模式使用
```python
from spider.chunking.chunker_factory import ChunkerFactory

# 創建分塊器
chunker = ChunkerFactory.create_chunker('sliding_window', {
    'window_size': 100,
    'step_size': 50
})

# 執行分塊
chunks = chunker.chunk_text("很長的文章內容...")
```

### 3. 工具模組 (`utils/`)

#### RateLimiter - 速率限制器
基於令牌桶算法的高效限速器。

**特點:**
- 🪣 令牌桶算法實現
- ⚡ 支援突發流量
- 🔧 動態速率調整
- 📊 實時統計監控

#### RetryManager - 重試管理器
智能重試機制，支援指數退避和多種失敗條件處理。

**特點:**
- 📈 指數退避算法
- 🎯 條件式重試
- 📝 詳細錯誤記錄
- ⏰ 自定義超時處理

## 💡 基本使用

### 1. 簡單爬取示例

```python
import asyncio
from spider.crawlers.web_crawler import WebCrawler

async def basic_crawl():
    crawler = WebCrawler()

    # 爬取單一 URL
    result = await crawler.crawl("https://example.com")

    if result['success']:
        print(f"標題: {result['title']}")
        print(f"內容長度: {len(result['content'])}")
    else:
        print(f"爬取失敗: {result['error']}")

# 執行
asyncio.run(basic_crawl())
```

### 2. 批量爬取示例

```python
async def batch_crawl():
    crawler = WebCrawler()

    urls = [
        "https://example1.com",
        "https://example2.com",
        "https://example3.com"
    ]

    # 逐一爬取
    results = []
    for u in urls:
        results.append(await crawler.crawl(u))

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"成功: {len(successful)}, 失敗: {len(failed)}")

    # 顯示結果統計
    for result in successful:
        print(f"✅ {result['title'][:50]}...")

    for result in failed:
        print(f"❌ {result['error']}")

asyncio.run(batch_crawl())
```

### 3. Sitemap 解析示例

```python
from spider.crawlers.sitemap_parser import SitemapParser

async def sitemap_crawl():
    parser = SitemapParser()
    
    # 從 robots.txt 發現 Sitemap
    robots_url = "https://example.com/robots.txt"
    sitemaps = await parser.discover_sitemaps_from_robots(robots_url)
    
    print(f"發現 {len(sitemaps)} 個 Sitemap:")
    for sitemap in sitemaps:
        print(f"- {sitemap}")
    
    # 解析 Sitemap 獲取 URL
    all_urls = []
    for sitemap_url in sitemaps:
        urls = await parser.parse_sitemap(sitemap_url)
        all_urls.extend(urls)
        print(f"從 {sitemap_url} 獲取 {len(urls)} 個 URL")
    
    print(f"總共發現 {len(all_urls)} 個 URL")
    
    # 顯示前 10 個 URL
    for i, url_info in enumerate(all_urls[:10], 1):
        print(f"{i}. {url_info['url']} (優先級: {url_info.get('priority', 'N/A')})")

asyncio.run(sitemap_crawl())
```

## 🔧 進階配置

### 1. 爬蟲配置

```python
from spider.crawlers.web_crawler import WebCrawler
from spider.utils.rate_limiter import RateLimiter

# 創建自定義限速器
rate_limiter = RateLimiter(
    requests_per_second=2.0,  # 每秒 2 個請求
    burst_size=5              # 允許突發 5 個請求
)

# 配置爬蟲
crawler = WebCrawler(
    headless=True,                    # 無頭模式
    user_agent="CustomBot/1.0",       # 自定義 User-Agent
    timeout=30000,                    # 30 秒超時
    delay=2.5,                        # 請求間隔 2.5 秒
    rate_limiter=rate_limiter,        # 使用自定義限速器
    max_retries=3                     # 最大重試次數
)

# 設置額外選項
crawler.set_viewport(1920, 1080)     # 設置視窗大小
crawler.set_cookies(cookies_dict)    # 設置 cookies
crawler.add_headers({                # 添加自定義 headers
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate"
})
```

### 2. 分塊器配置

```python
from spider.chunking.sliding_window import SlidingWindowChunker
from spider.chunking.sentence_chunking import SentenceChunker

# 滑動窗口分塊器
sliding_chunker = SlidingWindowChunker(
    window_size=150,    # 每塊 150 個字符
    step_size=75,       # 步長 75 個字符 (50% 重疊)
    min_chunk_size=50   # 最小塊大小
)

# 句子分塊器
sentence_chunker = SentenceChunker(
    max_chunk_size=200,     # 最大塊大小
    min_chunk_size=50,      # 最小塊大小
    overlap_sentences=1     # 重疊 1 個句子
)

# 使用分塊器
text = "很長的文章內容..."

sliding_chunks = sliding_chunker.chunk_text(text)
sentence_chunks = sentence_chunker.chunk_text(text)

print(f"滑動窗口分塊: {len(sliding_chunks)} 塊")
print(f"句子分塊: {len(sentence_chunks)} 塊")
```

### 3. 錯誤處理和重試

```python
from spider.utils.retry_manager import RetryManager
from spider.crawlers.web_crawler import WebCrawler, CrawlError

crawler = WebCrawler()

# 創建重試管理器
retry_manager = RetryManager(
    max_retries=5,           # 最大重試 5 次
    base_delay=1.0,         # 基礎延遲 1 秒
    max_delay=60.0,         # 最大延遲 60 秒
    exponential_base=2.0    # 指數退避係數
)

async def robust_crawl(url):
    """帶重試的爬取函數"""
    
    @retry_manager.retry_on_exception(
        exceptions=(CrawlError, TimeoutError),
        exclude_exceptions=(ValueError,)  # 不重試的例外
    )
    async def _crawl():
        return await crawler.crawl(url)
    
    try:
        return await _crawl()
    except Exception as e:
        print(f"爬取 {url} 最終失敗: {e}")
        return {'success': False, 'error': str(e)}

# 使用
result = await robust_crawl("https://difficult-site.com")
```

## 🛠️ 自定義擴展

### 1. 自定義爬蟲

```python
from spider.crawlers.web_crawler import WebCrawler

class CustomWebCrawler(WebCrawler):
    """自定義爬蟲，支援特殊網站"""
    
    async def pre_process_url(self, url: str) -> str:
        """URL 預處理"""
        # 添加必要的參數
        if "special-site.com" in url:
            return f"{url}?format=full"
        return url
    
    async def post_process_content(self, content: str, url: str) -> str:
        """內容後處理"""
        # 移除特定的無用內容
        if "advertisement" in content.lower():
            # 移除廣告內容的邏輯
            content = self.remove_ads(content)
        
        return content
    
    def remove_ads(self, content: str) -> str:
        """移除廣告內容"""
        # 實現廣告移除邏輯
        import re
        ad_patterns = [
            r'<div class="ad-.*?</div>',
            r'<!-- AD START -->.*?<!-- AD END -->',
        ]
        
        for pattern in ad_patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        return content

# 使用自定義爬蟲
custom_crawler = CustomWebCrawler()
result = await custom_crawler.crawl("https://special-site.com/article")
```

### 2. 自定義分塊器

```python
from spider.chunking.base_chunker import BaseChunker
from typing import List
import re

class ParagraphChunker(BaseChunker):
    """基於段落的分塊器"""
    
    def __init__(self, max_paragraphs_per_chunk: int = 3, min_chunk_size: int = 100):
        self.max_paragraphs_per_chunk = max_paragraphs_per_chunk
        self.min_chunk_size = min_chunk_size
    
    def chunk_text(self, text: str) -> List[str]:
        """基於段落進行分塊"""
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', text.strip())
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for paragraph in paragraphs:
            # 如果添加這個段落會超過限制，先保存當前塊
            if (len(current_chunk) >= self.max_paragraphs_per_chunk or
                current_size + len(paragraph) > self.min_chunk_size * 3):
                
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    if len(chunk_text) >= self.min_chunk_size:
                        chunks.append(chunk_text)
                    current_chunk = []
                    current_size = 0
            
            current_chunk.append(paragraph)
            current_size += len(paragraph)
        
        # 處理最後一塊
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(chunk_text)
        
        return chunks

# 註冊自定義分塊器
from spider.chunking.chunker_factory import ChunkerFactory
ChunkerFactory.register('paragraph', ParagraphChunker)

# 使用
chunker = ChunkerFactory.create_chunker('paragraph', {
    'max_paragraphs_per_chunk': 2,
    'min_chunk_size': 150
})
```

### 3. 自定義限速器

```python
from spider.utils.rate_limiter import RateLimiter
import time
import random

class AdaptiveRateLimiter(RateLimiter):
    """自適應限速器，根據響應時間調整速率"""
    
    def __init__(self, initial_rps: float = 1.0, min_rps: float = 0.1, max_rps: float = 10.0):
        super().__init__(initial_rps, burst_size=5)
        self.min_rps = min_rps
        self.max_rps = max_rps
        self.response_times = []
        self.adjustment_threshold = 10  # 每 N 次請求調整一次
        
    async def acquire(self) -> bool:
        """獲取令牌並記錄"""
        acquired = await super().acquire()
        
        # 每隔一段時間調整速率
        if len(self.response_times) >= self.adjustment_threshold:
            self._adjust_rate()
            self.response_times = []
        
        return acquired
    
    def record_response_time(self, response_time: float):
        """記錄響應時間"""
        self.response_times.append(response_time)
    
    def _adjust_rate(self):
        """根據響應時間調整速率"""
        if not self.response_times:
            return
        
        avg_response_time = sum(self.response_times) / len(self.response_times)
        
        # 如果響應時間太長，降低速率
        if avg_response_time > 5.0:  # 5 秒
            new_rps = max(self.requests_per_second * 0.7, self.min_rps)
        # 如果響應時間很短，可以提高速率
        elif avg_response_time < 1.0:  # 1 秒
            new_rps = min(self.requests_per_second * 1.2, self.max_rps)
        else:
            return  # 不需要調整
        
        print(f"調整速率: {self.requests_per_second:.2f} -> {new_rps:.2f} RPS")
        self.requests_per_second = new_rps
        self._update_token_bucket()
    
    def _update_token_bucket(self):
        """更新令牌桶參數"""
        self.token_refill_rate = self.requests_per_second
        # 重新計算令牌補充時間
        self.last_refill = time.time()

# 使用自適應限速器
adaptive_limiter = AdaptiveRateLimiter(initial_rps=2.0)
crawler = WebCrawler()

async def crawl_with_adaptive_rate(url):
    await adaptive_limiter.acquire()

    start_time = time.time()
    result = await crawler.crawl(url)
    response_time = time.time() - start_time

    adaptive_limiter.record_response_time(response_time)
    return result
```

## ⚠️ 常見問題和解決方案

### 1. 爬蟲被封鎖

**問題**: 目標網站返回 403 或 429 錯誤

**解決方案**:
```python
# 1. 調整請求頻率
crawler = WebCrawler(delay=5.0)  # 增加延遲

# 2. 使用更真實的 User-Agent
crawler = WebCrawler(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)

# 3. 添加更多 headers
crawler.add_headers({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
})

# 4. 使用會話和 cookies
cookies = {"session_id": "your_session_id"}
crawler.set_cookies(cookies)
```

### 2. JavaScript 內容無法獲取

**問題**: 動態生成的內容無法抓取

**解決方案**:
```python
# 使用 WebCrawler
from spider.crawlers.web_crawler import WebCrawler

crawler = WebCrawler(
    headless=True,      # 啟用瀏覽器模式
    wait_time=3000,     # 等待 3 秒讓 JS 執行
    timeout=30000       # 增加超時時間
)

# 等待特定元素出現
await crawler.wait_for_element("div.content", timeout=10000)
```

### 3. 記憶體使用過多

**問題**: 爬取大量頁面後記憶體不斷增長

**解決方案**:
```python
from spider.crawlers.web_crawler import WebCrawler

# 1. 限制併發數
crawler = WebCrawler()

# 2. 定期清理
async def crawl_with_cleanup(urls, batch_size=100):
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        results = []
        for u in batch:
            results.append(await crawler.crawl(u))

        # 處理結果
        process_results(results)

        # 強制垃圾回收
        import gc
        gc.collect()

        # 短暫休息
        await asyncio.sleep(1)
```

### 4. 分塊結果不理想

**問題**: 分塊把相關內容分開了

**解決方案**:
```python
# 1. 使用滑動窗口增加重疊
chunker = SlidingWindowChunker(
    window_size=200,
    step_size=100,      # 50% 重疊
    overlap_sentences=2  # 句子級重疊
)

# 2. 嘗試語義分塊
chunker = ChunkerFactory.create_chunker('semantic', {
    'similarity_threshold': 0.7,  # 降低閾值
    'min_chunk_size': 100
})

# 3. 自定義分塊邏輯
def custom_chunk_by_headers(text):
    """基於標題結構分塊"""
    import re
    
    # 尋找標題模式
    header_pattern = r'^#{1,6}\s+.+$'
    lines = text.split('\n')
    
    chunks = []
    current_chunk = []
    
    for line in lines:
        if re.match(header_pattern, line.strip()) and current_chunk:
            # 遇到新標題，保存當前塊
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
        else:
            current_chunk.append(line)
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks
```

## 📈 性能優化建議

### 1. 爬蟲優化

- **併發控制**: 根據目標網站和網路狀況調整併發數
- **連接重用**: 使用持久連接減少建立連接的開銷
- **快取機制**: 實現內容快取避免重複爬取
- **智能重試**: 使用指數退避，避免無效重試

### 2. 分塊優化

- **預處理**: 移除不必要的空白和格式字符
- **並行處理**: 對大文本使用多進程分塊
- **快取分塊**: 對相同內容使用快取分塊結果
- **動態調整**: 根據內容類型選擇最適合的分塊策略

### 3. 記憶體優化

- **流式處理**: 對大文件使用流式讀取和處理
- **及時清理**: 處理完畢後立即釋放大對象
- **批量處理**: 分批處理大量URL，避免記憶體堆積
- **生成器使用**: 使用生成器代替列表存儲大量數據

---

**💡 提示**: 這個模組設計時充分考慮了可擴展性和靈活性。如果預設功能無法滿足您的需求，請參考自定義擴展部分來實現您的特殊需求。

**🔗 相關文檔**: 
- [完整專案文檔](../README.md)
- [資料庫模組文檔](../database/README.md)
- [API 參考文檔](https://github.com/Grasonyang/Agentic-Rag/wiki/API)
