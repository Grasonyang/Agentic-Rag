"""將本地 PostgreSQL 資料遷移至 Supabase 的示範腳本"""

import logging

from database.operations import get_database_operations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    db = get_database_operations()
    if not db:
        logger.error("無法連接 PostgreSQL，遷移流程終止")
        return

    # 這裡僅示範如何取得資料，實際遷移邏輯請自行擴充
    count = db.get_table_count("articles")
    logger.info(f"PostgreSQL 目前共有 {count} 篇文章，可在此實作上傳至 Supabase 的流程")


if __name__ == "__main__":
    main()
