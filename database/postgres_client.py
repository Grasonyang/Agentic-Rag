#!/usr/bin/env python3
"""
postgres_client.py - PostgreSQL 直接連接客戶端

功能：
1. 使用 psycopg2 直接連接 Supabase PostgreSQL
2. 繞過 RLS 策略限制
3. 支援 schema 執行和資料庫管理操作
4. 提供連接池和事務管理
"""

import os
import sys
import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from spider.utils.enhanced_logger import get_spider_logger

logger = get_spider_logger("postgres_client")  # 取得資料庫日誌記錄器


class PostgreSQLClient:
    """PostgreSQL 直接連接客戶端"""
    
    def __init__(self, config_dict: Optional[Dict[str, str]] = None):
        """
        初始化 PostgreSQL 客戶端
        
        Args:
            config_dict: 配置字典，包含 host, port, database, user, password
        """
        if config_dict:
            # 使用提供的配置
            self.connection_params = config_dict
        else:
            # 從環境變數讀取配置
            self.connection_params = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'database': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'postgres')
            }
    
    def connect(self) -> bool:
        """
        建立資料庫連接
        
        Returns:
            bool: 連接是否成功
        """
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            logger.info("✅ PostgreSQL 連接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL 連接失敗: {e}")
            return False
    
    def disconnect(self):
        """關閉資料庫連接"""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        
        if self.connection:
            self.connection.close()
            self.connection = None
        
        logger.info("📌 PostgreSQL 連接已關閉")
    
    def execute_query(self, query: str, params: Tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
        """
        執行 SQL 查詢
        
        Args:
            query: SQL 查詢語句
            params: 查詢參數
            fetch: 是否獲取結果
            
        Returns:
            查詢結果或 None
        """
        try:
            self.cursor.execute(query, params)
            
            if fetch:
                return self.cursor.fetchall()
            else:
                self.connection.commit()
                return None
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"❌ SQL 執行失敗: {e}")
            logger.error(f"SQL: {query}")
            raise e
    
    def execute_script(self, script_content: str) -> Tuple[int, int, List[str]]:
        """
        執行 SQL 腳本
        
        Args:
            script_content: SQL 腳本內容
            
        Returns:
            (成功語句數, 失敗語句數, 錯誤列表)
        """
        # 分割 SQL 語句
        statements = self._split_sql_statements(script_content)
        
        success_count = 0
        error_count = 0
        errors = []
        
        for i, statement in enumerate(statements):
            statement = statement.strip()
            if not statement or statement.startswith('--'):
                continue
            
            try:
                self.cursor.execute(statement)
                self.connection.commit()
                success_count += 1
                logger.debug(f"✅ 語句 {i+1} 執行成功")
                
            except Exception as e:
                self.connection.rollback()
                error_count += 1
                error_msg = f"語句 {i+1} 執行失敗: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
                logger.debug(f"失敗的 SQL: {statement[:100]}...")
        
        logger.info(f"📊 腳本執行完成: {success_count} 成功, {error_count} 失敗")
        return success_count, error_count, errors
    
    def _split_sql_statements(self, script_content: str) -> List[str]:
        """
        分割 SQL 語句，正確處理 dollar-quoted strings
        
        Args:
            script_content: SQL 腳本內容
            
        Returns:
            SQL 語句列表
        """
        import re
        
        # 移除註釋和空行
        lines = []
        in_multiline_comment = False
        
        for line in script_content.split('\n'):
            line = line.strip()
            
            # 處理多行註釋
            if '/*' in line and '*/' in line:
                # 單行多行註釋
                continue
            elif '/*' in line:
                in_multiline_comment = True
                continue
            elif '*/' in line:
                in_multiline_comment = False
                continue
            elif in_multiline_comment:
                continue
            
            # 跳過單行註釋和空行
            if line.startswith('--') or not line:
                continue
            
            lines.append(line)
        
        # 重新組合
        content = '\n'.join(lines)
        
        # 使用更智能的方式分割 SQL 語句，考慮 dollar-quoted strings
        statements = []
        current_statement = ""
        in_dollar_quote = False
        dollar_tag = None
        
        i = 0
        while i < len(content):
            char = content[i]
            
            # 檢查是否是 dollar quote 開始
            if char == '$' and not in_dollar_quote:
                # 查找 dollar tag
                tag_match = re.match(r'\$([^$]*)\$', content[i:])
                if tag_match:
                    dollar_tag = tag_match.group(1)
                    in_dollar_quote = True
                    current_statement += tag_match.group(0)
                    i += len(tag_match.group(0))
                    continue
                    
            # 檢查是否是 dollar quote 結束
            elif char == '$' and in_dollar_quote:
                end_tag = f"${dollar_tag}$"
                if content[i:].startswith(end_tag):
                    in_dollar_quote = False
                    current_statement += end_tag
                    i += len(end_tag)
                    dollar_tag = None
                    continue
                    
            # 如果不在 dollar quote 中且遇到分號，則結束當前語句
            elif char == ';' and not in_dollar_quote:
                current_statement += char
                if current_statement.strip():
                    statements.append(current_statement.strip())
                current_statement = ""
                i += 1
                continue
            
            # 其他字符直接添加
            current_statement += char
            i += 1
        
        # 添加最後一個語句（如果有）
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        return statements
    
    def get_table_count(self, table_name: str) -> int:
        """
        獲取表格記錄數
        
        Args:
            table_name: 表格名稱
            
        Returns:
            記錄數
        """
        try:
            query = f"SELECT COUNT(*) as count FROM {table_name}"
            result = self.execute_query(query)
            return result[0]['count'] if result else 0
            
        except Exception as e:
            logger.error(f"❌ 獲取表格 {table_name} 記錄數失敗: {e}")
            return 0
    
    def clear_table(self, table_name: str) -> bool:
        """
        清空表格
        
        Args:
            table_name: 表格名稱
            
        Returns:
            是否成功
        """
        try:
            query = f"DELETE FROM {table_name}"
            self.execute_query(query, fetch=False)
            logger.info(f"✅ 表格 {table_name} 已清空")
            return True
            
        except Exception as e:
            logger.error(f"❌ 清空表格 {table_name} 失敗: {e}")
            return False
    
    def table_exists(self, table_name: str, schema: str = 'public') -> bool:
        """
        檢查表格是否存在
        
        Args:
            table_name: 表格名稱
            schema: Schema 名稱
            
        Returns:
            表格是否存在
        """
        try:
            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = %s
            )
            """
            result = self.execute_query(query, (schema, table_name))
            return result[0]['exists'] if result else False
            
        except Exception as e:
            logger.error(f"❌ 檢查表格 {table_name} 是否存在失敗: {e}")
            return False
    
    def function_exists(self, function_name: str, schema: str = 'public') -> bool:
        """
        檢查函數是否存在
        
        Args:
            function_name: 函數名稱
            schema: Schema 名稱
            
        Returns:
            函數是否存在
        """
        try:
            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.routines
                WHERE routine_schema = %s 
                AND routine_name = %s
            )
            """
            result = self.execute_query(query, (schema, function_name))
            return result[0]['exists'] if result else False
            
        except Exception as e:
            logger.error(f"❌ 檢查函數 {function_name} 是否存在失敗: {e}")
            return False
    
    def get_database_version(self) -> str:
        """
        獲取資料庫版本
        
        Returns:
            資料庫版本
        """
        try:
            result = self.execute_query("SELECT version()")
            return result[0]['version'] if result else "Unknown"
            
        except Exception as e:
            logger.error(f"❌ 獲取資料庫版本失敗: {e}")
            return "Unknown"
    
    def get_current_user(self) -> str:
        """
        獲取當前用戶
        
        Returns:
            當前用戶名
        """
        try:
            result = self.execute_query("SELECT current_user")
            return result[0]['current_user'] if result else "Unknown"
            
        except Exception as e:
            logger.error(f"❌ 獲取當前用戶失敗: {e}")
            return "Unknown"
    
    def disable_rls(self, table_name: str) -> bool:
        """
        禁用表格的 RLS
        
        Args:
            table_name: 表格名稱
            
        Returns:
            是否成功
        """
        try:
            query = f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"
            self.execute_query(query, fetch=False)
            logger.info(f"✅ 表格 {table_name} RLS 已禁用")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ 禁用表格 {table_name} RLS 失敗: {e}")
            return False
    
    def enable_rls(self, table_name: str) -> bool:
        """
        啟用表格的 RLS
        
        Args:
            table_name: 表格名稱
            
        Returns:
            是否成功
        """
        try:
            query = f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
            self.execute_query(query, fetch=False)
            logger.info(f"✅ 表格 {table_name} RLS 已啟用")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ 啟用表格 {table_name} RLS 失敗: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def test_connection():
    """測試資料庫連接"""
    try:
        with PostgreSQLClient() as client:
            logger.info("✅ 連接成功!")
            
            # 測試基本查詢
            version = client.get_database_version()
            user = client.get_current_user()
            
            logger.info(f"📊 資料庫版本: {version}")
            logger.info(f"👤 當前用戶: {user}")
            
            # 測試表格檢查
            tables = ["discovered_urls", "articles", "article_chunks", "sitemaps"]
            for table in tables:
                exists = client.table_exists(table)
                count = client.get_table_count(table) if exists else 0
                status = "✅" if exists else "❌"
                logger.info(
                    f"{status} 表格 {table}: {'存在' if exists else '不存在'} ({count} 筆記錄)"
                )
            
    except Exception as e:
        logger.error(f"❌ 連接測試失敗: {e}")


if __name__ == "__main__":
    test_connection()
