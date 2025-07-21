"""
簡化版網頁爬蟲 - 專注於核心爬蟲功能
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from crawl4ai import AsyncWebCrawler

logger = logging.getLogger(__name__)

@dataclass
class SimpleCrawlResult:
    """簡化的爬蟲結果"""
    url: str
    success: bool
    title: str = ""
    content: str = ""
    markdown: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    response_time: Optional[float] = None

class SimpleWebCrawler:
    """簡化版網頁爬蟲 - 去除資料庫依賴"""
    
    def __init__(self):
        """初始化爬蟲"""
        self.crawler = None
        
    async def crawl_url(self, url: str, **kwargs) -> SimpleCrawlResult:
        """
        爬取單個 URL
        
        Args:
            url: 要爬取的 URL
            **kwargs: 額外的爬蟲配置
            
        Returns:
            SimpleCrawlResult: 爬蟲結果
        """
        start_time = time.time()
        
        try:
            logger.info(f"🕷️ 開始爬取: {url}")
            
            # 初始化爬蟲（如果還沒有）
            if not self.crawler:
                self.crawler = AsyncWebCrawler(
                    headless=True,
                    verbose=False
                )
                await self.crawler.start()
            
            # 執行爬蟲
            result = await self.crawler.arun(
                url=url,
                word_count_threshold=10,
                **kwargs
            )
            
            response_time = time.time() - start_time
            
            if result.success:
                logger.info(f"✅ 爬取成功: {url} ({response_time:.2f}s)")
                return SimpleCrawlResult(
                    url=url,
                    success=True,
                    title=result.metadata.get('title', '') if result.metadata else '',
                    content=result.cleaned_html or '',
                    markdown=result.markdown or '',
                    metadata=result.metadata or {},
                    response_time=response_time
                )
            else:
                logger.warning(f"❌ 爬取失敗: {url} - {result.error_message}")
                return SimpleCrawlResult(
                    url=url,
                    success=False,
                    error=result.error_message,
                    response_time=response_time
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"❌ 爬取異常: {url} - {error_msg}")
            return SimpleCrawlResult(
                url=url,
                success=False,
                error=error_msg,
                response_time=response_time
            )
    
    async def crawl_batch(self, urls: List[str], max_concurrent: int = 5) -> List[SimpleCrawlResult]:
        """
        批量爬取 URLs
        
        Args:
            urls: URL 列表
            max_concurrent: 最大併發數
            
        Returns:
            List[SimpleCrawlResult]: 爬蟲結果列表
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def crawl_with_semaphore(url):
            async with semaphore:
                return await self.crawl_url(url)
        
        logger.info(f"🚀 開始批量爬取 {len(urls)} 個 URLs (併發數: {max_concurrent})")
        start_time = time.time()
        
        # 執行批量爬蟲
        tasks = [crawl_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 處理異常結果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(SimpleCrawlResult(
                    url=urls[i],
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        total_time = time.time() - start_time
        success_count = sum(1 for r in processed_results if r.success)
        
        logger.info(f"📊 批量爬取完成: {success_count}/{len(urls)} 成功 ({total_time:.2f}s)")
        
        return processed_results
    
    async def close(self):
        """關閉爬蟲"""
        if self.crawler:
            await self.crawler.close()
            self.crawler = None
            logger.info("🔒 爬蟲已關閉")
    
    async def __aenter__(self):
        """異步上下文管理器進入"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出"""
        await self.close()
