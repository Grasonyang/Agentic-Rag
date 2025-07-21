"""
滑動窗口分塊器
基於滑動窗口的文本分塊實現
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .base_chunker import BaseChunker, ChunkingConfig, Chunk

logger = logging.getLogger(__name__)

@dataclass
class SlidingWindowConfig(ChunkingConfig):
    """滑動窗口配置"""
    window_size: int = 100  # 窗口大小（單詞數）
    step_size: int = 50     # 步長（單詞數）
    use_sentences: bool = True  # 是否嘗試保持句子完整性

class SlidingWindowChunking(BaseChunker):
    """
    滑動窗口文本分塊器
    
    使用滑動窗口技術將長文本分割成重疊的塊，
    確保語義連續性和上下文保持。
    """
    
    def __init__(self, config: SlidingWindowConfig = None):
        """
        初始化滑動窗口分塊器
        
        Args:
            config: 滑動窗口配置
        """
        super().__init__(config or SlidingWindowConfig())
        
        if not isinstance(self.config, SlidingWindowConfig):
            # 如果傳入的是基礎配置，轉換為滑動窗口配置
            window_config = SlidingWindowConfig()
            window_config.chunk_size = self.config.chunk_size
            window_config.overlap_size = self.config.overlap_size
            window_config.min_chunk_size = self.config.min_chunk_size
            window_config.preserve_sentences = self.config.preserve_sentences
            window_config.remove_empty_chunks = self.config.remove_empty_chunks
            window_config.metadata_fields = self.config.metadata_fields
            self.config = window_config
        
        logger.info(f"初始化滑動窗口分塊器: window_size={self.config.window_size}, step_size={self.config.step_size}")

    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        將文本分割成塊
        
        Args:
            text: 要分割的文本
            metadata: 額外的元數據
            
        Returns:
            List[Chunk]: 分割後的文本塊列表
        """
        if not text or not text.strip():
            logger.warning("輸入文本為空")
            return []
        
        if not self.validate_config():
            logger.error("配置驗證失敗")
            return []
        
        base_metadata = metadata or {}
        
        try:
            if self.config.use_sentences:
                return self._chunk_by_sentences(text, base_metadata)
            else:
                return self._chunk_by_words(text, base_metadata)
                
        except Exception as e:
            logger.error(f"文本分塊過程中發生錯誤: {e}")
            return []
    
    def _chunk_by_words(self, text: str, base_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        基於單詞的分塊
        
        Args:
            text: 要分割的文本
            base_metadata: 基礎元數據
            
        Returns:
            List[Chunk]: 分塊結果
        """
        words = text.split()
        chunks = []
        
        if len(words) <= self.config.window_size:
            logger.info(f"文本長度 {len(words)} 小於窗口大小 {self.config.window_size}，返回原文本")
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "sliding_window_words",
                "word_count": len(words),
                "is_complete_text": True
            })
            
            return [Chunk(
                content=text,
                metadata=chunk_metadata,
                index=0,
                start_pos=0,
                end_pos=len(text)
            )]
        
        chunk_index = 0
        for i in range(0, len(words) - self.config.window_size + 1, self.config.step_size):
            chunk_words = words[i:i + self.config.window_size]
            chunk_content = ' '.join(chunk_words)
            
            # 計算字符位置
            start_words = words[:i]
            start_pos = len(' '.join(start_words)) + (1 if start_words else 0)
            end_pos = start_pos + len(chunk_content)
            
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "sliding_window_words",
                "word_count": len(chunk_words),
                "word_start_index": i,
                "word_end_index": i + self.config.window_size,
                "overlap_with_previous": i > 0,
                "overlap_with_next": i + self.config.window_size < len(words)
            })
            
            chunks.append(Chunk(
                content=chunk_content,
                metadata=chunk_metadata,
                index=chunk_index,
                start_pos=start_pos,
                end_pos=end_pos
            ))
            
            chunk_index += 1
        
        # 確保最後一段不被遺漏
        remaining_words = len(words) % self.config.step_size
        if remaining_words != 0 and len(words) > self.config.window_size:
            last_chunk_words = words[-self.config.window_size:]
            last_chunk_content = ' '.join(last_chunk_words)
            
            # 檢查是否與最後一個塊重複
            if not chunks or chunks[-1].content != last_chunk_content:
                start_words = words[:-self.config.window_size]
                start_pos = len(' '.join(start_words)) + (1 if start_words else 0)
                
                chunk_metadata = base_metadata.copy()
                chunk_metadata.update({
                    "chunk_method": "sliding_window_words",
                    "word_count": len(last_chunk_words),
                    "is_final_chunk": True,
                    "word_start_index": len(words) - self.config.window_size,
                    "word_end_index": len(words)
                })
                
                chunks.append(Chunk(
                    content=last_chunk_content,
                    metadata=chunk_metadata,
                    index=chunk_index,
                    start_pos=start_pos,
                    end_pos=len(text)
                ))
        
        logger.info(f"成功分割文本: {len(words)} 個單詞 -> {len(chunks)} 個塊")
        return self._post_process_chunks(chunks)
    
    def _chunk_by_sentences(self, text: str, base_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        基於句子的分塊
        
        Args:
            text: 要分割的文本
            base_metadata: 基礎元數據
            
        Returns:
            List[Chunk]: 分塊結果
        """
        # 簡單的句子分割（可以使用更複雜的 NLP 工具）
        import re
        sentences = re.split(r'[.!?。！？]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return []
        
        chunks = []
        chunk_index = 0
        
        # 估算每個句子的單詞數
        sentence_word_counts = [len(sentence.split()) for sentence in sentences]
        
        i = 0
        while i < len(sentences):
            current_sentences = []
            current_word_count = 0
            start_sentence_idx = i
            
            # 收集句子直到達到目標單詞數
            while i < len(sentences) and current_word_count < self.config.window_size:
                current_sentences.append(sentences[i])
                current_word_count += sentence_word_counts[i]
                i += 1
            
            if not current_sentences:
                break
            
            chunk_content = '. '.join(current_sentences)
            if not chunk_content.endswith('.'):
                chunk_content += '.'
            
            # 計算重疊
            if chunk_index > 0 and self.config.step_size < len(current_sentences):
                # 回退以創建重疊
                overlap_sentences = max(1, len(current_sentences) - self.config.step_size)
                i = start_sentence_idx + self.config.step_size
            
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "sliding_window_sentences",
                "sentence_count": len(current_sentences),
                "word_count": current_word_count,
                "sentence_start_index": start_sentence_idx,
                "sentence_end_index": start_sentence_idx + len(current_sentences),
                "overlap_with_previous": chunk_index > 0,
                "overlap_with_next": i < len(sentences)
            })
            
            chunks.append(Chunk(
                content=chunk_content,
                metadata=chunk_metadata,
                index=chunk_index,
                start_pos=0,  # 句子模式下位置計算較複雜，暫時設為0
                end_pos=len(chunk_content)
            ))
            
            chunk_index += 1
        
        logger.info(f"成功分割文本: {len(sentences)} 個句子 -> {len(chunks)} 個塊")
        return self._post_process_chunks(chunks)
    
    def get_chunk_info(self, text: str) -> Dict[str, Any]:
        """
        獲取分塊信息（不實際分塊）
        
        Args:
            text: 要分析的文本
            
        Returns:
            Dict[str, Any]: 包含分塊統計信息的字典
        """
        words = text.split()
        sentences = len([s for s in text.split('.') if s.strip()])
        
        estimated_chunks = max(1, (len(words) - self.config.window_size) // self.config.step_size + 1)
        
        return {
            "原始單詞數": len(words),
            "句子數": sentences,
            "預估分塊數量": estimated_chunks,
            "窗口大小": self.config.window_size,
            "步長": self.config.step_size,
            "使用句子分割": self.config.use_sentences,
            "預估平均塊長度": self.config.window_size
        }
