import os
import logging
from typing import List, Union
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import torch
import numpy as np

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 從環境變數獲取模型名稱
model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

try:
    model = SentenceTransformer(model_name)
    logger.info(f"模型 '{model_name}' 載入成功")
except Exception as e:
    logger.error(f"模型載入失敗: {e}")
    model = None

class EmbeddingManager:
    """嵌入模型管理器"""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name
        self.model = model  # 使用已載入的全局模型
        
    def get_embedding(self, text: str) -> np.ndarray:
        """獲取單個文本的嵌入向量"""
        if self.model is None:
            logger.error("模型未載入")
            return None
            
        try:
            embedding = self.model.encode([text])
            return embedding[0]
        except Exception as e:
            logger.error(f"生成嵌入失敗: {e}")
            return None
    
    def get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """獲取多個文本的嵌入向量"""
        if self.model is None:
            logger.error("模型未載入")
            return [None] * len(texts)
            
        try:
            embeddings = self.model.encode(texts)
            return [emb for emb in embeddings]
        except Exception as e:
            logger.error(f"批量生成嵌入失敗: {e}")
            return [None] * len(texts)
    
    def calculate_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """計算兩個嵌入向量的餘弦相似度"""
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            return cosine_similarity([emb1], [emb2])[0][0]
        except Exception as e:
            logger.error(f"計算相似度失敗: {e}")
            return 0.0
    
    def get_dimension(self) -> int:
        """獲取嵌入向量維度"""
        if self.model is None:
            return 0
        try:
            return self.model.get_sentence_embedding_dimension()
        except Exception as e:
            logger.error(f"獲取維度失敗: {e}")
            return 0

def embed_text(texts: Union[str, List[str]]) -> Union[torch.Tensor, None]:
    """
    使用 BGE 模型對文本進行嵌入
    
    Args:
        texts: 要嵌入的文本，可以是單個字符串或字符串列表
        
    Returns:
        torch.Tensor: 對應輸入文本的嵌入向量，失敗時返回 None
    """
    if model is None:
        logger.error("模型未載入，無法進行嵌入")
        return None
        
    try:
        # 確保輸入是列表格式
        if isinstance(texts, str):
            texts = [texts]
            
        embeddings = model.encode(texts, convert_to_tensor=True)
        logger.info(f"成功生成 {len(texts)} 個文本的嵌入向量")
        return embeddings
    except Exception as e:
        logger.error(f"文本嵌入過程中發生錯誤: {e}")
        return None

def get_embedding_dimension() -> int:
    """
    獲取嵌入向量的維度
    
    Returns:
        int: 嵌入向量維度，失敗時返回 0
    """
    if model is None:
        return 0
    try:
        return model.get_sentence_embedding_dimension()
    except Exception as e:
        logger.error(f"獲取嵌入維度時發生錯誤: {e}")
        return 0

if __name__ == "__main__":
    sample_texts = [
        "這是一個測試文本。",
        "BGE模型可以用來生成文本嵌入。",
        "這些嵌入可以用於各種自然語言處理任務。"
    ]
    
    # 測試嵌入功能
    embeddings = embed_text(sample_texts)
    if embeddings is not None:
        logger.info("範例嵌入向量生成成功")
        logger.info(f"嵌入向量形狀: {embeddings.shape}")
        logger.info(f"嵌入向量維度: {get_embedding_dimension()}")
        print("前10個向量值:", embeddings[0][:10].tolist())
    else:
        logger.error("範例嵌入向量生成失敗")