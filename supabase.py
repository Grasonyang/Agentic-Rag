import httpx
from embedding import embed_text
from chunking import SlidingWindowChunking
from uuid import uuid4
import datetime

SUPABASE_URL = "http://localhost:8000/rest/v1"
# SUPABASE_API_KEY = "your-supabase-service-role-key"

# Supabase 查詢封裝
async def url_exists_in_db(session: httpx.AsyncClient, url: str) -> bool:
    r = await session.get(
        f"{SUPABASE_URL}/articles",
        params={"select": "id", "url": f"eq.{url}"},
        # headers={"apikey": SUPABASE_API_KEY}
    )
    if r.status_code != 200:
        print(f"Error checking URL in database: {r.status_code} - {r.text}")
        return False
    if r.json() is None:
        print(f"Error: No response from database for URL check: {url}")
        return False
    if not isinstance(r.json(), list):
        print(f"Error: Unexpected response format for URL check: {r.json()}")
        return False
    # 檢查是否有資料
    if not r.json():
        print(f"No existing article found for URL: {url}")
        return False
    print(f"Existing article found for URL: {url}")
    # 如果有資料，返回 True
    print(f"Found {len(r.json())} articles for URL: {url}")
    return True

# 儲存爬回資料（簡版，只存 articles）
async def insert_article(session, url, title, content_md, metadata):
    article_id = str(uuid4())

    await session.post(
        f"{SUPABASE_URL}/articles",
        json={
            "id": article_id,
            "url": url,
            "title": title,
            "content_md": content_md,
            "metadata": metadata,
        },
        # headers={"apikey": SUPABASE_API_KEY, "Content-Type": "application/json"}
        headers={"Content-Type": "application/json"}
    )
    return article_id

async def insert_chunks(session, article_id, markdown_text):
    chunker = SlidingWindowChunking(window_size=200, step=100)
    chunks = chunker.chunk(markdown_text)
    embeddings = embed_text(chunks)

    for idx, (chunk_text, embedding_vector) in enumerate(zip(chunks, embeddings.tolist())):
        await session.post(
            f"{SUPABASE_URL}/article_chunks",
            json={
                "id": str(uuid4()),
                "article_id": article_id,
                "chunk_idx": idx,
                "chunk_text": chunk_text,
                "embedding": embedding_vector,
                "created_at": datetime.datetime.utcnow().isoformat()
            },
            headers={"Content-Type": "application/json"}
        )


if __name__ == "__main__":
    import asyncio

    async def main():
        async with httpx.AsyncClient() as session:
            url = "https://example.com/article"
            title = "Example Article"
            content_md = "# Example\nThis is an example article."
            metadata = {"author": "John Doe", "date": "2023-10-01"}
            print("OK1")
            if not await url_exists_in_db(session, url):
                article_id = await insert_article(session, url, title, content_md, metadata)
                print("OK2")
                await insert_chunks(session, article_id, content_md)
                print("OK3")
                print(f"Article '{title}' inserted with ID: {article_id}")
            else:
                print(f"Article already exists for URL: {url}")

    asyncio.run(main())