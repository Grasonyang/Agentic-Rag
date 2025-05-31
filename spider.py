import asyncio
import xml.etree.ElementTree as ET
from typing import List
from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode, RateLimiter
from crawl4ai.config import GeolocationConfig
from crawl4ai.crawlers import AsyncWebCrawler

def detect_sitemap_type(xml_text: str) -> str:
    try:
        root = ET.fromstring(xml_text)
        tag = root.tag.lower()
        if tag.endswith("sitemapindex"):
            return "index"
        elif tag.endswith("urlset"):
            return "urlset"
        else:
            return "unknown"
    except Exception:
        return "unknown"

def extract_locs(xml_text: str, tag: str) -> List[str]:
    root = ET.fromstring(xml_text)
    locs = []
    if tag == "index":
        for sm in root.findall("{*}sitemap"):
            loc = sm.find("{*}loc")
            if loc is not None:
                locs.append(loc.text.strip())
    elif tag == "urlset":
        for url in root.findall("{*}url"):
            loc = url.find("{*}loc")
            if loc is not None:
                locs.append(loc.text.strip())
    return locs

async def parse_sitemap(session, url: str, collected_urls: List[str]):
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                print(f"❌ 無法讀取 {url}")
                return
            xml_text = await resp.text()
    except Exception as e:
        print(f"❌ 請求錯誤 {url}: {e}")
        return

    sitemap_type = detect_sitemap_type(xml_text)
    if sitemap_type == "index":
        locs = extract_locs(xml_text, "index")
        for loc in locs:
            await parse_sitemap(session, loc, collected_urls)
    elif sitemap_type == "urlset":
        locs = extract_locs(xml_text, "urlset")
        collected_urls.extend(locs)
    else:
        print(f"⚠️ 未知 sitemap 類型：{url}")

async def web_crawler(urls: List[str]):
    
    # BrowserConfig 增強配置
    browser_config = BrowserConfig(
        verbose=True,  # 啟用詳細日誌，有助於調試
        user_agent_mode="random",  # 隨機化 User-Agent，避免固定模式被檢測
        browser_type="chromium",  # 選擇瀏覽器引擎，可根據目標網站測試 "firefox" 或 "webkit"
        headless=True,  # 無頭模式運行，高效但需配合其他參數增強隱蔽性
        viewport_width=1920,  # 模擬常見桌面視窗寬度
        viewport_height=1080,  # 模擬常見桌面視窗高度
        extra_args=["--disable-blink-features=AutomationControlled"],  # 禁用常見無頭瀏覽器檢測標誌
        # proxy_config={
        #     "server": "your_proxy_server:port",  # 配置代理服務器，隱藏真實 IP
        #     "username": "your_proxy_username",
        #     "password": "your_proxy_password"
        # },
        use_persistent_context=True,  # 使用持久性瀏覽器配置文件，保留 cookies 和本地儲存
        user_data_dir="./user_data",  # 指定儲存持久性資料的目錄
        # cookies=[{"name": "sessionid", "value": "your_session_id", "domain": ".example.com"}], # 根據網站需求設定初始 cookies
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "zh-TW,en-US;q=0.9,en;q=0.8",  # 模擬標準瀏覽器請求頭
            "Referer": "https://www.google.com/"  # 模擬來源網站
        },
        text_mode=False,  # 根據需求決定是否禁用圖片載入，若僅需文本可設為 True
        light_mode=True  # 根據需求決定是否關閉背景功能，若需提升效率可設為 True
    )

    # CrawlerRunConfig 增強配置
    run_config = CrawlerRunConfig(
        verbose=True,  # 啟用詳細日誌，有助於調試
        # 內容篩選
        word_count_threshold=10,  # 忽略字數過少的文本區塊
        excluded_tags=['form', 'header'],  # 移除特定 HTML 標籤
        exclude_external_links=True,  # 排除外部連結
        # 內容處理
        process_iframes=True,  # 控制是否處理 iframe 內容
        remove_overlay_elements=True,  # 移除頁面上的疊加元素
        # 快取控制
        cache_mode=CacheMode.ENABLED,  # 適當快取可以減少重複請求

        # 人類行為模式模擬
        # js_code=[
        #     "window.scrollTo(0, document.body.scrollHeight);",  # 模擬滾動到底部，觸發惰性載入
        #     "document.querySelector('.load-more-button')?.click();"  # 模擬點擊「載入更多」按鈕 (範例)
        # ],
        wait_for="js:() => document.readyState === 'complete'",  # 等待頁面完全載入
        # wait_for="css:.main-content", # 也可以等待特定元素出現
        # locale="zh-TW",  # 模擬瀏覽器語言環境
        # timezone_id="Asia/Taipei",  # 模擬瀏覽器時區
        # geolocation=GeolocationConfig(latitude=24.0776, longitude=120.5658),  # 模擬特定 GPS 座標 (彰化市為例)

        # 請求頻率控制與錯誤處理
        enable_rate_limiting=True,  # 啟用速率限制
        rate_limit_config=RateLimiter(
            base_delay=(2.0, 5.0),  # 請求之間隨機延遲 2 到 5 秒
            max_delay=60.0,  # 速率限制錯誤時最大延遲 60 秒
            max_retries=5,  # 速率限制錯誤時最大重試次數 5 次
            rate_limit_codes=[429, 503] # 預設觸發回退和重試的 HTTP 狀態碼
        ),
        page_timeout=60000,  # 頁面載入或腳本執行總體時間限制 60 秒
        delay_before_return_html=2.5,  # 捕獲 HTML 前額外等待 2.5 秒，確保動態內容渲染

        # 併發與資源管理
        max_session_permit=5,  # 最大並發爬取會話數，根據系統資源和目標網站調整
        memory_threshold_percent=90.0  # 記憶體使用閾值，防止系統記憶體耗盡
    )

    async with AsyncWebCrawler(browser_config=browser_config, crawler_run_config=run_config) as crawler:
        for url in urls:
            result = await crawler.arun(url)

