#!/usr/bin/env python3
"""
getEmbedding.py - 向量嵌入和資料庫存儲腳本

功能：
1. 讀取分塊清單文件
2. 批量生成文本向量嵌入
3. 更新資料庫中的向量數據
4. 記錄嵌入處理日誌
5. 驗證向量存儲完整性

使用方法：
    python scripts/getEmbedding.py --chunk-list chunks.txt
    python scripts/getEmbedding.py --chunk-list chunks.txt --batch-size 32 --device cuda
    make get-embedding CHUNK_LIST=chunks.txt
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re
import numpy as np

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

from embedding.embedding import EmbeddingManager
from database.client import SupabaseClient
from database.models import SearchLogModel


class EmbeddingProcessor:
    """向量嵌入處理類"""
    
    def __init__(self, batch_size: int = 16, device: str = 'auto'):
        self.embedding_manager = EmbeddingManager(device=device)
        self.db_client = SupabaseClient()
        self.batch_size = batch_size
        
        # 處理統計
        self.stats = {
            'total_chunks': 0,
            'processed_chunks': 0,
            'successful_embeddings': 0,
            'failed_embeddings': 0,
            'updated_database': 0,
            'processing_time': 0,
            'errors': []
        }
        
        # 存儲處理數據
        self.chunks_data: List[Dict] = []
        self.embedding_results: List[Dict] = []
    
    def parse_chunks_file(self, chunks_file: str) -> List[Dict]:
        """解析分塊文件，提取分塊資訊"""
        print(f"📖 正在解析分塊文件: {chunks_file}")
        
        if not os.path.exists(chunks_file):
            raise FileNotFoundError(f"分塊文件不存在: {chunks_file}")
        
        chunks = []
        current_chunk = None
        content_lines = []
        
        try:
            with open(chunks_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.rstrip()
                    
                    # 解析文章資訊
                    if line.startswith('# Article:'):
                        current_article_title = line.replace('# Article:', '').strip()
                    elif line.startswith('# URL:'):
                        current_article_url = line.replace('# URL:', '').strip()
                    elif line.startswith('# Article ID:'):
                        current_article_id = line.replace('# Article ID:', '').strip()
                    
                    # 解析分塊資訊
                    elif line.startswith('## Chunk'):
                        # 保存前一個分塊
                        if current_chunk and content_lines:
                            current_chunk['content'] = '\n'.join(content_lines).strip()
                            if current_chunk['content']:
                                chunks.append(current_chunk)
                        
                        # 開始新分塊
                        chunk_match = re.match(r'## Chunk (\d+)', line)
                        if chunk_match:
                            current_chunk = {
                                'chunk_index': int(chunk_match.group(1)),
                                'article_title': current_article_title,
                                'article_url': current_article_url,
                                'article_id': current_article_id,
                                'line_number': line_num
                            }
                            content_lines = []
                    
                    elif line.startswith('# Chunk ID:'):
                        if current_chunk:
                            current_chunk['chunk_id'] = line.replace('# Chunk ID:', '').strip()
                    
                    elif line.startswith('# Length:'):
                        if current_chunk:
                            length_match = re.search(r'(\d+)', line)
                            if length_match:
                                current_chunk['content_length'] = int(length_match.group(1))
                    
                    elif line == '---':
                        # 分塊結束標記，保存當前分塊
                        if current_chunk and content_lines:
                            current_chunk['content'] = '\n'.join(content_lines).strip()
                            if current_chunk['content']:
                                chunks.append(current_chunk)
                            current_chunk = None
                            content_lines = []
                    
                    elif line and not line.startswith('#'):
                        # 分塊內容
                        if current_chunk is not None:
                            content_lines.append(line)
                
                # 處理最後一個分塊
                if current_chunk and content_lines:
                    current_chunk['content'] = '\n'.join(content_lines).strip()
                    if current_chunk['content']:
                        chunks.append(current_chunk)
            
            # 驗證和清理數據
            valid_chunks = []
            for chunk in chunks:
                if self._validate_chunk_data(chunk):
                    valid_chunks.append(chunk)
                else:
                    print(f"⚠️ 跳過無效分塊: 行 {chunk.get('line_number', '?')}")
            
            self.stats['total_chunks'] = len(valid_chunks)
            print(f"✅ 解析完成，找到 {len(valid_chunks)} 個有效分塊")
            return valid_chunks
            
        except Exception as e:
            raise Exception(f"解析分塊文件失敗: {e}")
    
    def _validate_chunk_data(self, chunk: Dict) -> bool:
        """驗證分塊數據完整性"""
        required_fields = ['chunk_id', 'article_id', 'content']
        
        for field in required_fields:
            if not chunk.get(field):
                return False
        
        # 內容長度檢查
        if len(chunk['content'].strip()) < 10:
            return False
        
        return True
    
    async def process_embeddings_batch(self, chunks: List[Dict]) -> None:
        """批量處理向量嵌入"""
        print(f"\n🚀 開始批量生成向量嵌入 (批次大小: {self.batch_size})")
        
        start_time = datetime.now()
        
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size
            
            print(f"\n🧠 處理嵌入批次 {batch_num}/{total_batches} ({len(batch)} 個分塊)")
            
            try:
                # 提取批次文本
                batch_texts = [chunk['content'] for chunk in batch]
                
                # 生成嵌入向量
                print("   ⚡ 正在生成向量嵌入...")
                embeddings = await asyncio.to_thread(
                    self.embedding_manager.get_embeddings, batch_texts
                )
                
                if len(embeddings) != len(batch):
                    raise Exception(f"嵌入數量不匹配: 期望 {len(batch)}, 得到 {len(embeddings)}")
                
                # 準備結果數據
                for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                    if embedding is not None and len(embedding) > 0:
                        result = {
                            'chunk_id': chunk['chunk_id'],
                            'article_id': chunk['article_id'],
                            'content': chunk['content'],
                            'embedding': embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
                            'embedding_dim': len(embedding),
                            'content_length': len(chunk['content']),
                            'processed_at': datetime.now().isoformat()
                        }
                        self.embedding_results.append(result)
                        self.stats['successful_embeddings'] += 1
                    else:
                        error_msg = f"嵌入生成失敗: chunk_id={chunk['chunk_id']}"
                        print(f"   ❌ {error_msg}")
                        self.stats['failed_embeddings'] += 1
                        self.stats['errors'].append({
                            'chunk_id': chunk['chunk_id'],
                            'error': error_msg
                        })
                
                self.stats['processed_chunks'] += len(batch)
                
                # 顯示進度
                progress = (self.stats['processed_chunks'] / self.stats['total_chunks']) * 100
                print(f"   ✅ 批次完成，進度: {progress:.1f}%")
                
            except Exception as e:
                error_msg = f"批次 {batch_num} 處理失敗: {str(e)}"
                print(f"   ❌ {error_msg}")
                
                # 記錄批次中每個分塊的錯誤
                for chunk in batch:
                    self.stats['failed_embeddings'] += 1
                    self.stats['errors'].append({
                        'chunk_id': chunk['chunk_id'],
                        'error': error_msg
                    })
                
                self.stats['processed_chunks'] += len(batch)
        
        end_time = datetime.now()
        self.stats['processing_time'] = (end_time - start_time).total_seconds()
        
        print(f"\n✅ 嵌入生成完成！")
        print(f"   ⏱️ 耗時: {self.stats['processing_time']:.2f} 秒")
        print(f"   🎯 成功: {self.stats['successful_embeddings']} 個")
        print(f"   ❌ 失敗: {self.stats['failed_embeddings']} 個")
    
    async def update_database(self) -> None:
        """更新資料庫中的向量數據"""
        if not self.embedding_results:
            print("⚠️ 沒有嵌入結果需要更新到資料庫")
            return
        
        print(f"\n💾 正在更新資料庫向量數據...")
        print(f"📊 準備更新 {len(self.embedding_results)} 個分塊的向量")
        
        try:
            supabase = self.db_client.get_client()
            batch_size = 50  # 資料庫更新批次大小
            updated_count = 0
            
            for i in range(0, len(self.embedding_results), batch_size):
                batch = self.embedding_results[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(self.embedding_results) + batch_size - 1) // batch_size
                
                print(f"   📦 更新批次 {batch_num}/{total_batches} ({len(batch)} 個分塊)")
                
                # 準備更新數據
                updates = []
                for result in batch:
                    update_data = {
                        'id': result['chunk_id'],
                        'embedding': result['embedding'],
                        'metadata': {
                            'embedding_model': self.embedding_manager.model_name,
                            'embedding_dim': result['embedding_dim'],
                            'embedded_at': result['processed_at'],
                            'content_length': result['content_length']
                        }
                    }
                    updates.append(update_data)
                
                # 批量更新
                try:
                    result = supabase.from_('article_chunks')\
                        .upsert(updates, on_conflict='id')\
                        .execute()
                    
                    if result.data:
                        batch_updated = len(result.data)
                        updated_count += batch_updated
                        print(f"   ✅ 更新成功: {batch_updated} 個分塊")
                    else:
                        print(f"   ⚠️ 批次更新無數據返回")
                
                except Exception as e:
                    print(f"   ❌ 批次 {batch_num} 更新失敗: {e}")
                    continue
            
            self.stats['updated_database'] = updated_count
            print(f"\n✅ 資料庫更新完成！")
            print(f"   📊 成功更新: {updated_count} 個分塊向量")
            
            # 記錄處理日誌
            await self._log_processing_summary()
            
        except Exception as e:
            print(f"❌ 資料庫更新失敗: {e}")
    
    async def _log_processing_summary(self) -> None:
        """記錄處理摘要到搜索日誌"""
        try:
            supabase = self.db_client.get_client()
            
            log_entry = SearchLogModel(
                query=f"embedding_processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                results_count=self.stats['successful_embeddings'],
                response_time_ms=int(self.stats['processing_time'] * 1000),
                search_type='embedding_processing',
                metadata={
                    'total_chunks': self.stats['total_chunks'],
                    'successful_embeddings': self.stats['successful_embeddings'],
                    'failed_embeddings': self.stats['failed_embeddings'],
                    'updated_database': self.stats['updated_database'],
                    'processing_time_seconds': self.stats['processing_time'],
                    'batch_size': self.batch_size,
                    'embedding_model': self.embedding_manager.model_name,
                    'error_count': len(self.stats['errors'])
                }
            )
            
            result = supabase.from_('search_logs').insert(log_entry.to_dict()).execute()
            
            if result.data:
                print(f"📝 處理日誌已記錄")
        
        except Exception as e:
            print(f"⚠️ 記錄處理日誌失敗: {e}")
    
    async def validate_embeddings(self) -> None:
        """驗證向量嵌入完整性"""
        if not self.embedding_results:
            return
        
        print(f"\n🔍 正在驗證向量嵌入完整性...")
        
        try:
            supabase = self.db_client.get_client()
            
            # 隨機選擇幾個分塊進行驗證
            import random
            sample_size = min(5, len(self.embedding_results))
            samples = random.sample(self.embedding_results, sample_size)
            
            print(f"   🎯 隨機檢查 {sample_size} 個分塊")
            
            valid_count = 0
            for sample in samples:
                chunk_id = sample['chunk_id']
                
                # 從資料庫查詢向量
                result = supabase.from_('article_chunks')\
                    .select('id, embedding')\
                    .eq('id', chunk_id)\
                    .limit(1)\
                    .execute()
                
                if result.data and result.data[0].get('embedding'):
                    db_embedding = result.data[0]['embedding']
                    
                    # 驗證維度
                    if len(db_embedding) == len(sample['embedding']):
                        valid_count += 1
                        print(f"   ✅ {chunk_id}: 向量完整 ({len(db_embedding)} 維)")
                    else:
                        print(f"   ❌ {chunk_id}: 向量維度不匹配")
                else:
                    print(f"   ❌ {chunk_id}: 未找到向量數據")
            
            if valid_count == sample_size:
                print(f"   🎉 驗證通過！所有樣本向量正常")
            else:
                print(f"   ⚠️ 驗證結果: {valid_count}/{sample_size} 個樣本正常")
        
        except Exception as e:
            print(f"   ❌ 驗證過程出錯: {e}")
    
    def print_summary(self) -> None:
        """打印處理摘要"""
        print(f"\n📋 向量嵌入處理摘要:")
        print(f"=" * 60)
        print(f"📊 處理統計:")
        print(f"   • 總分塊數: {self.stats['total_chunks']}")
        print(f"   • 已處理分塊: {self.stats['processed_chunks']}")
        print(f"   • 成功嵌入: {self.stats['successful_embeddings']}")
        print(f"   • 失敗嵌入: {self.stats['failed_embeddings']}")
        print(f"   • 資料庫更新: {self.stats['updated_database']}")
        
        if self.stats['processed_chunks'] > 0:
            success_rate = (self.stats['successful_embeddings'] / self.stats['processed_chunks']) * 100
            print(f"   • 成功率: {success_rate:.1f}%")
        
        print(f"\n⏱️ 性能統計:")
        print(f"   • 總處理時間: {self.stats['processing_time']:.2f} 秒")
        
        if self.stats['successful_embeddings'] > 0:
            avg_time = self.stats['processing_time'] / self.stats['successful_embeddings']
            print(f"   • 平均每個嵌入: {avg_time:.3f} 秒")
            
            throughput = self.stats['successful_embeddings'] / self.stats['processing_time']
            print(f"   • 處理速度: {throughput:.1f} 個/秒")
        
        print(f"\n🧠 模型資訊:")
        print(f"   • 嵌入模型: {self.embedding_manager.model_name}")
        print(f"   • 向量維度: {self.embedding_manager.embedding_dim}")
        print(f"   • 計算設備: {self.embedding_manager.device}")
        print(f"   • 批次大小: {self.batch_size}")
        
        # 顯示錯誤摘要
        if self.stats['errors']:
            print(f"\n❌ 錯誤摘要 (前 3 個):")
            for i, error in enumerate(self.stats['errors'][:3], 1):
                print(f"   {i}. {error['chunk_id']}: {error['error']}")
            
            if len(self.stats['errors']) > 3:
                print(f"   ... 還有 {len(self.stats['errors']) - 3} 個錯誤")
        
        print(f"=" * 60)
        
        if self.stats['updated_database'] > 0:
            print(f"🎯 向量嵌入流程完成！資料庫已準備好進行語義搜索")
            print(f"🔍 您可以使用以下方式測試搜索功能:")
            print(f"   python -c \"from database.operations import DatabaseOperations; db = DatabaseOperations(); print(db.semantic_search('測試查詢', limit=3))\"")


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='向量嵌入和資料庫存儲工具')
    parser.add_argument('--chunk-list', required=True, help='分塊清單文件')
    parser.add_argument('--batch-size', type=int, default=16, help='嵌入批次大小')
    parser.add_argument('--device', default='auto', choices=['auto', 'cuda', 'cpu'], help='計算設備')
    parser.add_argument('--no-db-update', action='store_true', help='不更新資料庫')
    parser.add_argument('--validate', action='store_true', help='驗證嵌入完整性')
    
    args = parser.parse_args()
    
    print(f"🚀 開始向量嵌入處理流程")
    print(f"📖 分塊清單: {args.chunk_list}")
    print(f"🧠 批次大小: {args.batch_size}")
    print(f"💻 計算設備: {args.device}")
    
    processor = EmbeddingProcessor(
        batch_size=args.batch_size,
        device=args.device
    )
    
    try:
        # 1. 解析分塊文件
        chunks = processor.parse_chunks_file(args.chunk_list)
        
        if not chunks:
            print("⚠️ 未找到有效分塊，退出處理")
            return
        
        # 2. 批量生成嵌入
        await processor.process_embeddings_batch(chunks)
        
        # 3. 更新資料庫（如果啟用）
        if not args.no_db_update and processor.embedding_results:
            await processor.update_database()
        
        # 4. 驗證嵌入（如果啟用）
        if args.validate and processor.embedding_results:
            await processor.validate_embeddings()
        
        # 5. 打印摘要
        processor.print_summary()
        
        if processor.stats['updated_database'] > 0:
            print(f"\n🎉 向量嵌入流程完成！")
            print(f"🔍 RAG 系統已準備就緒，可以進行語義搜索")
        else:
            print(f"\n⚠️ 向量嵌入完成，但未更新到資料庫")
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
