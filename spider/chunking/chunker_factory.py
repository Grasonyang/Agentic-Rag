"""
分塊器工廠
提供統一的分塊器創建接口
"""

import logging
from typing import Dict, Any, Optional, Type, List
from enum import Enum

from .base_chunker import BaseChunker, ChunkingConfig
from .sliding_window import SlidingWindowChunking, SlidingWindowConfig
from .sentence_chunking import SentenceChunking, SentenceChunkingConfig
from .semantic_chunking import SemanticChunking, SemanticChunkingConfig

logger = logging.getLogger(__name__)

class ChunkerType(Enum):
    """分塊器類型枚舉"""
    SLIDING_WINDOW = "sliding_window"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"

class ChunkerFactory:
    """分塊器工廠類"""
    
    # 註冊的分塊器類型
    _chunkers: Dict[ChunkerType, Type[BaseChunker]] = {
        ChunkerType.SLIDING_WINDOW: SlidingWindowChunking,
        ChunkerType.SENTENCE: SentenceChunking,
        ChunkerType.SEMANTIC: SemanticChunking
    }
    
    # 對應的配置類型
    _configs: Dict[ChunkerType, Type[ChunkingConfig]] = {
        ChunkerType.SLIDING_WINDOW: SlidingWindowConfig,
        ChunkerType.SENTENCE: SentenceChunkingConfig,
        ChunkerType.SEMANTIC: SemanticChunkingConfig
    }
    
    @classmethod
    def create_chunker(cls, chunker_type: str, config: Dict[str, Any] = None) -> BaseChunker:
        """
        創建分塊器實例
        
        Args:
            chunker_type: 分塊器類型字符串
            config: 配置字典
            
        Returns:
            BaseChunker: 分塊器實例
            
        Raises:
            ValueError: 未知的分塊器類型
        """
        try:
            chunk_type = ChunkerType(chunker_type.lower())
        except ValueError:
            raise ValueError(f"未支持的分塊器類型: {chunker_type}. "
                           f"支持的類型: {[t.value for t in ChunkerType]}")
        
        chunker_class = cls._chunkers[chunk_type]
        config_class = cls._configs[chunk_type]
        
        # 創建配置實例
        if config:
            chunker_config = config_class(**config)
        else:
            chunker_config = config_class()
        
        # 創建分塊器實例
        chunker = chunker_class(chunker_config)
        
        logger.info(f"創建了 {chunker_type} 分塊器實例")
        return chunker
    
    @classmethod
    def create_sliding_window_chunker(cls, window_size: int = 100, 
                                    step_size: int = 50,
                                    use_sentences: bool = True,
                                    **kwargs) -> SlidingWindowChunking:
        """
        創建滑動窗口分塊器
        
        Args:
            window_size: 窗口大小
            step_size: 步長
            use_sentences: 是否使用句子
            **kwargs: 其他配置參數
            
        Returns:
            SlidingWindowChunking: 滑動窗口分塊器
        """
        config = SlidingWindowConfig(
            window_size=window_size,
            step_size=step_size,
            use_sentences=use_sentences,
            **kwargs
        )
        return SlidingWindowChunking(config)
    
    @classmethod
    def create_sentence_chunker(cls, max_sentences_per_chunk: int = 10,
                              min_sentences_per_chunk: int = 2,
                              sentence_overlap: int = 1,
                              language: str = "zh",
                              **kwargs) -> SentenceChunking:
        """
        創建句子分塊器
        
        Args:
            max_sentences_per_chunk: 每塊最大句子數
            min_sentences_per_chunk: 每塊最小句子數
            sentence_overlap: 句子重疊數
            language: 語言
            **kwargs: 其他配置參數
            
        Returns:
            SentenceChunking: 句子分塊器
        """
        config = SentenceChunkingConfig(
            max_sentences_per_chunk=max_sentences_per_chunk,
            min_sentences_per_chunk=min_sentences_per_chunk,
            sentence_overlap=sentence_overlap,
            language=language,
            **kwargs
        )
        return SentenceChunking(config)
    
    @classmethod
    def create_semantic_chunker(cls, similarity_threshold: float = 0.7,
                              use_embedding_model: bool = True,
                              embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                              **kwargs) -> SemanticChunking:
        """
        創建語義分塊器
        
        Args:
            similarity_threshold: 相似度閾值
            use_embedding_model: 是否使用嵌入模型
            embedding_model: 嵌入模型名稱
            **kwargs: 其他配置參數
            
        Returns:
            SemanticChunking: 語義分塊器
        """
        config = SemanticChunkingConfig(
            similarity_threshold=similarity_threshold,
            use_embedding_model=use_embedding_model,
            embedding_model=embedding_model,
            **kwargs
        )
        return SemanticChunking(config)
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """
        獲取支持的分塊器類型
        
        Returns:
            List[str]: 支持的類型列表
        """
        return [t.value for t in ChunkerType]
    
    @classmethod
    def get_chunker_info(cls, chunker_type: str) -> Dict[str, Any]:
        """
        獲取分塊器信息
        
        Args:
            chunker_type: 分塊器類型
            
        Returns:
            Dict[str, Any]: 分塊器信息
        """
        try:
            chunk_type = ChunkerType(chunker_type.lower())
        except ValueError:
            return {"error": f"未知的分塊器類型: {chunker_type}"}
        
        chunker_class = cls._chunkers[chunk_type]
        config_class = cls._configs[chunk_type]
        
        return {
            "type": chunker_type,
            "class": chunker_class.__name__,
            "config_class": config_class.__name__,
            "description": chunker_class.__doc__.strip() if chunker_class.__doc__ else "無描述",
            "config_fields": list(config_class.__annotations__.keys()) if hasattr(config_class, '__annotations__') else []
        }
    
    @classmethod
    def register_chunker(cls, chunker_type: str, 
                        chunker_class: Type[BaseChunker],
                        config_class: Type[ChunkingConfig]):
        """
        註冊自定義分塊器
        
        Args:
            chunker_type: 分塊器類型字符串
            chunker_class: 分塊器類
            config_class: 配置類
        """
        try:
            chunk_type = ChunkerType(chunker_type.lower())
            logger.warning(f"分塊器類型 {chunker_type} 已存在，將被覆蓋")
        except ValueError:
            # 創建新的枚舉值（注意：這在運行時添加枚舉值是不推薦的做法）
            logger.info(f"註冊新的分塊器類型: {chunker_type}")
        
        # 簡單的字符串鍵註冊（避免動態枚舉的複雜性）
        cls._chunkers[chunker_type] = chunker_class
        cls._configs[chunker_type] = config_class
        
        logger.info(f"成功註冊分塊器: {chunker_type}")

# 便捷函數
def create_chunker(chunker_type: str, **config) -> BaseChunker:
    """
    便捷函數：創建分塊器
    
    Args:
        chunker_type: 分塊器類型
        **config: 配置參數
        
    Returns:
        BaseChunker: 分塊器實例
    """
    return ChunkerFactory.create_chunker(chunker_type, config)

def get_available_chunkers() -> List[str]:
    """
    便捷函數：獲取可用的分塊器類型
    
    Returns:
        List[str]: 可用類型列表
    """
    return ChunkerFactory.get_supported_types()
