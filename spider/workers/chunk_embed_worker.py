"""分塊與嵌入背景工作者"""

import asyncio
from typing import Optional, Set

from spider.chunking.chunker_factory import ChunkerFactory
from embedding.embedding import embed_text
from spider.utils.enhanced_logger import get_spider_logger


class ChunkEmbedWorker:
    """負責將原始內容分塊並計算向量的工作者"""

    def __init__(self, db_manager, chunker: Optional[object] = None) -> None:
        self.db_manager = db_manager
        self.chunker = chunker or ChunkerFactory.create_sentence_chunker(language="zh")
        self.tasks: Set[asyncio.Task] = set()
        self.logger = get_spider_logger("chunk_embed_worker")

    async def process(self, url_id: str, content: str) -> None:
        """分塊並嵌入內容後寫入資料庫"""
        try:
            chunks = self.chunker.chunk(content)
            if not chunks:
                return

            texts = [c.content for c in chunks]
            embeddings = embed_text(texts)
            if embeddings is None or len(embeddings) != len(chunks):
                return

            sql = (
                "INSERT INTO embeddings (url_id, chunk_index, content, embedding) "
                "VALUES (%s, %s, %s, %s)"
            )
            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                await self.db_manager._execute_async_with_retry(
                    lambda idx=idx, chunk=chunk, emb=emb: self.db_manager._db_ops.client.execute_query(
                        sql, (url_id, idx, chunk.content, emb.tolist()), fetch=False
                    ),
                    f"insert_embedding_{url_id}_{idx}",
                )
        except Exception as e:  # noqa: BLE001
            self.logger.error(f"處理 {url_id} 時發生錯誤: {e}")

    def add_task(self, task: asyncio.Task) -> None:
        """追蹤背景任務"""
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def flush(self) -> None:
        """等待所有任務完成"""
        if self.tasks:
            await asyncio.gather(*self.tasks)
