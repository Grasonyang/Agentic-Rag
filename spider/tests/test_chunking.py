import pytest

from spider.chunking.chunker_factory import ChunkerFactory
from spider.chunking.sentence_chunking import SentenceChunking, SentenceChunkingConfig
from spider.chunking.sliding_window import SlidingWindowChunking, SlidingWindowConfig
from spider.chunking.semantic_chunking import SemanticChunking, SemanticChunkingConfig


@pytest.mark.parametrize(
    "chunker_type, expected_class, config",
    [
        ("sentence", SentenceChunking, {}),
        ("sliding_window", SlidingWindowChunking, {}),
        ("semantic", SemanticChunking, {"use_embedding_model": False}),
    ],
)
def test_chunker_factory_create_chunker(chunker_type, expected_class, config):
    """測試工廠建立對應類型的分塊器"""
    chunker = ChunkerFactory.create_chunker(chunker_type, config)
    assert isinstance(chunker, expected_class)


@pytest.mark.parametrize(
    "max_sentences, expected",
    [
        # 當每塊僅允許一個句子時，應產生四個塊
        (1, ["第一句", "第二句", "第三句", "第四句"]),
        # 當每塊允許兩個句子時，應產生兩個塊
        (2, ["第一句第二句", "第三句第四句"]),
    ],
)
def test_sentence_chunking(max_sentences, expected):
    """測試句子分塊器的分塊結果"""
    text = "第一句。第二句。第三句。第四句。"
    config = SentenceChunkingConfig(
        max_sentences_per_chunk=max_sentences,
        min_sentences_per_chunk=1,
        sentence_overlap=0,
        respect_paragraph_breaks=False,
        min_chunk_size=1,
    )
    chunker = SentenceChunking(config)
    chunks = chunker.chunk(text)
    assert [c.content for c in chunks] == expected


@pytest.mark.parametrize(
    "step_size, expected",
    [
        # 步長為 1 時，每次滑動一個單詞
        (1, ["w1 w2 w3", "w2 w3 w4", "w3 w4 w5"]),
        # 步長為 2 時，每次滑動兩個單詞
        (2, ["w1 w2 w3", "w3 w4 w5"]),
    ],
)
def test_sliding_window_chunking(step_size, expected):
    """測試滑動窗口分塊器的分塊結果"""
    text = "w1 w2 w3 w4 w5"
    config = SlidingWindowConfig(
        window_size=3,
        step_size=step_size,
        use_sentences=False,
        min_chunk_size=1,
    )
    chunker = SlidingWindowChunking(config)
    chunks = chunker.chunk(text)
    assert [c.content for c in chunks] == expected


@pytest.mark.parametrize(
    "threshold, expected",
    [
        # 相似度閾值為 0 時，所有句子合併為一個塊
        (0, ["句子0 句子1 句子2 句子3"]),
        # 相似度閾值為 1 時，句子各自成塊
        (1, ["句子0", "句子1", "句子2", "句子3"]),
    ],
)
def test_semantic_chunking(threshold, expected):
    """測試語義分塊器的分塊結果"""
    text = "第一句。第二句。第三句。第四句。"
    config = SemanticChunkingConfig(
        similarity_threshold=threshold,
        use_embedding_model=False,
        min_chunk_size=1,
    )
    chunker = SemanticChunking(config)
    chunks = chunker.chunk(text)
    assert [c.content for c in chunks] == expected
