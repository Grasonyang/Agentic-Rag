#!/usr/bin/env python3
"""
make-chunk-data.py
資料分塊腳本 - RAG 流程第三步
將爬取的文章內容分塊處理
"""

import sys
from pathlib import Path
from typing import List

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.client import SupabaseClient
from database.operations import DatabaseOperations
from database.models import ChunkModel
from spider.chunking.chunker_factory import ChunkerFactory
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def chunk_articles(chunker_type: str = "sliding_window", chunk_size: int = 500):
    """對所有文章進行分塊處理"""
    print("📄 RAG 步驟 3: 資料分塊")
    print("=" * 50)
    
    try:
        # 連接資料庫
        print("📡 連接資料庫...")
        client = SupabaseClient()
        db_ops = DatabaseOperations(client.get_client())
        
        # 獲取所有文章
        print("📚 獲取文章列表...")
        articles = db_ops.get_all_articles()
        
        if not articles:
            print("❌ 沒有找到任何文章")
            print("🎯 請先執行 'make crawl' 爬取資料")
            return False
        
        print(f"📊 找到 {len(articles)} 篇文章")
        
        # 初始化分塊器
        print(f"🔧 初始化分塊器: {chunker_type}")
        chunker = ChunkerFactory.create_chunker(
            chunker_type, 
            window_size=chunk_size,
            step_size=chunk_size // 2
        )
        
        total_chunks = 0
        processed_articles = 0
        
        for i, article in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}] 處理文章: {article.title}")
            
            # 檢查是否已經分塊
            existing_chunks = db_ops.get_article_chunks(article.id)
            if existing_chunks:
                print(f"⏭️ 跳過 (已分塊): {len(existing_chunks)} 個區塊")
                continue
            
            try:
                # 對文章內容進行分塊
                chunks = chunker.chunk(
                    article.content, 
                    metadata={
                        "article_id": article.id,
                        "article_title": article.title,
                        "article_url": article.url
                    }
                )
                
                if not chunks:
                    print("⚠️ 未產生任何分塊")
                    continue
                
                # 儲存分塊到資料庫
                saved_chunks = 0
                for chunk_idx, chunk in enumerate(chunks):
                    chunk_model = ChunkModel(
                        article_id=article.id,
                        content=chunk.content,
                        chunk_index=chunk_idx,
                        start_position=chunk.start_pos,
                        end_position=chunk.end_pos,
                        metadata=chunk.metadata
                    )
                    
                    if db_ops.create_chunk(chunk_model):
                        saved_chunks += 1
                
                print(f"✅ 成功分塊: {saved_chunks}/{len(chunks)} 個區塊")
                total_chunks += saved_chunks
                processed_articles += 1
                
            except Exception as e:
                print(f"❌ 分塊失敗: {e}")
        
        print(f"\n🎉 分塊完成!")
        print(f"📊 處理文章: {processed_articles}/{len(articles)}")
        print(f"📊 總分塊數: {total_chunks}")
        
        if total_chunks > 0:
            print("🎯 下一步: 執行 'make embed' 生成嵌入向量")
        
        return total_chunks > 0
        
    except Exception as e:
        print(f"❌ 分塊過程失敗: {e}")
        return False

def show_chunking_stats():
    """顯示分塊統計"""
    print("📊 分塊統計")
    print("=" * 30)
    
    try:
        client = SupabaseClient()
        db_ops = DatabaseOperations(client.get_client())
        
        stats = db_ops.get_statistics()
        print(f"文章總數: {stats.get('articles_count', 0)}")
        print(f"分塊總數: {stats.get('chunks_count', 0)}")
        
        # 顯示平均分塊數
        if stats.get('articles_count', 0) > 0:
            avg_chunks = stats.get('chunks_count', 0) / stats.get('articles_count', 1)
            print(f"平均每篇文章分塊數: {avg_chunks:.1f}")
            
    except Exception as e:
        print(f"❌ 獲取統計失敗: {e}")

def main():
    """主函數"""
    import argparse
    parser = argparse.ArgumentParser(description="資料分塊工具")
    parser.add_argument("--type", choices=["sliding_window", "sentence", "semantic"], 
                       default="sliding_window", help="分塊方式")
    parser.add_argument("--size", type=int, default=500, help="分塊大小")
    parser.add_argument("--stats", action="store_true", help="顯示分塊統計")
    args = parser.parse_args()
    
    if args.stats:
        show_chunking_stats()
    else:
        chunk_articles(args.type, args.size)

if __name__ == "__main__":
    main()
