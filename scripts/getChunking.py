#!/usr/bin/env python3
"""
getChunking.py - 網頁內容爬取和分塊腳本

功能：
1. 讀取 URL 清單文件
2. 依序爬取每個網頁內容
3. 對內容進行智能分塊處理
4. 保存文章和分塊資訊
5. 生成待嵌入的分塊清單

使用方法：
    python scripts/getChunking.py --url-list urls.txt
    python scripts/getChunking.py --url-list urls.txt --chunker sliding_window --chunk-size 200
    make get-chunking URL_LIST=urls.txt
"""

import argparse
import asyncio
import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import hashlib
import re

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

# 導入配置管理和增強版工具
from config_manager import get_config
from spider.utils.enhanced_logger import SpiderLogger
from spider.utils.connection_manager import EnhancedConnectionManager
from spider.utils.database_manager import EnhancedDatabaseManager
from spider.crawlers.web_crawler import WebCrawler
from spider.chunking.chunker_factory import ChunkerFactory
from database.models import ArticleModel, ChunkModel


class ContentProcessor:
    """內容爬取和分塊處理類"""
    
    def __init__(self, output_file: str = "chunks.txt", chunker_type: str = "sliding_window", 
                 chunker_params: Dict = None, max_workers: int = 3):
        
        # 初始化配置
        self.config = get_config()
        self.output_file = output_file
        self.chunker_type = chunker_type
        self.chunker_params = chunker_params or {}
        self.max_workers = max_workers
        
        # 初始化增強版日誌系統
        self.logger = SpiderLogger("content_processor")
        
        # 初始化增強版爬蟲
        try:
            from spider.utils.retry_manager import RetryConfig
            from spider.utils.rate_limiter import RateLimitConfig
            
            retry_config = RetryConfig(max_retries=3, base_delay=1.0, max_delay=30.0)
            rate_config = RateLimitConfig(requests_per_second=0.5, adaptive=True)
            
            self.crawler = WebCrawler(retry_config=retry_config, rate_config=rate_config)
            self.logger.info("網頁爬蟲初始化成功")
        except Exception as e:
            self.logger.error(f"爬蟲初始化失敗: {e}")
            raise
        
        # 初始化增強版資料庫管理器
        try:
            db_config = self.config.get_database_config()
            self.db_manager = EnhancedDatabaseManager(db_config)
            self.logger.info("資料庫管理器初始化成功")
        except Exception as e:
            self.logger.error(f"資料庫管理器初始化失敗: {e}")
            raise
        
        # 初始化分塊器
        try:
            self.chunker = ChunkerFactory.create_chunker(chunker_type, self.chunker_params)
            self.logger.info(f"分塊器 {chunker_type} 初始化成功")
        except Exception as e:
            self.logger.warning(f"分塊器初始化失敗，使用預設 sliding_window: {e}")
            print(f"⚠️ 分塊器初始化失敗，使用預設 sliding_window: {e}")
            self.chunker = ChunkerFactory.create_chunker("sliding_window", {})
        
        # 處理統計
        self.stats = {
            'total_urls': 0,
            'processed_urls': 0,
            'successful_crawls': 0,
            'failed_crawls': 0,
            'total_articles': 0,
            'total_chunks': 0,
            'processing_time': 0,
            'errors': []
        }
        
        # 存儲處理數據
        self.articles_data = []
        self.chunks_data = []
    
    def parse_urls_file(self, urls_file: str) -> List[Dict]:
        """解析 URL 清單文件"""
        print(f"📖 正在解析 URL 清單: {urls_file}")
        
        if not os.path.exists(urls_file):
            raise FileNotFoundError(f"URL 清單文件不存在: {urls_file}")
        
        urls = []
        current_sitemap = None
        
        try:
            with open(urls_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析 sitemap 分組
                    if line.startswith('## Sitemap:'):
                        current_sitemap = line.replace('## Sitemap:', '').strip()
                        continue
                    
                    # 解析 URL 行 - 支持簡化格式
                    url_info = {}
                    
                    if line.startswith('- '):
                        # 完整格式：- url metadata
                        url_match = re.search(r'- (https?://[^\s]+)', line)
                        if url_match:
                            url_info['url'] = url_match.group(1)
                        else:
                            continue
                    elif line.startswith('https://') or line.startswith('http://'):
                        # 簡化格式：直接是 URL
                        url_parts = line.split()
                        if url_parts:
                            url_info['url'] = url_parts[0]
                            # 解析註釋中的 metadata
                            if '#' in line:
                                comment_part = line.split('#', 1)[1].strip()
                                # 解析 priority, freq, modified
                                priority_match = re.search(r'priority=([\d.]+)', comment_part)
                                if priority_match:
                                    url_info['priority'] = float(priority_match.group(1))
                                
                                freq_match = re.search(r'freq=(\w+)', comment_part)
                                if freq_match:
                                    url_info['changefreq'] = freq_match.group(1)
                                
                                modified_match = re.search(r'modified=([\d-]+)', comment_part)
                                if modified_match:
                                    url_info['lastmod'] = modified_match.group(1)
                        else:
                            continue
                    else:
                        continue
                    
                    # 設置 sitemap 來源
                    url_info['sitemap_source'] = current_sitemap
                    url_info['line_number'] = line_num
                    
                    urls.append(url_info)
            
            self.stats['total_urls'] = len(urls)
            print(f"✅ 解析完成，找到 {len(urls)} 個 URL")
            return urls
            
        except Exception as e:
            raise Exception(f"解析 URL 清單失敗: {e}")
    
    async def process_urls_batch(self, urls: List[Dict], batch_size: int = 5) -> None:
        """批量處理 URL 爬取和分塊"""
        print(f"\n🚀 開始批量處理 URL (批次大小: {batch_size})")
        
        start_time = datetime.now()
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(urls) + batch_size - 1) // batch_size
            
            print(f"\n📦 處理批次 {batch_num}/{total_batches} ({len(batch)} 個 URL)")
            
            # 並發爬取批次 URL
            crawl_tasks = []
            for url_info in batch:
                task = self._crawl_and_process_single_url(url_info)
                crawl_tasks.append(task)
            
            # 執行批次爬取
            batch_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
            
            # 處理批次結果
            for url_info, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    error_msg = f"批次處理失敗: {str(result)}"
                    print(f"   ❌ {url_info['url'][:50]}... - {error_msg}")
                    self.stats['failed_crawls'] += 1
                    self.stats['errors'].append({
                        'url': url_info['url'],
                        'error': error_msg
                    })
                else:
                    self.stats['successful_crawls'] += 1
            
            self.stats['processed_urls'] += len(batch)
            
            # 顯示進度
            progress = (self.stats['processed_urls'] / self.stats['total_urls']) * 100
            print(f"   ✅ 批次完成，總進度: {progress:.1f}%")
        
        end_time = datetime.now()
        self.stats['processing_time'] = (end_time - start_time).total_seconds()
        
        print(f"\n✅ URL 處理完成！")
        print(f"   ⏱️ 耗時: {self.stats['processing_time']:.2f} 秒")
        print(f"   🎯 成功: {self.stats['successful_crawls']} 個")
        print(f"   ❌ 失敗: {self.stats['failed_crawls']} 個")
    
    async def _crawl_and_process_single_url(self, url_info: Dict) -> Dict:
        """爬取和處理單個 URL"""
        url = url_info['url']
        
        try:
            # 爬取網頁內容
            print(f"   🔍 爬取: {url[:60]}...")
            crawl_result = await self.crawler.crawl_url(url)
            
            if not crawl_result or not crawl_result.success or not crawl_result.content:
                raise Exception("爬取結果為空或無內容")
            
            # 準備文章數據
            article_data = {
                'url': url,
                'title': crawl_result.title or '',
                'content': crawl_result.content,
                'metadata': {
                    'sitemap_source': url_info.get('sitemap_source'),
                    'priority': url_info.get('priority'),
                    'lastmod': url_info.get('lastmod'),
                    'changefreq': url_info.get('changefreq'),
                    'crawled_at': datetime.now().isoformat(),
                    'content_length': len(crawl_result.content),
                    'chunker_type': self.chunker_type,
                    'chunker_params': self.chunker_params
                }
            }
            
            # 生成文章 ID
            article_id = self._generate_article_id(url)
            article_data['id'] = article_id
            
            # 進行內容分塊
            print(f"   ✂️ 分塊: {article_data['title'][:40]}...")
            chunks = await self._chunk_content(article_data)
            
            # 保存到資料庫
            await self._save_article_and_chunks(article_data, chunks)
            
            # 記錄處理結果
            self.articles_data.append(article_data)
            self.chunks_data.extend(chunks)
            
            self.stats['total_articles'] += 1
            self.stats['total_chunks'] += len(chunks)
            
            print(f"   ✅ 完成: {len(chunks)} 個分塊")
            
            return {
                'url': url,
                'article_id': article_id,
                'chunks_count': len(chunks),
                'success': True
            }
            
        except Exception as e:
            error_msg = f"處理 {url} 失敗: {str(e)}"
            print(f"   ❌ {error_msg}")
            raise Exception(error_msg)
    
    def _generate_article_id(self, url: str) -> str:
        """生成文章唯一 ID"""
        # 使用 URL 的 SHA-256 哈希生成 UUID 格式的 ID
        import uuid
        hash_value = hashlib.sha256(url.encode('utf-8')).hexdigest()
        # 将哈希值转换为 UUID 格式
        uuid_str = f"{hash_value[:8]}-{hash_value[8:12]}-{hash_value[12:16]}-{hash_value[16:20]}-{hash_value[20:32]}"
        return uuid_str
    
    async def _chunk_content(self, article_data: Dict) -> List[Dict]:
        """對文章內容進行分塊"""
        content = article_data['content']
        
        try:
            # 使用分塊器處理內容
            chunks = await asyncio.to_thread(self.chunker.chunk, content)
            
            # 準備分塊數據
            chunk_data_list = []
            for i, chunk_obj in enumerate(chunks):
                # 處理 Chunk 對象，獲取其 content 屬性
                if hasattr(chunk_obj, 'content'):
                    chunk_text = chunk_obj.content
                else:
                    chunk_text = str(chunk_obj)
                
                if not chunk_text.strip():
                    continue
                
                chunk_id = f"{article_data['id']}_{i:04d}"
                
                # 将分块 ID 转换为 UUID 格式
                chunk_hash = hashlib.sha256(f"{article_data['url']}_{i}".encode('utf-8')).hexdigest()
                chunk_uuid = f"{chunk_hash[:8]}-{chunk_hash[8:12]}-{chunk_hash[12:16]}-{chunk_hash[16:20]}-{chunk_hash[20:32]}"
                
                chunk_data = {
                    'id': chunk_uuid,
                    'article_id': article_data['id'],
                    'chunk_index': i,
                    'content': chunk_text.strip(),
                    'metadata': {
                        'chunk_length': len(chunk_text.strip()),
                        'chunker_type': self.chunker_type,
                        'chunker_params': self.chunker_params,
                        'created_at': datetime.now().isoformat()
                    }
                }
                
                chunk_data_list.append(chunk_data)
            
            return chunk_data_list
            
        except Exception as e:
            raise Exception(f"內容分塊失敗: {e}")
    
    async def _save_article_and_chunks(self, article_data: Dict, chunks: List[Dict]) -> None:
        """保存文章和分塊到資料庫"""
        try:
            # 準備文章模型
            article_model = ArticleModel(
                url=article_data['url'],
                title=article_data['title'],
                content=article_data['content'],
                metadata=article_data['metadata']
            )
            
            # 設置自定義 ID
            article_model.id = article_data['id']
            
            # 使用增強版資料庫管理器保存文章
            await self.db_manager.create_article(article_model)
            
            # 準備分塊模型
            chunk_models = []
            for chunk_data in chunks:
                chunk_model = ChunkModel(
                    article_id=chunk_data['article_id'],
                    chunk_index=chunk_data['chunk_index'],
                    content=chunk_data['content'],
                    metadata=chunk_data['metadata']
                )
                # 設置自定義 ID
                chunk_model.id = chunk_data['id']
                chunk_models.append(chunk_model)
            
            # 批量保存分塊
            if chunk_models:
                await self.db_manager.create_chunks(chunk_models)
            
        except Exception as e:
            self.logger.error(f"資料庫保存失敗: {e}")
            raise Exception(f"資料庫保存失敗: {e}")
    
    async def generate_chunks_list(self) -> None:
        """生成分塊清單文件"""
        if not self.chunks_data:
            print("⚠️ 沒有分塊數據需要輸出")
            return
        
        print(f"\n📝 正在生成分塊清單文件: {self.output_file}")
        
        try:
            # 按文章分組分塊
            articles_chunks = {}
            for chunk in self.chunks_data:
                article_id = chunk['article_id']
                if article_id not in articles_chunks:
                    articles_chunks[article_id] = []
                articles_chunks[article_id].append(chunk)
            
            # 寫入分塊清單文件
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"# 分塊清單文件\n")
                f.write(f"# 生成時間: {datetime.now().isoformat()}\n")
                f.write(f"# 分塊器類型: {self.chunker_type}\n")
                f.write(f"# 總文章數: {len(articles_chunks)}\n")
                f.write(f"# 總分塊數: {len(self.chunks_data)}\n")
                f.write(f"\n")
                
                # 找到對應的文章數據
                articles_lookup = {article['id']: article for article in self.articles_data}
                
                for article_id, chunks in articles_chunks.items():
                    article = articles_lookup.get(article_id, {})
                    
                    f.write(f"# Article: {article.get('title', 'Unknown Title')}\n")
                    f.write(f"# URL: {article.get('url', 'Unknown URL')}\n")
                    f.write(f"# Article ID: {article_id}\n")
                    f.write(f"\n")
                    
                    # 按分塊索引排序
                    chunks.sort(key=lambda x: x['chunk_index'])
                    
                    for chunk in chunks:
                        f.write(f"## Chunk {chunk['chunk_index'] + 1}\n")
                        f.write(f"# Chunk ID: {chunk['id']}\n")
                        f.write(f"# Length: {len(chunk['content'])} 字符\n")
                        f.write(f"\n")
                        f.write(f"{chunk['content']}\n")
                        f.write(f"\n---\n\n")
            
            print(f"✅ 分塊清單已保存: {self.output_file}")
            print(f"   📊 包含 {len(articles_chunks)} 篇文章，{len(self.chunks_data)} 個分塊")
            
        except Exception as e:
            print(f"❌ 生成分塊清單失敗: {e}")
    
    def print_summary(self) -> None:
        """打印處理摘要"""
        print(f"\n📋 內容處理摘要:")
        print(f"=" * 60)
        print(f"📊 處理統計:")
        print(f"   • 總 URL 數: {self.stats['total_urls']}")
        print(f"   • 已處理 URL: {self.stats['processed_urls']}")
        print(f"   • 成功爬取: {self.stats['successful_crawls']}")
        print(f"   • 失敗爬取: {self.stats['failed_crawls']}")
        print(f"   • 總文章數: {self.stats['total_articles']}")
        print(f"   • 總分塊數: {self.stats['total_chunks']}")
        
        if self.stats['processed_urls'] > 0:
            success_rate = (self.stats['successful_crawls'] / self.stats['processed_urls']) * 100
            print(f"   • 成功率: {success_rate:.1f}%")
        
        if self.stats['total_articles'] > 0:
            avg_chunks = self.stats['total_chunks'] / self.stats['total_articles']
            print(f"   • 平均分塊數: {avg_chunks:.1f} 個/篇")
        
        print(f"\n⏱️ 性能統計:")
        print(f"   • 總處理時間: {self.stats['processing_time']:.2f} 秒")
        
        if self.stats['successful_crawls'] > 0:
            avg_time_per_url = self.stats['processing_time'] / self.stats['successful_crawls']
            print(f"   • 平均每個 URL: {avg_time_per_url:.2f} 秒")
            
            throughput = self.stats['successful_crawls'] / self.stats['processing_time']
            print(f"   • 處理速度: {throughput:.2f} URL/秒")
        
        print(f"🔧 配置資訊:")
        print(f"   • 分塊器類型: {self.chunker_type}")
        print(f"   • 分塊器參數: {self.chunker_params}")
        print(f"   • 輸出文件: {self.output_file}")
        print(f"   • 最大工作執行緒: {self.max_workers}")
        
        # 顯示錯誤摘要
        if self.stats['errors']:
            print(f"\n❌ 錯誤摘要 (前 3 個):")
            for i, error in enumerate(self.stats['errors'][:3], 1):
                print(f"   {i}. {error['url'][:50]}... - {error['error']}")
            
            if len(self.stats['errors']) > 3:
                print(f"   ... 還有 {len(self.stats['errors']) - 3} 個錯誤")
        
        print(f"=" * 60)
        
        if self.stats['total_chunks'] > 0:
            print(f"🎯 內容爬取和分塊完成！")
            print(f"📝 分塊清單文件: {self.output_file}")
            print(f"🔄 下一步可執行: python scripts/getEmbedding.py --chunk-list {self.output_file}")


