"""簡易的 RAG API 伺服器"""

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from .dependencies import get_db, get_a2a_client
from embedding.embedding import embed_text

app = FastAPI()


class QueryRequest(BaseModel):
    """使用者查詢資料模型"""

    question: str


@app.post("/rag/query")
async def rag_query(req: QueryRequest, db=Depends(get_db), model=Depends(get_a2a_client)):
    """處理 RAG 查詢"""
    # 1. 生成問題的嵌入向量
    embedding_tensor = embed_text(req.question)
    if embedding_tensor is None:
        raise HTTPException(status_code=500, detail="無法生成嵌入向量")
    embedding = embedding_tensor[0].tolist()

    # 2. 從資料庫搜尋相似內容
    sql = (
        """
        SELECT ac.content AS chunk_content, a.url AS article_url, a.title AS article_title
        FROM article_chunks ac
        JOIN articles a ON ac.article_id = a.id
        ORDER BY ac.embedding <=> %s
        LIMIT 5
        """
    )
    rows = db.client.execute_query(sql, (embedding,))
    if not rows:
        raise HTTPException(status_code=404, detail="找不到相關內容")

    context = "\n".join(row["chunk_content"] for row in rows)

    # 3. 呼叫 Google A2A 生成回答
    prompt = f"請根據以下內容回答問題：{req.question}\n\n{context}"
    try:
        result = model.generate_content(prompt)
        answer = result.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google A2A 呼叫失敗: {e}")

    sources = [row["article_url"] for row in rows]
    return {"answer": answer, "sources": sources}
