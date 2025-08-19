"""分塊與嵌入背景工作者"""

import asyncio
from typing import List

from spider.chunking.chunker_factory import ChunkerFactory
from spider.utils.enhanced_logger import get_spider_logger
from embedding.embedding import embed_text


class ChunkEmbedWorker:
    """負責分塊與向量化的背景工作者"""

    def __init__(self, db_manager, chunker_type: str = "sentence"):
        # 資料庫管理器
        self.db_manager = db_manager
        # 建立分塊器
        self.chunker = ChunkerFactory.create_chunker(chunker_type)
        self.logger = get_spider_logger("chunk_embed_worker")
        # 追蹤背景任務
        self.tasks: set[asyncio.Task] = set()

    async def process(self, url_id: str, content: str) -> None:
        """處理單一 URL 的分塊與嵌入"""
        try:
            # 文本分塊
            chunks = self.chunker.chunk(content)
            if not chunks:
                self.logger.warning(f"URL {url_id} 無法分塊")
                return

            texts: List[str] = [c.content for c in chunks]
            embeddings = embed_text(texts)
            if embeddings is None or len(embeddings) != len(chunks):
                self.logger.error(f"URL {url_id} 嵌入計算失敗")
                return

            emb_list = [emb.tolist() for emb in embeddings]
            await self.db_manager.insert_embeddings(url_id, texts, emb_list)
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"背景處理失敗: {exc}")

    async def flush(self) -> None:
        """等待所有背景任務完成"""
        if self.tasks:
            await asyncio.gather(*self.tasks)
