import os
import uuid
from supabase import create_client, Client

url: str = "http://host.docker.internal:8000"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE"

def article_check_url(supabase, url):
    try:
        response = supabase.table("articles").select("id").eq("url", url).execute()
        if response.data:
            print(f"URL 已存在: {url}")
            return True
        else:
            print(f"URL 不存在: {url}")
            return False
    except Exception as e:
        print(f"Error checking URL: {e}")
        return False

def article_insert(supabase, data):
    # data = {
    #     "id": "4e494cd4-a986-4f64-8406-96a57dd2c14a",  # 使用 UUID 生成唯一 ID
    #     "url": "https://example.com/article1",
    #     "title": "我的第一篇文章",
    #     "content_md": "這是一篇用 Markdown 寫成的文章內容。",
    #     "metadata": {"author": "某某人", "tags": ["Python", "Supabase"]}
    # }
    try:
        supabase.table("articles").insert(data).execute()
    except Exception as e:
        print(f"Error inserting article: {e}")


if __name__ == "__main__":
    supabase: Client = create_client(url, key)
    print("Supabase client created successfully.")
    
    # article_insert(supabase)
    # article_check_url(supabase, "https://example.com/article1")