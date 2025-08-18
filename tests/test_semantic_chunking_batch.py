import sys
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).resolve().parent.parent))

from spider.chunking.semantic_chunking import SemanticChunking, SemanticChunkingConfig


class FakeEmbeddingModel:
    """簡單的嵌入模型，使用句子長度作為向量"""

    def encode(self, sentences):
        # 將句子長度轉為一維向量
        return np.array([[len(s)] for s in sentences], dtype=float)


def test_batch_embeddings_consistent():
    """確認分批計算與一次計算的結果一致"""

    text = "今天天氣很好。我們去公園散步。接著去吃冰淇淋。回家後休息。"

    # 取得句子列表
    sentences = SemanticChunking().sentence_chunker._split_into_sentences(text)

    # 不分批處理
    cfg_full = SemanticChunkingConfig(use_embedding_model=False, embedding_batch_size=64)
    chunker_full = SemanticChunking(cfg_full)
    chunker_full.embedding_model = FakeEmbeddingModel()
    chunker_full.config.use_embedding_model = True

    # 分批處理
    cfg_batch = SemanticChunkingConfig(use_embedding_model=False, embedding_batch_size=2)
    chunker_batch = SemanticChunking(cfg_batch)
    chunker_batch.embedding_model = FakeEmbeddingModel()
    chunker_batch.config.use_embedding_model = True

    groups_full = chunker_full._group_by_embedding_similarity(sentences)
    groups_batch = chunker_batch._group_by_embedding_similarity(sentences)

    assert groups_full == groups_batch
