腳本四: 語義搜索 (Semantic Search)

功能:
1. 接收一個文字查詢作為命令列參數。
2. 將查詢轉換為向量嵌入。
3. 在資料庫中執行向量相似度搜索。
4. 將最相關的結果格式化並輸出到控制台。

執行方式:
python -m scripts.4_semantic_search --query "你的問題是什麼？"
python -m scripts.4_semantic_search --query "RAG是什麼？" --limit 5 --threshold 0.5
"""

import argparse
import logging
import textwrap

# 配置專案根目錄
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.operations import get_database_operations
from embedding.embedding import embed_text

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# 控制台輸出顏色
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def main(query: str, limit: int, threshold: float):
    """
    主執行函數

    Args:
        query (str): 用戶的搜索查詢。
        limit (int): 返回結果的數量上限。
        threshold (float): 相似度閾值。
    """
    logger.info(f"收到搜索請求: '{query}', 上限: {limit}, 閾值: {threshold}")

    # 1. 初始化資料庫連接
    db_ops = get_database_operations()
    if not db_ops:
        logger.error("無法初始化資料庫連接，腳本終止。")
        return

    # 2. 為查詢生成向量嵌入
    logger.info("正在為查詢生成向量嵌入...")
    query_embedding_tensor = embed_text(query)
    if query_embedding_tensor is None:
        logger.error("無法生成查詢的向量嵌入，腳本終止。")
        return
    
    # 從 Tensor 中提取單個向量並轉換為 list
    query_embedding = query_embedding_tensor[0].tolist()
    logger.info("向量嵌入生成成功。")

    # 3. 執行向量搜索
    logger.info("正在資料庫中執行語義搜索...")
    search_results = db_ops.search_similar_chunks(
        embedding=query_embedding,
        limit=limit,
        threshold=threshold
    )

    if not search_results:
        logger.warning("未找到相關結果。您可以嘗試放寬搜索條件（例如降低閾值）。")
        return

    # 4. 格式化並打印結果
    print("\n" + "="*80)
    print(f"{Colors.HEADER}{Colors.BOLD}🔍 語義搜索結果{Colors.ENDC}")
    print("="*80)
    print(f"{Colors.OKBLUE}查詢:{Colors.ENDC} {query}\n")

    for i, result in enumerate(search_results):
        similarity = result.get('similarity_score', 0)
        article_url = result.get('article_url', '未知來源')
        article_title = result.get('article_title', '無標題')
        chunk_content = result.get('chunk_content', '無內容')

        print(f"{Colors.OKGREEN}--- 結果 {i+1} ---
{Colors.ENDC}")
        print(f"{Colors.BOLD}相似度:{Colors.ENDC} {Colors.WARNING}{similarity:.4f}{Colors.ENDC}")
        print(f"{Colors.BOLD}來源:{Colors.ENDC} {Colors.UNDERLINE}{article_url}{Colors.ENDC}")
        print(f"{Colors.BOLD}標題:{Colors.ENDC} {article_title}")
        print(f"{Colors.BOLD}相關內容:{Colors.ENDC}")
        # 使用 textwrap 來格式化長文本，使其更易讀
        wrapped_content = textwrap.fill(chunk_content, width=80, initial_indent='  ', subsequent_indent='  ')
        print(wrapped_content)
        print("\n")

    print("="*80)
    logger.info(f"搜索完成，共找到 {len(search_results)} 條結果。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="語義搜索腳本：在資料庫中執行向量搜索。")
    parser.add_argument(
        '--query',
        type=str,
        required=True,
        help='要執行的文本查詢。'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='返回結果的數量上限。'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.3,
        help='結果的相似度閾值 (0.0 到 1.0)。'
    )
    args = parser.parse_args()

    main(args.query, args.limit, args.threshold)