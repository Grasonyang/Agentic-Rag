"""共用的 FastAPI 依賴"""

import os
from functools import lru_cache
from typing import Generator

import google.generativeai as genai
from config_manager import load_config
from database.operations import get_database_operations

# 載入 .env 設定
load_config()


def get_db() -> Generator:
    """提供資料庫連線"""
    db = get_database_operations()
    try:
        yield db
    finally:
        if db:
            db.close()


@lru_cache
def get_a2a_client() -> genai.GenerativeModel:
    """取得 Google A2A API 客戶端"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GOOGLE_API_KEY")
    genai.configure(api_key=api_key)
    model_name = os.getenv("GOOGLE_A2A_MODEL", "gemini-1.5-pro")
    return genai.GenerativeModel(model_name)
