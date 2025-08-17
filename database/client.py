"""PostgreSQL 客戶端相容層"""

from config_manager import load_config
from .postgres_client import PostgreSQLClient

# 載入 .env 設定
load_config()

class PostgresClient(PostgreSQLClient):
    """PostgreSQL 客戶端，提供基本連線管理"""
    pass
