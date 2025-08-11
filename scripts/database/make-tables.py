#!/usr/bin/env python3
"""
make-tables.py - 顯示資料庫各表記錄數
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from config_manager import load_config
load_config()

from database.operations import get_database_operations

def main():
    """主函數"""
    db_ops = get_database_operations()
    if db_ops:
        tables = ['sitemaps', 'discovered_urls', 'articles', 'article_chunks']
        for table in tables:
            try:
                count = db_ops.get_table_count(table)
                print(f'{table}: {count} 條記錄')
            except Exception as e:
                print(f"Error getting count for table {table}: {e}")
    else:
        print("Could not connect to the database.")

if __name__ == "__main__":
    main()