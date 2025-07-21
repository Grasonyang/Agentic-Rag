"""
句子分塊器
基於句子邊界的智能文本分塊
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .base_chunker import BaseChunker, ChunkingConfig, Chunk

logger = logging.getLogger(__name__)

@dataclass
class SentenceChunkingConfig(ChunkingConfig):
    """句子分塊配置"""
    max_sentences_per_chunk: int = 10
    min_sentences_per_chunk: int = 2
    sentence_overlap: int = 1
    respect_paragraph_breaks: bool = True
    language: str = "zh"  # 支持 "zh", "en"

class SentenceChunking(BaseChunker):
    """
    句子分塊器
    
    基於句子邊界進行文本分塊，保持語義完整性
    """
    
    def __init__(self, config: SentenceChunkingConfig = None):
        """
        初始化句子分塊器
        
        Args:
            config: 句子分塊配置
        """
        super().__init__(config or SentenceChunkingConfig())
        
        if not isinstance(self.config, SentenceChunkingConfig):
            # 轉換基礎配置到句子配置
            sentence_config = SentenceChunkingConfig()
            sentence_config.chunk_size = self.config.chunk_size
            sentence_config.overlap_size = self.config.overlap_size
            sentence_config.min_chunk_size = self.config.min_chunk_size
            sentence_config.preserve_sentences = self.config.preserve_sentences
            sentence_config.remove_empty_chunks = self.config.remove_empty_chunks
            sentence_config.metadata_fields = self.config.metadata_fields
            self.config = sentence_config
        
        # 根據語言設置句子分割模式
        if self.config.language == "zh":
            self.sentence_pattern = r'[。！？；]+(?=\s|$|[^。！？；])'
        else:  # 英文
            self.sentence_pattern = r'[.!?]+(?=\s|$|[^.!?])'
        
        logger.info(f"初始化句子分塊器: 語言={self.config.language}, 最大句子數={self.config.max_sentences_per_chunk}")

    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        將文本分割成基於句子的塊
        
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
            if self.config.respect_paragraph_breaks:
                return self._chunk_with_paragraphs(text, base_metadata)
            else:
                return self._chunk_by_sentences_only(text, base_metadata)
                
        except Exception as e:
            logger.error(f"句子分塊過程中發生錯誤: {e}")
            return []
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        將文本分割成句子
        
        Args:
            text: 要分割的文本
            
        Returns:
            List[str]: 句子列表
        """
        # 使用正則表達式分割句子
        sentences = re.split(self.sentence_pattern, text)
        
        # 清理和過濾句子
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                # 移除多餘的空格
                sentence = re.sub(r'\s+', ' ', sentence)
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def _chunk_by_sentences_only(self, text: str, base_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        僅基於句子進行分塊
        
        Args:
            text: 要分割的文本
            base_metadata: 基礎元數據
            
        Returns:
            List[Chunk]: 分塊結果
        """
        sentences = self._split_into_sentences(text)
        
        if not sentences:
            return []
        
        if len(sentences) <= self.config.max_sentences_per_chunk:
            # 句子數不多，返回單個塊
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "sentence_complete",
                "sentence_count": len(sentences),
                "is_complete_text": True
            })
            
            return [Chunk(
                content=text,
                metadata=chunk_metadata,
                index=0,
                start_pos=0,
                end_pos=len(text)
            )]
        
        chunks = []
        chunk_index = 0
        i = 0
        
        while i < len(sentences):
            current_sentences = []
            current_length = 0
            start_sentence_idx = i
            
            # 收集句子直到達到最大數量或長度限制
            while (i < len(sentences) and 
                   len(current_sentences) < self.config.max_sentences_per_chunk and
                   current_length < self.config.chunk_size):
                
                sentence = sentences[i]
                current_sentences.append(sentence)
                current_length += len(sentence)
                i += 1
            
            if not current_sentences:
                break
            
            # 確保最少句子數
            if len(current_sentences) < self.config.min_sentences_per_chunk and i < len(sentences):
                # 嘗試添加更多句子
                while (i < len(sentences) and 
                       len(current_sentences) < self.config.min_sentences_per_chunk):
                    current_sentences.append(sentences[i])
                    i += 1
            
            chunk_content = self._join_sentences(current_sentences)
            
            # 處理重疊
            if chunk_index > 0 and self.config.sentence_overlap > 0:
                # 回退以創建重疊
                overlap_size = min(self.config.sentence_overlap, len(current_sentences) - 1)
                i = start_sentence_idx + len(current_sentences) - overlap_size
            
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "sentence_based",
                "sentence_count": len(current_sentences),
                "word_count": len(chunk_content.split()),
                "sentence_start_index": start_sentence_idx,
                "sentence_end_index": start_sentence_idx + len(current_sentences),
                "has_overlap": chunk_index > 0 and self.config.sentence_overlap > 0,
                "overlap_sentences": self.config.sentence_overlap if chunk_index > 0 else 0
            })
            
            chunks.append(Chunk(
                content=chunk_content,
                metadata=chunk_metadata,
                index=chunk_index,
                start_pos=0,  # 句子模式下位置計算較複雜
                end_pos=len(chunk_content)
            ))
            
            chunk_index += 1
        
        logger.info(f"成功分割文本: {len(sentences)} 個句子 -> {len(chunks)} 個塊")
        return self._post_process_chunks(chunks)
    
    def _chunk_with_paragraphs(self, text: str, base_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        考慮段落邊界的分塊
        
        Args:
            text: 要分割的文本
            base_metadata: 基礎元數據
            
        Returns:
            List[Chunk]: 分塊結果
        """
        # 按段落分割
        paragraphs = text.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if not paragraphs:
            return self._chunk_by_sentences_only(text, base_metadata)
        
        chunks = []
        chunk_index = 0
        
        for para_idx, paragraph in enumerate(paragraphs):
            para_sentences = self._split_into_sentences(paragraph)
            
            if not para_sentences:
                continue
            
            # 如果段落較短，嘗試與其他段落合併
            if len(para_sentences) < self.config.min_sentences_per_chunk:
                # 尋找可以合併的段落
                combined_paragraphs = [paragraph]
                combined_sentences = para_sentences.copy()
                
                # 向前尋找
                for next_idx in range(para_idx + 1, len(paragraphs)):
                    next_para = paragraphs[next_idx]
                    next_sentences = self._split_into_sentences(next_para)
                    
                    if (len(combined_sentences) + len(next_sentences) <= self.config.max_sentences_per_chunk):
                        combined_paragraphs.append(next_para)
                        combined_sentences.extend(next_sentences)
                    else:
                        break
                
                if len(combined_sentences) >= self.config.min_sentences_per_chunk:
                    chunk_content = '\n\n'.join(combined_paragraphs)
                    
                    chunk_metadata = base_metadata.copy()
                    chunk_metadata.update({
                        "chunk_method": "paragraph_combined",
                        "paragraph_count": len(combined_paragraphs),
                        "sentence_count": len(combined_sentences),
                        "word_count": len(chunk_content.split()),
                        "paragraph_start_index": para_idx,
                        "paragraph_end_index": para_idx + len(combined_paragraphs)
                    })
                    
                    chunks.append(Chunk(
                        content=chunk_content,
                        metadata=chunk_metadata,
                        index=chunk_index,
                        start_pos=0,
                        end_pos=len(chunk_content)
                    ))
                    
                    chunk_index += 1
                    continue
            
            # 段落足夠大，按句子分塊
            para_chunks = self._chunk_paragraph_by_sentences(
                paragraph, para_sentences, base_metadata, para_idx, chunk_index
            )
            
            chunks.extend(para_chunks)
            chunk_index += len(para_chunks)
        
        logger.info(f"成功分割文本: {len(paragraphs)} 個段落 -> {len(chunks)} 個塊")
        return self._post_process_chunks(chunks)
    
    def _chunk_paragraph_by_sentences(self, paragraph: str, sentences: List[str],
                                    base_metadata: Dict[str, Any], para_idx: int,
                                    start_chunk_idx: int) -> List[Chunk]:
        """
        將單個段落按句子分塊
        
        Args:
            paragraph: 段落文本
            sentences: 句子列表
            base_metadata: 基礎元數據
            para_idx: 段落索引
            start_chunk_idx: 起始塊索引
            
        Returns:
            List[Chunk]: 分塊結果
        """
        if len(sentences) <= self.config.max_sentences_per_chunk:
            # 段落不大，作為單個塊
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "paragraph_complete",
                "paragraph_index": para_idx,
                "sentence_count": len(sentences),
                "word_count": len(paragraph.split()),
                "is_complete_paragraph": True
            })
            
            return [Chunk(
                content=paragraph,
                metadata=chunk_metadata,
                index=start_chunk_idx,
                start_pos=0,
                end_pos=len(paragraph)
            )]
        
        # 段落較大，需要分塊
        chunks = []
        chunk_index = start_chunk_idx
        i = 0
        
        while i < len(sentences):
            current_sentences = sentences[i:i + self.config.max_sentences_per_chunk]
            chunk_content = self._join_sentences(current_sentences)
            
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "paragraph_sentence_split",
                "paragraph_index": para_idx,
                "sentence_count": len(current_sentences),
                "word_count": len(chunk_content.split()),
                "sentence_start_index": i,
                "sentence_end_index": i + len(current_sentences),
                "is_paragraph_part": True
            })
            
            chunks.append(Chunk(
                content=chunk_content,
                metadata=chunk_metadata,
                index=chunk_index,
                start_pos=0,
                end_pos=len(chunk_content)
            ))
            
            # 移動到下一組句子，考慮重疊
            i += self.config.max_sentences_per_chunk - self.config.sentence_overlap
            chunk_index += 1
        
        return chunks
    
    def _join_sentences(self, sentences: List[str]) -> str:
        """
        連接句子
        
        Args:
            sentences: 句子列表
            
        Returns:
            str: 連接後的文本
        """
        if self.config.language == "zh":
            # 中文句子間不需要空格
            return ''.join(sentences)
        else:
            # 英文句子間需要空格
            return ' '.join(sentences)
    
    def get_sentence_info(self, text: str) -> Dict[str, Any]:
        """
        獲取句子信息
        
        Args:
            text: 要分析的文本
            
        Returns:
            Dict[str, Any]: 句子統計信息
        """
        sentences = self._split_into_sentences(text)
        paragraphs = text.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            estimated_chunks = max(1, len(sentences) // self.config.max_sentences_per_chunk)
        else:
            avg_sentence_length = 0
            estimated_chunks = 0
        
        return {
            "句子總數": len(sentences),
            "段落數": len(paragraphs),
            "平均句子長度": round(avg_sentence_length, 2),
            "預估分塊數量": estimated_chunks,
            "最大句子每塊": self.config.max_sentences_per_chunk,
            "最小句子每塊": self.config.min_sentences_per_chunk,
            "句子重疊數": self.config.sentence_overlap,
            "語言": self.config.language
        }
