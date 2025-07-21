"""
內容處理器
基於 crawl4ai 的內建功能，優化 Agentic RAG 效果
"""

import logging
from typing import Optional, Dict, Any
from crawl4ai import AsyncWebCrawler, DefaultMarkdownGenerator, LLMExtractionStrategy
from crawl4ai.chunking_strategy import RegexChunking

logger = logging.getLogger(__name__)

class ContentProcessor:
    """
    內容處理器
    充分利用 crawl4ai 的內建功能進行內容處理和格式轉換
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.markdown_generator = DefaultMarkdownGenerator()
        self.chunking_strategy = RegexChunking()
    
    async def crawl_and_process(self, url: str, format_type: str = "markdown") -> Dict[str, Any]:
        """
        使用 crawl4ai 爬取並處理內容
        
        Args:
            url: 目標網址
            format_type: 輸出格式 (markdown, text, html)
            
        Returns:
            處理後的內容字典
        """
        try:
            async with AsyncWebCrawler(
                headless=True,
                verbose=False
            ) as crawler:
                
                # 根據格式類型設置爬取參數
                if format_type == "markdown":
                    result = await crawler.arun(
                        url=url,
                        word_count_threshold=10,
                        extraction_strategy=None,  # 使用預設的 markdown 提取
                        chunking_strategy=self.chunking_strategy,
                        bypass_cache=True
                    )
                    
                    return {
                        'url': url,
                        'title': result.metadata.get('title', ''),
                        'content': result.markdown,  # crawl4ai 內建的高品質 markdown
                        'content_type': 'markdown',
                        'word_count': len(result.markdown.split()) if result.markdown else 0,
                        'metadata': {
                            'original_format': 'html',
                            'processed_format': 'markdown',
                            'extraction_method': 'crawl4ai_builtin',
                            'page_metadata': result.metadata,
                            'links_found': len(result.links.get('internal', []) + result.links.get('external', [])),
                            'media_found': len(result.media.get('images', []) + result.media.get('videos', []))
                        }
                    }
                
                elif format_type == "text":
                    result = await crawler.arun(
                        url=url,
                        word_count_threshold=10,
                        only_text=True,  # 只提取純文本
                        bypass_cache=True
                    )
                    
                    return {
                        'url': url,
                        'title': result.metadata.get('title', ''),
                        'content': result.cleaned_html,  # 清理過的文本
                        'content_type': 'text',
                        'word_count': len(result.cleaned_html.split()) if result.cleaned_html else 0,
                        'metadata': {
                            'original_format': 'html',
                            'processed_format': 'text',
                            'extraction_method': 'crawl4ai_text_only'
                        }
                    }
                
                elif format_type == "structured":
                    # 使用 LLM 提取策略獲取結構化內容
                    extraction_strategy = LLMExtractionStrategy(
                        provider="ollama",  # 可以根據需要調整
                        api_token="",
                        instruction="Extract the main content and organize it in a structured format with clear headings and sections."
                    )
                    
                    result = await crawler.arun(
                        url=url,
                        extraction_strategy=extraction_strategy,
                        bypass_cache=True
                    )
                    
                    return {
                        'url': url,
                        'title': result.metadata.get('title', ''),
                        'content': result.extracted_content or result.markdown,
                        'content_type': 'structured',
                        'word_count': len((result.extracted_content or result.markdown).split()),
                        'metadata': {
                            'original_format': 'html',
                            'processed_format': 'structured',
                            'extraction_method': 'crawl4ai_llm_extraction'
                        }
                    }
                
                else:  # 原始 HTML
                    result = await crawler.arun(
                        url=url,
                        bypass_cache=True
                    )
                    
                    return {
                        'url': url,
                        'title': result.metadata.get('title', ''),
                        'content': result.html,
                        'content_type': 'html',
                        'word_count': len(result.cleaned_html.split()) if result.cleaned_html else 0,
                        'metadata': {
                            'original_format': 'html',
                            'processed_format': 'html',
                            'extraction_method': 'crawl4ai_raw'
                        }
                    }
                    
        except Exception as e:
            logger.error(f"爬取處理失敗 {url}: {e}")
            return {
                'url': url,
                'title': 'Error',
                'content': f"爬取失敗: {str(e)}",
                'content_type': 'error',
                'word_count': 0,
                'metadata': {'error': str(e)}
            }
    
    def get_optimal_format_for_rag(self) -> str:
        """
        返回最適合 RAG 的內容格式
        
        crawl4ai 的 markdown 輸出是最佳選擇，因為：
        1. 保留完整的文檔結構（標題、段落、列表、連結）
        2. 智能內容清理，移除廣告和無關內容
        3. 保留語義信息，便於向量嵌入
        4. 格式一致，便於後續處理
        """
        return "markdown"
    
    def analyze_content_quality(self, content: str) -> Dict[str, Any]:
        """
        分析內容品質
        """
        if not content:
            return {'quality_score': 0, 'issues': ['empty_content']}
        
        word_count = len(content.split())
        char_count = len(content)
        line_count = len(content.split('\n'))
        
        # 簡單的品質評分
        quality_score = min(100, (word_count / 50) * 100)  # 50個詞為滿分
        
        issues = []
        if word_count < 10:
            issues.append('too_short')
        if char_count / word_count > 20:  # 平均詞長過長
            issues.append('possible_noise')
        if line_count / word_count > 0.5:  # 行數太多
            issues.append('fragmented_content')
        
        return {
            'quality_score': quality_score,
            'word_count': word_count,
            'char_count': char_count,
            'line_count': line_count,
            'issues': issues
        }
