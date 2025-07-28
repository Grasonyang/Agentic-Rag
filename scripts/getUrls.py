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
import os
from pathlib import Path
from typing import List, Set, Dict, Optional
from urllib.parse import urlparse, urljoin
from datetime import datetime

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

from spider.crawlers.sitemap_parser import SitemapParser
from database.client import SupabaseClient
from database.models import DiscoveredURLModel, URLType, CrawlStatus


class URLExtractor:
    """URL 提取和管理類"""
    
    def __init__(self, output_file: str = "urls.txt", max_urls: int = None):
        self.parser = SitemapParser()
        self.db_client = SupabaseClient()
        self.output_file = output_file
        self.max_urls = max_urls
        self.discovered_urls: List[Dict] = []
        self.url_set: Set[str] = set()  # 用於去重
        self.stats = {
            'total_sitemaps': 0,
            'processed_sitemaps': 0,
            'total_urls': 0,
            'unique_urls': 0,
            'skipped_urls': 0,
            'errors': 0
        }
    
    def load_sitemap_list(self, sitemap_file: str) -> List[str]:
        """從文件載入 Sitemap 清單"""
        print(f"📖 正在讀取 Sitemap 清單: {sitemap_file}")
        
        if not os.path.exists(sitemap_file):
            raise FileNotFoundError(f"Sitemap 清單文件不存在: {sitemap_file}")
        
        sitemaps = []
        try:
            with open(sitemap_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # 跳過註釋和空行
                    if line.startswith('#') or not line:
                        continue
                    
                    # 處理縮排的子 sitemap（保持層次結構）
                    if line.startswith('  '):
                        # 子 sitemap，移除縮排
                        clean_url = line.strip()
                        if self._is_valid_url(clean_url):
                            sitemaps.append(clean_url)
                    else:
                        # 主 sitemap
                        if self._is_valid_url(line):
                            sitemaps.append(line)
                        else:
                            print(f"⚠️ 第 {line_num} 行 URL 格式不正確: {line}")
            
            self.stats['total_sitemaps'] = len(sitemaps)
            print(f"✅ 載入 {len(sitemaps)} 個 Sitemap")
            return sitemaps
            
        except Exception as e:
            raise Exception(f"讀取 Sitemap 清單失敗: {e}")
    
    def _is_valid_url(self, url: str) -> bool:
        """驗證 URL 格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    async def extract_urls_from_sitemap(self, sitemap_url: str) -> List[Dict]:
        """從單個 Sitemap 提取 URL"""
        print(f"🔍 正在解析 Sitemap: {sitemap_url}")
        
        try:
            # 使用正確的方法來解析 sitemap
            urls_data = await self.parser.parse_sitemaps([sitemap_url])
            
            extracted_urls = []
            for entry in urls_data:
                url = entry.url if hasattr(entry, 'url') else str(entry)
                
                # 基本驗證
                if not self._is_valid_url(url):
                    self.stats['skipped_urls'] += 1
                    continue
                
                # 去重檢查
                if url in self.url_set:
                    self.stats['skipped_urls'] += 1
                    continue
                
                self.url_set.add(url)
                
                # 構建 URL 資訊
                url_data = {
                    'url': url,
                    'source_sitemap': sitemap_url,
                    'priority': getattr(entry, 'priority', None),
                    'changefreq': getattr(entry, 'changefreq', None),
                    'lastmod': getattr(entry, 'lastmod', None),
                    'discovered_at': datetime.now().isoformat(),
                    'url_type': self._classify_url_type(url)
                }
                
                extracted_urls.append(url_data)
                self.stats['total_urls'] += 1
                
                # 檢查是否達到最大 URL 限制
                if self.max_urls and self.stats['total_urls'] >= self.max_urls:
                    print(f"⚠️ 已達到最大 URL 限制: {self.max_urls}")
                    break
            
            print(f"✅ 從 {sitemap_url} 提取 {len(extracted_urls)} 個 URL")
            return extracted_urls
            
        except Exception as e:
            print(f"❌ 解析 {sitemap_url} 失敗: {e}")
            self.stats['errors'] += 1
            return []
    
    def _classify_url_type(self, url: str) -> str:
        """根據 URL 分類內容類型"""
        # 基本的 URL 分類邏輯
        url_lower = url.lower()
        
        # 常見的非內容頁面
        if any(pattern in url_lower for pattern in [
            '/category/', '/tag/', '/archive/', '/page/',
            '/search/', '/feed/', '/rss/', '/sitemap'
        ]):
            return 'other'
        
        # 媒體文件
        if any(url_lower.endswith(ext) for ext in [
            '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.zip'
        ]):
            return 'media'
        
        # 默認為內容頁面
        return 'content'
    
    async def process_all_sitemaps(self, sitemap_urls: List[str]) -> None:
        """處理所有 Sitemap"""
        print(f"\n🚀 開始處理 {len(sitemap_urls)} 個 Sitemap")
        
        for i, sitemap_url in enumerate(sitemap_urls, 1):
            print(f"\n[{i}/{len(sitemap_urls)}] 處理中...")
            
            urls = await self.extract_urls_from_sitemap(sitemap_url)
            self.discovered_urls.extend(urls)
            self.stats['processed_sitemaps'] += 1
            
            # 如果達到最大 URL 限制，停止處理
            if self.max_urls and self.stats['total_urls'] >= self.max_urls:
                break
            
            # 添加小延遲避免過於頻繁的請求
            await asyncio.sleep(0.5)
        
        self.stats['unique_urls'] = len(self.discovered_urls)
        print(f"\n✅ 處理完成！總計提取 {self.stats['unique_urls']} 個唯一 URL")
    
    async def save_to_database(self) -> None:
        """保存 URL 到資料庫"""
        print(f"\n💾 正在保存 {len(self.discovered_urls)} 個 URL 到資料庫...")
        
        try:
            supabase = self.db_client.get_client()
            batch_size = 100
            saved_count = 0
            
            for i in range(0, len(self.discovered_urls), batch_size):
                batch = self.discovered_urls[i:i + batch_size]
                
                # 準備批量插入數據
                batch_data = []
                for url_data in batch:
                    # 獲取對應的 sitemap_id（需要查詢資料庫）
                    sitemap_result = supabase.from_('sitemaps')\
                        .select('id')\
                        .eq('url', url_data['source_sitemap'])\
                        .limit(1)\
                        .execute()
                    
                    sitemap_id = None
                    if sitemap_result.data:
                        sitemap_id = sitemap_result.data[0]['id']
                    
                    if sitemap_id:
                        url_model = DiscoveredURLModel(
                            url=url_data['url'],
                            source_sitemap_id=sitemap_id,
                            url_type=URLType.CONTENT if url_data['url_type'] == 'content' else URLType.OTHER,
                            priority=url_data['priority'],
                            changefreq=url_data['changefreq'],
                            lastmod=datetime.fromisoformat(url_data['lastmod']) if url_data['lastmod'] else None,
                            crawl_status=CrawlStatus.PENDING,
                            metadata={
                                'discovered_from': 'sitemap',
                                'discovered_at': url_data['discovered_at'],
                                'url_type_detail': url_data['url_type']
                            }
                        )
                        
                        batch_data.append(url_model.to_dict())
                
                # 批量插入
                if batch_data:
                    result = supabase.from_('discovered_urls')\
                        .upsert(batch_data, on_conflict='url')\
                        .execute()
                    
                    if result.data:
                        saved_count += len(result.data)
                        print(f"✅ 已保存批次 {i//batch_size + 1}: {len(result.data)} 個 URL")
                
            print(f"✅ 資料庫保存完成！總計: {saved_count} 個 URL")
            
        except Exception as e:
            print(f"❌ 資料庫保存失敗: {e}")
    
    def save_to_file(self) -> None:
        """保存 URL 清單到文件"""
        print(f"\n📁 正在保存 URL 清單到 {self.output_file}...")
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                # 寫入標題和統計
                f.write("# Discovered URLs\n")
                f.write(f"# Generated by getUrls.py\n")
                f.write(f"# Total unique URLs: {len(self.discovered_urls)}\n")
                f.write(f"# Processed sitemaps: {self.stats['processed_sitemaps']}\n")
                f.write(f"# Generated at: {datetime.now().isoformat()}\n\n")
                
                # 按來源 sitemap 分組寫入
                current_sitemap = None
                for url_data in self.discovered_urls:
                    if url_data['source_sitemap'] != current_sitemap:
                        current_sitemap = url_data['source_sitemap']
                        f.write(f"\n# From: {current_sitemap}\n")
                    
                    # 寫入 URL 和額外資訊（註釋形式）
                    f.write(f"{url_data['url']}")
                    
                    # 添加元數據作為註釋
                    metadata = []
                    if url_data.get('priority'):
                        metadata.append(f"priority={url_data['priority']}")
                    if url_data.get('changefreq'):
                        metadata.append(f"freq={url_data['changefreq']}")
                    if url_data.get('lastmod'):
                        lastmod_str = url_data['lastmod']
                        if hasattr(lastmod_str, 'isoformat'):  # datetime 物件
                            lastmod_str = lastmod_str.isoformat()
                        metadata.append(f"modified={lastmod_str[:10]}")  # 只顯示日期
                    
                    if metadata:
                        f.write(f"  # {', '.join(metadata)}")
                    
                    f.write("\n")
            
            print(f"✅ URL 清單已保存到 {self.output_file}")
            
        except Exception as e:
            print(f"❌ 文件保存失敗: {e}")
    
    def print_summary(self) -> None:
        """打印提取摘要"""
        print(f"\n📋 URL 提取摘要:")
        print(f"=" * 50)
        print(f"📊 處理統計:")
        print(f"   • 總 Sitemap 數: {self.stats['total_sitemaps']}")
        print(f"   • 已處理 Sitemap: {self.stats['processed_sitemaps']}")
        print(f"   • 發現 URL 總數: {self.stats['total_urls']}")
        print(f"   • 唯一 URL 數: {self.stats['unique_urls']}")
        print(f"   • 跳過重複/無效: {self.stats['skipped_urls']}")
        print(f"   • 錯誤數: {self.stats['errors']}")
        
        # URL 類型統計
        type_counts = {}
        for url_data in self.discovered_urls:
            url_type = url_data['url_type']
            type_counts[url_type] = type_counts.get(url_type, 0) + 1
        
        if type_counts:
            print(f"\n🏷️ URL 類型分布:")
            for url_type, count in sorted(type_counts.items()):
                percentage = (count / len(self.discovered_urls)) * 100
                print(f"   • {url_type}: {count} ({percentage:.1f}%)")
        
        print(f"=" * 50)
        print(f"🎯 準備爬取 {self.stats['unique_urls']} 個 URL")


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='URL 提取和排序工具')
    parser.add_argument('--sitemap-list', required=True, help='Sitemap 清單文件')
    parser.add_argument('--output', default='urls.txt', help='輸出文件名稱')
    parser.add_argument('--max-urls', type=int, help='最大 URL 數量限制')
    parser.add_argument('--no-db', action='store_true', help='不保存到資料庫')
    parser.add_argument('--content-only', action='store_true', help='只提取內容頁面 URL')
    
    args = parser.parse_args()
    
    print(f"🚀 開始 URL 提取流程")
    print(f"📖 Sitemap 清單: {args.sitemap_list}")
    print(f"📁 輸出文件: {args.output}")
    if args.max_urls:
        print(f"🔢 URL 限制: {args.max_urls}")
    
    extractor = URLExtractor(args.output, args.max_urls)
    
    try:
        # 1. 載入 Sitemap 清單
        sitemap_urls = extractor.load_sitemap_list(args.sitemap_list)
        
        # 2. 處理所有 Sitemap
        await extractor.process_all_sitemaps(sitemap_urls)
        
        # 3. 過濾內容類型（如果指定）
        if args.content_only:
            original_count = len(extractor.discovered_urls)
            extractor.discovered_urls = [
                url_data for url_data in extractor.discovered_urls
                if url_data['url_type'] == 'content'
            ]
            filtered_count = len(extractor.discovered_urls)
            print(f"🔍 內容過濾: {original_count} -> {filtered_count} URLs")
        
        # 4. 保存到資料庫（如果啟用）
        if not args.no_db and extractor.discovered_urls:
            await extractor.save_to_database()
        
        # 5. 保存到文件
        if extractor.discovered_urls:
            extractor.save_to_file()
        
        # 6. 打印摘要
        extractor.print_summary()
        
        if extractor.discovered_urls:
            print(f"\n🎉 URL 提取完成！")
            print(f"📄 下一步: python scripts/getChunking.py --url-list {args.output}")
        else:
            print(f"\n⚠️ 未提取到任何 URL")
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
