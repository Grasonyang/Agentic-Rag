#!/usr/bin/env python3
"""
getSiteMap.py - Sitemap 發現和解析腳本

功能：
1. 從指定 URL 獲取 robots.txt
2. 解析所有 Sitemap 連結
3. 遞歸解析 Sitemap Index
4. 輸出所有發現的 Sitemap 到文件

使用方法：
    python scripts/getSiteMap.py --url https://example.com
    python scripts/getSiteMap.py --url         # 1. 從 robots.txt 發現初始 sitemap
        initial_sitemaps = await discovery.discover_sitemaps(args.url)tps://example.com --output sitemaps.txt
    make get-sitemap URL=https://example.com
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin, urlparse

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

from spider.crawlers.sitemap_parser import SitemapParser
from database.client import SupabaseClient
from database.models import SitemapModel, SitemapType, CrawlStatus


class SitemapDiscovery:
    """Sitemap 發現和管理類"""
    
    def __init__(self, output_file: str = "sitemaps.txt"):
        self.parser = SitemapParser()
        self.db_client = SupabaseClient()
        self.output_file = output_file
        self.discovered_sitemaps: Set[str] = set()
        self.sitemap_hierarchy: List[dict] = []
    
    async def discover_sitemaps(self, robots_url: str) -> List[str]:
        """從 robots.txt 發現 sitemap"""
        print(f"🤖 正在解析 robots.txt: {robots_url}")
        
        try:
            sitemaps = await self._parse_robots_txt(robots_url)
            
            if not sitemaps:
                print("⚠️ 未在 robots.txt 中找到 Sitemap 條目，嘗試常見路徑")
                # 嘗試常見的 sitemap 路徑
                base_url = robots_url.replace('/robots.txt', '')
                common_paths = ['/sitemap.xml', '/sitemap_index.xml', '/sitemapindex.xml']
                
                for path in common_paths:
                    potential_url = base_url + path
                    print(f"   � 檢查: {potential_url}")
                    # 這裡可以添加檢查邏輯
                
            return sitemaps
            
        except Exception as e:
            raise Exception(f"解析 robots.txt 失敗: {e}")
    
    async def _parse_robots_txt(self, robots_url: str) -> List[str]:
        """解析 robots.txt 文件提取 sitemap URL"""
        import aiohttp
        
        sitemaps = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # 解析每一行查找 Sitemap 條目
                        for line in text.split('\n'):
                            line = line.strip()
                            if line.lower().startswith('sitemap:'):
                                sitemap_url = line[8:].strip()  # 移除 'Sitemap:' 前綴
                                if sitemap_url:
                                    sitemaps.append(sitemap_url)
                                    print(f"   ✅ 發現 Sitemap: {sitemap_url}")
                    else:
                        raise Exception(f"HTTP {response.status}: 無法訪問 robots.txt")
                        
        except Exception as e:
            raise Exception(f"讀取 robots.txt 失敗: {e}")
        
        return sitemaps
    
    async def analyze_sitemap_hierarchy(self, sitemap_urls: List[str]) -> None:
        """分析 Sitemap 層次結構"""
        print(f"\n🔍 正在分析 Sitemap 層次結構...")
        
        for sitemap_url in sitemap_urls:
            try:
                # 檢查是否為 Sitemap Index
                sitemap_info = await self.parser.get_sitemap_info(sitemap_url)
                
                sitemap_data = {
                    'url': sitemap_url,
                    'type': sitemap_info.get('type', 'unknown'),
                    'url_count': sitemap_info.get('url_count', 0),
                    'last_modified': sitemap_info.get('lastmod'),
                    'sub_sitemaps': []
                }
                
                # 如果是 Sitemap Index，獲取子 Sitemap
                if sitemap_info.get('type') == 'sitemapindex':
                    print(f"📚 {sitemap_url} 是 Sitemap Index")
                    sub_sitemaps = await self.parser.get_sub_sitemaps(sitemap_url)
                    sitemap_data['sub_sitemaps'] = sub_sitemaps
                    
                    for sub_sitemap in sub_sitemaps:
                        self.discovered_sitemaps.add(sub_sitemap)
                        print(f"   └── 📄 {sub_sitemap}")
                else:
                    print(f"📄 {sitemap_url} 包含 {sitemap_data['url_count']} 個 URL")
                
                self.sitemap_hierarchy.append(sitemap_data)
                
            except Exception as e:
                print(f"⚠️ 分析 {sitemap_url} 時出錯: {e}")
                # 仍然添加到列表中，但標記為錯誤
                self.sitemap_hierarchy.append({
                    'url': sitemap_url,
                    'type': 'error',
                    'error': str(e),
                    'url_count': 0,
                    'sub_sitemaps': []
                })
    
    async def save_to_database(self) -> None:
        """保存 Sitemap 資訊到資料庫"""
        print(f"\n💾 正在保存 {len(self.sitemap_hierarchy)} 個 Sitemap 到資料庫...")
        
        try:
            supabase = self.db_client.get_client()
            
            for sitemap_data in self.sitemap_hierarchy:
                # 創建 Sitemap 模型
                sitemap_model = SitemapModel(
                    url=sitemap_data['url'],
                    sitemap_type=SitemapType.SITEMAPINDEX if sitemap_data['type'] == 'sitemapindex' else SitemapType.SITEMAP,
                    status=CrawlStatus.COMPLETED if sitemap_data['type'] != 'error' else CrawlStatus.ERROR,
                    urls_count=sitemap_data['url_count'],
                    metadata={
                        'discovered_from': 'robots.txt',
                        'hierarchy_level': 0,
                        'sub_sitemaps_count': len(sitemap_data.get('sub_sitemaps', [])),
                        'analysis_timestamp': asyncio.get_event_loop().time()
                    }
                )
                
                if sitemap_data['type'] == 'error':
                    sitemap_model.error_message = sitemap_data.get('error', 'Unknown error')
                
                # 保存到資料庫
                result = supabase.from_('sitemaps').upsert(
                    sitemap_model.to_dict(),
                    on_conflict='url'
                ).execute()
                
                if result.data:
                    print(f"✅ 已保存: {sitemap_data['url']}")
                else:
                    print(f"⚠️ 保存失敗: {sitemap_data['url']}")
        
        except Exception as e:
            print(f"❌ 資料庫保存失敗: {e}")
    
    def save_to_file(self) -> None:
        """保存 Sitemap 清單到文件"""
        print(f"\n📁 正在保存 Sitemap 清單到 {self.output_file}...")
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                # 寫入標題
                f.write("# Discovered Sitemaps\n")
                f.write(f"# Generated by getSiteMap.py\n")
                f.write(f"# Total: {len(self.discovered_sitemaps)} sitemaps\n\n")
                
                # 按層次結構寫入
                for sitemap_data in self.sitemap_hierarchy:
                    f.write(f"{sitemap_data['url']}\n")
                    
                    # 如果有子 Sitemap，縮排寫入
                    for sub_sitemap in sitemap_data.get('sub_sitemaps', []):
                        f.write(f"  {sub_sitemap}\n")
                
                # 如果有其他發現的 sitemap（容錯處理）
                written_urls = set()
                for sitemap_data in self.sitemap_hierarchy:
                    written_urls.add(sitemap_data['url'])
                    written_urls.update(sitemap_data.get('sub_sitemaps', []))
                
                remaining_sitemaps = self.discovered_sitemaps - written_urls
                if remaining_sitemaps:
                    f.write("\n# Additional discovered sitemaps\n")
                    for sitemap in sorted(remaining_sitemaps):
                        f.write(f"{sitemap}\n")
            
            print(f"✅ Sitemap 清單已保存到 {self.output_file}")
            print(f"📊 總計: {len(self.discovered_sitemaps)} 個 Sitemap")
            
        except Exception as e:
            print(f"❌ 文件保存失敗: {e}")
    
    def print_summary(self) -> None:
        """打印發現摘要"""
        print(f"\n📋 Sitemap 發現摘要:")
        print(f"=" * 50)
        
        total_urls = 0
        for sitemap_data in self.sitemap_hierarchy:
            sitemap_type = sitemap_data['type']
            url_count = sitemap_data['url_count']
            total_urls += url_count
            
            status_icon = "✅" if sitemap_type != 'error' else "❌"
            type_label = {
                'sitemapindex': 'Sitemap Index',
                'sitemap': 'Sitemap',
                'urlset': 'URL Set',
                'error': 'Error'
            }.get(sitemap_type, 'Unknown')
            
            print(f"{status_icon} {type_label}: {url_count} URLs")
            print(f"   📍 {sitemap_data['url']}")
            
            if sitemap_data.get('sub_sitemaps'):
                print(f"   📚 包含 {len(sitemap_data['sub_sitemaps'])} 個子 Sitemap")
        
        print(f"=" * 50)
        print(f"🎯 總計: {len(self.discovered_sitemaps)} 個 Sitemap")
        print(f"🔢 預估 URL 總數: {total_urls}")


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='Sitemap 發現和解析工具')
    parser.add_argument('--url', required=True, help='要解析的網站 URL')
    parser.add_argument('--output', default='sitemaps.txt', help='輸出文件名稱')
    parser.add_argument('--no-db', action='store_true', help='不保存到資料庫')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    print(f"🚀 開始 Sitemap 發現流程")
    print(f"🎯 目標網站: {args.url}")
    print(f"📁 輸出文件: {args.output}")
    
    discovery = SitemapDiscovery(args.output)
    
    try:
        # 1. 從 robots.txt 發現 Sitemap
        initial_sitemaps = await discovery.discover_sitemaps(args.url)
        
        # 2. 分析 Sitemap 層次結構
        await discovery.analyze_sitemap_hierarchy(initial_sitemaps)
        
        # 3. 保存到資料庫（如果啟用）
        if not args.no_db:
            await discovery.save_to_database()
        
        # 4. 保存到文件
        discovery.save_to_file()
        
        # 5. 打印摘要
        discovery.print_summary()
        
        print(f"\n🎉 Sitemap 發現完成！")
        print(f"📄 下一步: python scripts/getUrls.py --sitemap-list {args.output}")
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
