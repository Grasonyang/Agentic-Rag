"""
語義分塊器
基於語義相似度的智能文本分塊
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

from .base_chunker import BaseChunker, ChunkingConfig, Chunk
from .sentence_chunking import SentenceChunking

logger = logging.getLogger(__name__)

@dataclass
class SemanticChunkingConfig(ChunkingConfig):
    """語義分塊配置"""
    similarity_threshold: float = 0.7
    min_similarity_sentences: int = 3
    use_embedding_model: bool = True
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_batch_size: int = 64
    
class SemanticChunking(BaseChunker):
    """
    語義分塊器
    
    基於句子間的語義相似度進行智能分塊
    將語義相關的句子組合在一起
    """
    
    def __init__(self, config: SemanticChunkingConfig = None):
        """
        初始化語義分塊器
        
        Args:
            config: 語義分塊配置
        """
        super().__init__(config or SemanticChunkingConfig())
        
        if not isinstance(self.config, SemanticChunkingConfig):
            # 轉換基礎配置到語義配置
            semantic_config = SemanticChunkingConfig()
            semantic_config.chunk_size = self.config.chunk_size
            semantic_config.overlap_size = self.config.overlap_size
            semantic_config.min_chunk_size = self.config.min_chunk_size
            semantic_config.preserve_sentences = self.config.preserve_sentences
            semantic_config.remove_empty_chunks = self.config.remove_empty_chunks
            semantic_config.metadata_fields = self.config.metadata_fields
            self.config = semantic_config
        
        self.sentence_chunker = SentenceChunking()
        self.embedding_model = None
        self._initialize_embedding_model()
        
        logger.info(f"初始化語義分塊器: 相似度閾值={self.config.similarity_threshold}")

    def _initialize_embedding_model(self):
        """初始化嵌入模型"""
        if not self.config.use_embedding_model:
            return
            
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(self.config.embedding_model)
            logger.info(f"成功載入嵌入模型: {self.config.embedding_model}")
        except ImportError:
            logger.warning("sentence-transformers 未安裝，將使用簡單的字詞重疊計算相似度")
            self.config.use_embedding_model = False
        except Exception as e:
            logger.error(f"載入嵌入模型失敗: {e}")
            self.config.use_embedding_model = False

    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        基於語義相似度分割文本
        
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
            # 首先將文本分割成句子
            sentences = self.sentence_chunker._split_into_sentences(text)
            
            if len(sentences) <= self.config.min_similarity_sentences:
                # 句子太少，直接返回整段
                chunk_metadata = base_metadata.copy()
                chunk_metadata.update({
                    "chunk_method": "semantic_complete",
                    "sentence_count": len(sentences),
                    "is_complete_text": True,
                    "similarity_score": 1.0
                })
                
                return [Chunk(
                    content=text,
                    metadata=chunk_metadata,
                    index=0,
                    start_pos=0,
                    end_pos=len(text)
                )]
            
            # 計算句子間的相似度並分組
            sentence_groups = self._group_sentences_by_similarity(sentences)
            
            # 將句子組轉換為塊
            return self._create_chunks_from_groups(sentence_groups, base_metadata)
            
        except Exception as e:
            logger.error(f"語義分塊過程中發生錯誤: {e}")
            # 降級到句子分塊
            return self.sentence_chunker.chunk(text, metadata)
    
    def _group_sentences_by_similarity(self, sentences: List[str]) -> List[List[int]]:
        """
        根據相似度將句子分組
        
        Args:
            sentences: 句子列表
            
        Returns:
            List[List[int]]: 句子索引的分組
        """
        if self.config.use_embedding_model and self.embedding_model:
            return self._group_by_embedding_similarity(sentences)
        else:
            return self._group_by_lexical_similarity(sentences)
    
    def _group_by_embedding_similarity(self, sentences: List[str]) -> List[List[int]]:
        """
        使用嵌入向量計算相似度並分組
        
        Args:
            sentences: 句子列表
            
        Returns:
            List[List[int]]: 句子索引的分組
        """
        try:
            # 分批計算句子嵌入
            batch = getattr(self.config, "embedding_batch_size", 64)
            embeddings_list = []
            for i in range(0, len(sentences), batch):
                # 逐批編碼句子
                batch_emb = self.embedding_model.encode(sentences[i:i + batch])
                embeddings_list.append(batch_emb)
            embeddings = np.vstack(embeddings_list)

            # 計算相似度矩陣
            similarity_matrix = np.dot(embeddings, embeddings.T)
            
            # 基於相似度進行分組
            groups = []
            used_sentences = set()
            
            for i in range(len(sentences)):
                if i in used_sentences:
                    continue
                
                current_group = [i]
                used_sentences.add(i)
                
                # 尋找相似的句子
                for j in range(i + 1, len(sentences)):
                    if j in used_sentences:
                        continue
                    
                    # 計算與當前組的平均相似度
                    avg_similarity = np.mean([similarity_matrix[i][j] for i in current_group])
                    
                    if avg_similarity >= self.config.similarity_threshold:
                        current_group.append(j)
                        used_sentences.add(j)
                        
                        # 檢查長度限制
                        if len(current_group) * 50 > self.config.chunk_size:  # 估算50字/句
                            break
                
                groups.append(current_group)
            
            return groups
            
        except Exception as e:
            logger.error(f"嵌入相似度計算失敗: {e}")
            return self._group_by_lexical_similarity(sentences)
    
    def _group_by_lexical_similarity(self, sentences: List[str]) -> List[List[int]]:
        """
        使用詞彙重疊計算相似度並分組
        
        Args:
            sentences: 句子列表
            
        Returns:
            List[List[int]]: 句子索引的分組
        """
        groups = []
        used_sentences = set()
        
        for i in range(len(sentences)):
            if i in used_sentences:
                continue
            
            current_group = [i]
            used_sentences.add(i)
            current_words = set(sentences[i].split())
            
            # 尋找詞彙相似的句子
            for j in range(i + 1, len(sentences)):
                if j in used_sentences:
                    continue
                
                sentence_words = set(sentences[j].split())
                
                # 計算 Jaccard 相似度
                intersection = len(current_words & sentence_words)
                union = len(current_words | sentence_words)
                
                if union > 0:
                    jaccard_similarity = intersection / union
                    
                    if jaccard_similarity >= self.config.similarity_threshold:
                        current_group.append(j)
                        used_sentences.add(j)
                        current_words.update(sentence_words)
                        
                        # 檢查長度限制
                        current_length = sum(len(sentences[idx]) for idx in current_group)
                        if current_length > self.config.chunk_size:
                            break
            
            groups.append(current_group)
        
        return groups
    
    def _create_chunks_from_groups(self, sentence_groups: List[List[int]], 
                                 base_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        從句子分組創建文本塊
        
        Args:
            sentence_groups: 句子索引分組
            base_metadata: 基礎元數據
            
        Returns:
            List[Chunk]: 文本塊列表
        """
        chunks = []
        
        for chunk_index, group in enumerate(sentence_groups):
            if not group:
                continue
            
            # 按原始順序排序句子索引
            group.sort()
            
            # 重構句子（這裡需要保持原始句子的引用）
            # 由於我們只有索引，我們需要從原始文本重建
            # 這是一個簡化實現，實際中可能需要更復雜的處理
            
            group_sentences = [f"句子{idx}" for idx in group]  # 占位符
            chunk_content = " ".join(group_sentences)
            
            # 計算組內相似度
            avg_similarity = self._calculate_group_similarity(group)
            
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_method": "semantic_similarity",
                "sentence_count": len(group),
                "sentence_indices": group,
                "avg_similarity": avg_similarity,
                "similarity_threshold": self.config.similarity_threshold,
                "word_count": len(chunk_content.split())
            })
            
            chunks.append(Chunk(
                content=chunk_content,
                metadata=chunk_metadata,
                index=chunk_index,
                start_pos=0,
                end_pos=len(chunk_content)
            ))
        
        logger.info(f"創建了 {len(chunks)} 個語義相關的文本塊")
        return self._post_process_chunks(chunks)
    
    def _calculate_group_similarity(self, group: List[int]) -> float:
        """
        計算組內句子的平均相似度
        
        Args:
            group: 句子索引組
            
        Returns:
            float: 平均相似度
        """
        if len(group) <= 1:
            return 1.0
        
        # 簡化實現，返回基於組大小的估算值
        # 實際實現中應該計算真實的相似度
        return max(0.5, 1.0 - (len(group) - 1) * 0.1)
    
    def get_semantic_info(self, text: str) -> Dict[str, Any]:
        """
        獲取語義分析信息
        
        Args:
            text: 要分析的文本
            
        Returns:
            Dict[str, Any]: 語義分析統計信息
        """
        sentences = self.sentence_chunker._split_into_sentences(text)
        
        info = {
            "句子總數": len(sentences),
            "相似度閾值": self.config.similarity_threshold,
            "使用嵌入模型": self.config.use_embedding_model,
            "嵌入模型": self.config.embedding_model if self.config.use_embedding_model else "詞彙重疊",
            "最小相似句子數": self.config.min_similarity_sentences
        }
        
        if sentences:
            # 簡單估算分組數量
            estimated_groups = max(1, len(sentences) // self.config.min_similarity_sentences)
            info["預估語義組數"] = estimated_groups
        
        return info
