#!/usr/bin/env python3
"""
make-embedding.py
嵌入生成腳本 - RAG 流程第四步
為所有分塊生成嵌入向量
"""

import sys
from pathlib import Path
from typing import List

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.client import SupabaseClient
from database.operations import DatabaseOperations
from embedding import EmbeddingManager
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def generate_embeddings(batch_size: int = 10):
    """為所有分塊生成嵌入向量"""
    print("🧠 RAG 步驟 4: 嵌入生成")
    print("=" * 50)
    
    try:
        # 連接資料庫
        print("📡 連接資料庫...")
        client = SupabaseClient()
        db_ops = DatabaseOperations(client.get_client())
        
        # 初始化嵌入管理器
        print("🔧 初始化嵌入模型...")
        embedding_manager = EmbeddingManager()
        
        # 獲取所有需要嵌入的分塊
        print("📄 獲取分塊列表...")
        chunks = db_ops.get_chunks_without_embeddings()
        
        if not chunks:
            print("✅ 所有分塊都已有嵌入向量")
            print("🎯 下一步: 執行 'make search' 進行搜索測試")
            return True
        
        print(f"📊 找到 {len(chunks)} 個待處理分塊")
        
        # 批次處理嵌入
        total_processed = 0
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(chunks), batch_size):
            batch_chunks = chunks[batch_idx:batch_idx + batch_size]
            current_batch = (batch_idx // batch_size) + 1
            
            print(f"\n[批次 {current_batch}/{total_batches}] 處理 {len(batch_chunks)} 個分塊...")
            
            try:
                # 準備文本列表
                texts = [chunk.content for chunk in batch_chunks]
                
                # 生成嵌入向量
                print("🧠 生成嵌入向量...")
                embeddings = embedding_manager.get_embeddings(texts)
                
                # 更新分塊的嵌入向量
                batch_success = 0
                for chunk, embedding in zip(batch_chunks, embeddings):
                    if db_ops.update_chunk_embedding(chunk.id, embedding.tolist()):
                        batch_success += 1
                    else:
                        print(f"❌ 更新嵌入失敗: {chunk.id}")
                
                print(f"✅ 批次完成: {batch_success}/{len(batch_chunks)}")
                total_processed += batch_success
                
            except Exception as e:
                print(f"❌ 批次處理失敗: {e}")
        
        print(f"\n🎉 嵌入生成完成!")
        print(f"📊 成功處理: {total_processed}/{len(chunks)} 個分塊")
        
        if total_processed > 0:
            print("🎯 下一步: 執行 'make search' 進行搜索測試")
        
        return total_processed > 0
        
    except Exception as e:
        print(f"❌ 嵌入生成失敗: {e}")
        return False

def show_embedding_stats():
    """顯示嵌入統計"""
    print("📊 嵌入統計")
    print("=" * 30)
    
    try:
        client = SupabaseClient()
        db_ops = DatabaseOperations(client.get_client())
        
        stats = db_ops.get_statistics()
        chunks_count = stats.get('chunks_count', 0)
        embedded_count = stats.get('embedded_chunks_count', 0)
        
        print(f"分塊總數: {chunks_count}")
        print(f"已嵌入: {embedded_count}")
        print(f"待處理: {chunks_count - embedded_count}")
        
        if chunks_count > 0:
            progress = (embedded_count / chunks_count) * 100
            print(f"完成度: {progress:.1f}%")
            
    except Exception as e:
        print(f"❌ 獲取統計失敗: {e}")

def test_embedding_model():
    """測試嵌入模型"""
    print("🧪 測試嵌入模型")
    print("=" * 30)
    
    try:
        embedding_manager = EmbeddingManager()
        
        test_text = "這是一個測試文本"
        print(f"測試文本: {test_text}")
        
        embedding = embedding_manager.get_embedding(test_text)
        print(f"嵌入維度: {len(embedding)}")
        print(f"嵌入向量範例: {embedding[:5]}...")
        print("✅ 嵌入模型正常工作")
        
    except Exception as e:
        print(f"❌ 嵌入模型測試失敗: {e}")

def main():
    """主函數"""
    import argparse
    parser = argparse.ArgumentParser(description="嵌入生成工具")
    parser.add_argument("--batch-size", type=int, default=10, help="批次大小")
    parser.add_argument("--stats", action="store_true", help="顯示嵌入統計")
    parser.add_argument("--test", action="store_true", help="測試嵌入模型")
    args = parser.parse_args()
    
    if args.test:
        test_embedding_model()
    elif args.stats:
        show_embedding_stats()
    else:
        generate_embeddings(args.batch_size)

if __name__ == "__main__":
    main()
