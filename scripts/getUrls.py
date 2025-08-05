#!/usr/bin/env python3
"""
getUrls.py - URL 提取和排序腳本

功能：
1. 讀取 Sitemap 清單文件
2. 依序解析每個 Sitemap
3. 提取所有 URL 並保持原始順序
4. 過濾重複和無效 URL
5. 輸出有序的 URL 清單

使用方法：
    python scripts/getUrls.py --sitemap-list sitemaps.txt
    python scripts/getUrls.py --sitemap-list sitemaps.txt --output urls.txt --max-urls 1000
    make get-urls SITEMAP_LIST=sitemaps.txt
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Set, Dict, Optional
from urllib.parse import urlparse

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

from scripts.utils import ScriptRunner


class UrlExtractor(ScriptRunner):
    """URL 提取和管理類"""
    
    def __init__(self):
        super().__init__("url_extractor")
        self.extracted_urls: List[Dict] = []
        self.seen_urls: Set[str] = set()
    
    def setup_arguments(self, parser: argparse.ArgumentParser):
        """設置命令行參數"""
        parser.add_argument('--sitemap-list', required=True, help='Sitemap 清單文件')
        parser.add_argument('--output', default='urls.txt', help='輸出文件名')
        parser.add_argument('--max-urls', type=int, default=None, help='最大 URL 數量')
        parser.add_argument('--filter-extensions', nargs='*', 
                          default=['.pdf', '.jpg', '.png', '.gif', '.zip'], 
                          help='要過濾的文件擴展名')
    
    async def run_script(self, args: argparse.Namespace) -> bool:
        """執行腳本主邏輯"""
        try:
            self.log_info(f"開始從 {args.sitemap_list} 提取 URL")
            
            # 讀取 sitemap 列表
            sitemaps = self.read_sitemap_list(args.sitemap_list)
            
            if not sitemaps:
                self.log_warning("Sitemap 列表為空")
                return False
            
            self.stats.set_custom_stat("Sitemap 數量", len(sitemaps))
            
            # 提取 URLs
            await self.extract_urls_from_sitemaps(sitemaps, args.filter_extensions, args.max_urls)
            
            if not self.extracted_urls:
                self.log_warning("未提取到任何 URL")
                return False
            
            self.stats.set_custom_stat("提取的 URL 數量", len(self.extracted_urls))
            
            # 保存到文件
            output_path = self.save_urls_to_file(args.output)
            self.log_success(f"URL 列表已保存到: {output_path}")
            
            return True
            
        except Exception as e:
            self.log_error("URL 提取失敗", e)
            return False
    
    def read_sitemap_list(self, sitemap_file: str) -> List[str]:
        """讀取 sitemap 列表文件"""
        self.log_info(f"正在讀取 Sitemap 列表: {sitemap_file}")
        
        try:
            sitemaps = []
            with open(sitemap_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # 跳過註釋和空行
                    if not line or line.startswith('#'):
                        continue
                    
                    # 提取 URL（支持編號格式）
                    if line.startswith(('http://', 'https://')):
                        url = line.split()[0]  # 取第一個部分
                        sitemaps.append(url)
                    elif '. http' in line:  # 編號格式 "1. https://..."
                        parts = line.split('. ', 1)
                        if len(parts) > 1 and parts[1].startswith(('http://', 'https://')):
                            url = parts[1].split()[0]
                            sitemaps.append(url)
            
            self.log_success(f"讀取到 {len(sitemaps)} 個 Sitemap")
            return sitemaps
            
        except Exception as e:
            self.log_error(f"讀取 Sitemap 列表失敗", e)
            raise
    
    async def extract_urls_from_sitemaps(self, sitemaps: List[str], 
                                       filter_extensions: List[str], 
                                       max_urls: Optional[int]):
        """從 sitemaps 提取 URLs"""
        self.log_info("開始提取 URLs")
        
        try:
            from spider.crawlers.sitemap_parser import SitemapParser
            parser = SitemapParser()
            
            for i, sitemap_url in enumerate(sitemaps, 1):
                if max_urls and len(self.extracted_urls) >= max_urls:
                    self.log_info(f"已達到最大 URL 數量限制: {max_urls}")
                    break
                
                self.log_progress(f"處理 Sitemap: {sitemap_url}", i, len(sitemaps))
                
                try:
                    # 解析 sitemap
                    urls = await parser.get_urls_from_sitemap(sitemap_url)
                    
                    for url_data in urls:
                        if max_urls and len(self.extracted_urls) >= max_urls:
                            break
                        
                        url = url_data.get('url', url_data) if isinstance(url_data, dict) else url_data
                        
                        # 過濾重複 URL
                        if url in self.seen_urls:
                            continue
                        
                        # 過濾文件擴展名
                        if self._should_filter_url(url, filter_extensions):
                            continue
                        
                        # 添加到結果
                        self.extracted_urls.append({
                            'url': url,
                            'sitemap_source': sitemap_url,
                            'priority': url_data.get('priority') if isinstance(url_data, dict) else None,
                            'lastmod': url_data.get('lastmod') if isinstance(url_data, dict) else None,
                            'changefreq': url_data.get('changefreq') if isinstance(url_data, dict) else None
                        })
                        self.seen_urls.add(url)
                    
                    self.log_success(f"從 {sitemap_url} 提取了 {len(urls)} 個 URL")
                    
                except Exception as e:
                    self.log_warning(f"處理 Sitemap {sitemap_url} 失敗: {e}")
                    continue
            
            self.log_success(f"總共提取了 {len(self.extracted_urls)} 個 URL")
            
        except Exception as e:
            self.log_error("提取 URLs 失敗", e)
            raise
    
    def _should_filter_url(self, url: str, filter_extensions: List[str]) -> bool:
        """檢查是否應該過濾該 URL"""
        if not filter_extensions:
            return False
        
        for ext in filter_extensions:
            if url.lower().endswith(ext.lower()):
                return True
        
        return False
    
    def save_urls_to_file(self, output_filename: str) -> str:
        """保存 URL 列表到文件"""
        content = f"# URL 提取結果\n"
        content += f"# 生成時間: {self.stats.start_time.isoformat()}\n"
        content += f"# 總數量: {len(self.extracted_urls)}\n\n"
        
        for url_data in self.extracted_urls:
            url = url_data['url']
            
            # 添加註釋信息
            comments = []
            if url_data.get('priority'):
                comments.append(f"priority={url_data['priority']}")
            if url_data.get('changefreq'):
                comments.append(f"freq={url_data['changefreq']}")
            if url_data.get('lastmod'):
                comments.append(f"modified={url_data['lastmod']}")
            
            if comments:
                content += f"{url} # {', '.join(comments)}\n"
            else:
                content += f"{url}\n"
        
        return self.file_manager.save_text_file(content, output_filename)


if __name__ == "__main__":
    from scripts.utils import run_script
    run_script(UrlExtractor)
