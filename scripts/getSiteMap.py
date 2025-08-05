#!/usr/bin/env python3
"""
getSiteMap.py - Sitemap 發現和解析腳本

功能：
1. 從指定 URL 獲取 robots.txt
2. 解析所有 Sitemap 連結
3. 遞歸解析 Sitemap Index
4. 輸出所有發現的 Sitemap 到文件
5. 記錄詳細日誌到 logs 目錄

使用方法：
    python scripts/getSiteMap.py --url https://example.com
    python scripts/getSiteMap.py --url https://example.com --output sitemaps.txt
    make get-sitemap URL=https://example.com
"""

import argparse
import asyncio
import aiohttp
import sys
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin, urlparse

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

from scripts.utils import ScriptRunner


class SitemapDiscovery(ScriptRunner):
    """Sitemap 發現和管理類"""
    
    def __init__(self):
        super().__init__("sitemap_discovery")
        self.discovered_sitemaps: Set[str] = set()
    
    def setup_arguments(self, parser: argparse.ArgumentParser):
        """設置命令行參數"""
        parser.add_argument('--url', required=True, help='目標網站 URL')
        parser.add_argument('--output', default='sitemaps.txt', help='輸出文件名')
        parser.add_argument('--save-db', action='store_true', help='將結果保存到數據庫')
    
    async def run_script(self, args: argparse.Namespace) -> bool:
        """執行腳本主邏輯"""
        try:
            self.log_info(f"開始發現 {args.url} 的 Sitemap")
            
            # 發現 sitemaps
            robots_url = urljoin(args.url, '/robots.txt')
            sitemaps = await self.discover_sitemaps(robots_url)
            
            if not sitemaps:
                self.log_warning("未發現任何 Sitemap")
                return False
            
            self.stats.set_custom_stat("發現的 Sitemap 數量", len(sitemaps))
            
            # 保存到文件
            output_path = self.save_sitemaps_to_file(sitemaps, args.output)
            self.log_success(f"Sitemap 列表已保存到: {output_path}")
            
            # 可選：保存到數據庫
            if args.save_db:
                await self.save_sitemaps_to_db(sitemaps, args.url)
                self.log_success("Sitemap 列表已保存到數據庫")
            
            return True
            
        except Exception as e:
            self.log_error("Sitemap 發現失敗", e)
            return False
    
    async def discover_sitemaps(self, robots_url: str) -> List[str]:
        """從 robots.txt 發現 sitemap"""
        self.log_info(f"正在解析 robots.txt: {robots_url}")
        
        try:
            sitemaps = await self._parse_robots_txt(robots_url)
            
            if not sitemaps:
                self.log_warning("未在 robots.txt 中找到 Sitemap 條目，嘗試常見路徑")
                # 嘗試常見的 sitemap 路徑
                base_url = robots_url.replace('/robots.txt', '')
                common_paths = ['/sitemap.xml', '/sitemap_index.xml', '/sitemapindex.xml']
                
                for path in common_paths:
                    potential_url = base_url + path
                    self.log_info(f"檢查: {potential_url}")
                    if await self._check_sitemap_exists(potential_url):
                        sitemaps.append(potential_url)
                        self.log_success(f"發現 Sitemap: {potential_url}")
                
            return sitemaps
            
        except Exception as e:
            self.log_error(f"解析 robots.txt 失敗", e)
            raise
    
    async def _parse_robots_txt(self, robots_url: str) -> List[str]:
        """解析 robots.txt 文件提取 sitemap URL"""
        sitemaps = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        for line in text.split('\n'):
                            line = line.strip()
                            if line.lower().startswith('sitemap:'):
                                sitemap_url = line.split(':', 1)[1].strip()
                                if sitemap_url:
                                    sitemaps.append(sitemap_url)
                                    self.discovered_sitemaps.add(sitemap_url)
                                    self.log_success(f"發現 Sitemap: {sitemap_url}")
                    else:
                        self.log_warning(f"無法訪問 robots.txt: HTTP {response.status}")
                        
        except Exception as e:
            self.log_error(f"讀取 robots.txt 失敗", e)
            raise
        
        return sitemaps
    
    async def _check_sitemap_exists(self, url: str) -> bool:
        """檢查 sitemap URL 是否存在"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url) as response:
                    return response.status == 200
        except:
            return False
    
    def save_sitemaps_to_file(self, sitemaps: List[str], output_filename: str) -> str:
        """保存 sitemap 列表到文件"""
        content = f"# Sitemap 發現結果\n"
        content += f"# 生成時間: {self.stats.start_time.isoformat()}\n"
        content += f"# 總數量: {len(sitemaps)}\n\n"
        
        for i, sitemap_url in enumerate(sitemaps, 1):
            content += f"{i}. {sitemap_url}\n"
        
        return self.file_manager.save_text_file(content, output_filename)
    
    async def save_sitemaps_to_db(self, sitemaps: List[str], base_url: str):
        """保存 sitemap 列表到資料庫"""
        try:
            from database.client import SupabaseClient
            from database.models import SitemapModel, SitemapType, CrawlStatus
            
            supabase_client = SupabaseClient()
            supabase = supabase_client.get_client()
            
            saved_count = 0
            for sitemap_url in sitemaps:
                try:
                    sitemap_model = SitemapModel(
                        url=sitemap_url,
                        sitemap_type=SitemapType.SITEMAP,
                        status=CrawlStatus.PENDING,
                        metadata={
                            'discovered_from': base_url,
                            'discovery_timestamp': self.stats.start_time.isoformat()
                        }
                    )
                    
                    result = supabase.from_('sitemaps').upsert(
                        sitemap_model.to_dict(), on_conflict='url'
                    ).execute()
                    
                    if result.data:
                        saved_count += 1
                        
                except Exception as e:
                    self.log_warning(f"保存 sitemap {sitemap_url} 失敗: {e}")
            
            self.stats.set_custom_stat("保存到資料庫的數量", saved_count)
            
        except Exception as e:
            self.log_error("保存到資料庫失敗", e)
            raise


if __name__ == "__main__":
    from scripts.utils import run_script
    run_script(SitemapDiscovery)