async def main():
    """主函數"""
    # 初始化日志
    logger = SpiderLogger("content_processor_main")
    logger.info("開始內容爬取和分塊流程")
    
    parser = argparse.ArgumentParser(description='網頁內容爬取和分塊工具')
    parser.add_argument('--url-list', required=True, help='URL 清單文件')
    parser.add_argument('--output', default='chunks.txt', help='分塊清單輸出文件')
    parser.add_argument('--chunker', default='sliding_window', 
                       choices=['sliding_window', 'sentence', 'semantic'],
                       help='分塊器類型')
    parser.add_argument('--chunk-size', type=int, default=300, help='分塊大小')
    parser.add_argument('--overlap', type=int, default=50, help='重疊大小')
    parser.add_argument('--batch-size', type=int, default=5, help='批次處理大小')
    parser.add_argument('--max-workers', type=int, default=3, help='最大並發數')
    
    args = parser.parse_args()
    
    # 記錄運行參數
    logger.info(f"運行參數: {vars(args)}")
    
    print(f"🚀 開始內容爬取和分塊流程")
    print(f"📖 URL 清單: {args.url_list}")
    print(f"📝 輸出文件: {args.output}")
    print(f"✂️ 分塊器: {args.chunker}")
    print(f"📏 分塊大小: {args.chunk_size}")
    print(f"🔄 重疊大小: {args.overlap}")
    print(f"📦 批次大小: {args.batch_size}")
    print(f"⚡ 並發數: {args.max_workers}")
    
    # 準備分塊器參數
    chunker_params = {
        'window_size': args.chunk_size,
        'step_size': args.overlap
    }
    
    processor = ContentProcessor(
        output_file=args.output,
        chunker_type=args.chunker,
        chunker_params=chunker_params,
        max_workers=args.max_workers
    )
    
    try:
        # 1. 解析 URL 清單  
        logger.info("開始解析 URL 清單")
        urls = processor.parse_urls_file(args.url_list)
        logger.info(f"解析到 {len(urls)} 個 URL")
        
        if not urls:
            logger.warning("未找到有效 URL")
            print("⚠️ 未找到有效 URL，退出處理")
            return
        
        # 2. 批量處理 URL
        logger.info("開始批量處理 URL")
        await processor.process_urls_batch(urls, args.batch_size)
        
        # 3. 生成分塊清單
        logger.info("生成分塊清單")
        await processor.generate_chunks_list()
        
        # 4. 打印摘要
        processor.print_summary()
        
        logger.info(f"處理完成: 總文章數={processor.stats['total_articles']}, 總分塊數={processor.stats['total_chunks']}")
        
        if processor.stats['total_chunks'] > 0:
            print(f"\n🎉 內容爬取和分塊完成！")
            print(f"📝 分塊清單已生成: {args.output}")
            print(f"🔄 下一步請執行向量嵌入:")
            print(f"   python scripts/getEmbedding.py --chunk-list {args.output}")
        else:
            print(f"\n⚠️ 未生成任何分塊，請檢查 URL 清單或網絡連接")
        
    except Exception as e:
        logger.error(f"執行失敗: {e}")
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
