"""
腳本三: 內容處理與向量化 (Process and Embed)

功能:
1. 從資料庫中查找尚未被處理的文章 (即沒有對應分塊的文章)。
2. 使用 SentenceChunking 對每篇文章的內容進行分塊。
3. 使用 embedding 模組為每個分塊生成向量嵌入。
4. 將分塊內容和對應的向量存入 `article_chunks` 表。
5. 此腳本可重複執行，直到所有文章都被處理完畢。

執行方式:
python -m scripts.3_process_and_embed --limit 10
"""

import argparse

# 配置專案根目錄
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.operations import get_database_operations, DatabaseOperations
from database.models import ChunkModel
from spider.chunking.sentence_chunking import SentenceChunking, SentenceChunkingConfig
from embedding.embedding import embed_text, get_embedding_dimension
from scripts.utils import get_script_logger

logger = get_script_logger("process_and_embed")

def main(limit: int):
    """
    主執行函數

    Args:
        limit (int): 每次執行時處理的文章數量上限。
    """
    logger.info(f"內容處理與向量化腳本開始執行，本次最多處理 {limit} 篇文章。")

    db_ops = get_database_operations()
    if not db_ops:
        logger.error("無法初始化資料庫連接，腳本終止。")
        return

    # 1. 獲取需要處理的文章
    # 這裡使用一個 RPC 函數來獲取未處理的文章，更高效
    # 如果沒有 RPC 函數，則需要手動查詢 articles 和 article_chunks 來比對
    try:
        response = db_ops.client.rpc('get_unprocessed_articles', {'row_limit': limit}).execute()
        if not response.data:
            logger.info("沒有需要處理的新文章，腳本執行完畢。")
            return
        articles_to_process = response.data
    except Exception as e:
        logger.error(f"獲取未處理文章時發生錯誤: {e}。請確認 `get_unprocessed_articles` RPC 函數是否存在。")
        # 提供一個備用方案 (效率較低)
        logger.info("正在嘗試使用備用方案獲取未處理文章...")
        all_articles_resp = db_ops.client.table('articles').select('id, content').limit(limit * 2).execute()
        if not all_articles_resp.data:
            logger.info("沒有需要處理的新文章，腳本執行完畢。")
            return
        
        processed_chunks_resp = db_ops.client.table('article_chunks').select('article_id').in_(
            'article_id', [a['id'] for a in all_articles_resp.data]
        ).execute()
        processed_article_ids = {c['article_id'] for c in processed_chunks_resp.data}
        articles_to_process = [a for a in all_articles_resp.data if a['id'] not in processed_article_ids][:limit]
        
        if not articles_to_process:
            logger.info("沒有需要處理的新文章，腳本執行完畢。")
            return

    logger.info(f"從資料庫獲取了 {len(articles_to_process)} 篇待處理的文章。")

    # 2. 初始化分塊器和檢查向量維度
    chunker = SentenceChunking(SentenceChunkingConfig(language='zh'))
    embedding_dim = get_embedding_dimension()
    if embedding_dim == 0:
        logger.error("無法獲取嵌入模型維度，腳本終止。")
        return
    logger.info(f"嵌入向量維度為: {embedding_dim}")

    # 3. 逐一處理文章
    total_chunks_created = 0
    for article in articles_to_process:
        article_id = article.get('id')
        content = article.get('content')

        if not content or not article_id:
            logger.warning(f"文章 {article_id} 內容為空，跳過。")
            continue

        logger.info(f"正在處理文章 ID: {article_id}")

        # a. 文本分塊
        chunks = chunker.chunk(content)
        if not chunks:
            logger.warning(f"文章 {article_id} 未能成功分塊，跳過。")
            continue
        
        logger.info(f"文章 {article_id} 被分割成 {len(chunks)} 個分塊。")

        # b. 生成向量嵌入
        chunk_contents = [chunk.content for chunk in chunks]
        embeddings = embed_text(chunk_contents)

        if embeddings is None or len(embeddings) != len(chunks):
            logger.error(f"為文章 {article_id} 生成嵌入向量失敗，跳過。")
            continue
        
        logger.info(f"成功為 {len(chunks)} 個分塊生成向量。")

        # c. 準備數據模型並存入資料庫
        chunk_models = [
            ChunkModel(
                article_id=article_id,
                content=chunk.content,
                chunk_index=chunk.index,
                embedding=embedding.tolist(), # 將 tensor 轉換為 list
                metadata=chunk.metadata
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        created_count = db_ops.create_chunks(chunk_models)
        total_chunks_created += created_count
        logger.info(f"成功為文章 {article_id} 在資料庫中創建了 {created_count} 個分塊記錄。")

    logger.info(f"本次執行完成。共為 {len(articles_to_process)} 篇文章創建了 {total_chunks_created} 個分塊。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="內容處理與向量化腳本。")
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='每次執行時處理的文章數量上限。'
    )
    args = parser.parse_args()
    
    main(args.limit)
