"""
基礎分塊器
定義分塊器的接口和基本配置
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ChunkingConfig:
    """分塊配置基類"""
    chunk_size: int = 1000
    overlap_size: int = 200
    min_chunk_size: int = 100
    preserve_sentences: bool = True
    remove_empty_chunks: bool = True
    metadata_fields: List[str] = None

    def __post_init__(self):
        if self.metadata_fields is None:
            self.metadata_fields = ["source", "timestamp", "chunk_index"]

@dataclass
class Chunk:
    """文本塊數據結構"""
    content: str
    metadata: Dict[str, Any]
    index: int
    start_pos: int = 0
    end_pos: int = 0
    
    def __len__(self) -> int:
        return len(self.content)
    
    def is_empty(self) -> bool:
        return not self.content.strip()

class BaseChunker(ABC):
    """分塊器基類"""
    
    def __init__(self, config: ChunkingConfig = None):
        """
        初始化分塊器
        
        Args:
            config: 分塊配置
        """
        self.config = config or ChunkingConfig()
        self.stats = {
            "total_chunks": 0,
            "avg_chunk_size": 0,
            "min_chunk_size": float('inf'),
            "max_chunk_size": 0
        }
    
    @abstractmethod
    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        將文本分割成塊
        
        Args:
            text: 要分割的文本
            metadata: 額外的元數據
            
        Returns:
            List[Chunk]: 分割後的文本塊列表
        """
        pass
    
    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Chunk]:
        """
        批量處理文檔
        
        Args:
            documents: 文檔列表，每個文檔包含 'content' 和可選的元數據
            
        Returns:
            List[Chunk]: 所有文檔的分塊結果
        """
        all_chunks = []
        
        for doc_idx, doc in enumerate(documents):
            content = doc.get('content', '')
            doc_metadata = doc.get('metadata', {})
            doc_metadata.update({
                'document_index': doc_idx,
                'document_id': doc.get('id', f'doc_{doc_idx}')
            })
            
            chunks = self.chunk(content, doc_metadata)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def _post_process_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        後處理分塊結果
        
        Args:
            chunks: 原始分塊結果
            
        Returns:
            List[Chunk]: 處理後的分塊結果
        """
        processed_chunks = []
        
        for chunk in chunks:
            # 移除空塊
            if self.config.remove_empty_chunks and chunk.is_empty():
                continue
            
            # 檢查最小塊大小
            if len(chunk.content) < self.config.min_chunk_size:
                # 嘗試與前一個塊合併
                if processed_chunks and len(processed_chunks[-1].content) + len(chunk.content) <= self.config.chunk_size * 1.5:
                    last_chunk = processed_chunks[-1]
                    last_chunk.content += " " + chunk.content
                    last_chunk.end_pos = chunk.end_pos
                    last_chunk.metadata.update(chunk.metadata)
                    continue
            
            processed_chunks.append(chunk)
        
        # 更新統計信息
        self._update_stats(processed_chunks)
        
        return processed_chunks
    
    def _update_stats(self, chunks: List[Chunk]):
        """
        更新統計信息
        
        Args:
            chunks: 分塊結果
        """
        if not chunks:
            return
        
        chunk_sizes = [len(chunk.content) for chunk in chunks]
        
        self.stats.update({
            "total_chunks": len(chunks),
            "avg_chunk_size": sum(chunk_sizes) / len(chunks),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes)
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取分塊統計信息
        
        Returns:
            Dict[str, Any]: 統計信息
        """
        return self.stats.copy()
    
    def validate_config(self) -> bool:
        """
        驗證配置有效性
        
        Returns:
            bool: 配置是否有效
        """
        if self.config.chunk_size <= 0:
            logger.error("chunk_size 必須大於 0")
            return False
        
        if self.config.overlap_size < 0:
            logger.error("overlap_size 不能小於 0")
            return False
        
        if self.config.overlap_size >= self.config.chunk_size:
            logger.error("overlap_size 不能大於等於 chunk_size")
            return False
        
        if self.config.min_chunk_size <= 0:
            logger.error("min_chunk_size 必須大於 0")
            return False
        
        return True
    
    def reset_stats(self):
        """重置統計信息"""
        self.stats = {
            "total_chunks": 0,
            "avg_chunk_size": 0,
            "min_chunk_size": float('inf'),
            "max_chunk_size": 0
        }
