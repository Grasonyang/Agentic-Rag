#!/usr/bin/env python3
"""
make-search.py
搜索查詢腳本 - RAG 流程第五步
執行語義搜索並展示結果
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.client import SupabaseClient
from database.operations import DatabaseOperations
from embedding import EmbeddingManager
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def search_content(query: str, limit: int = 5, threshold: float = 0.7):
    """執行語義搜索"""
    print("🔍 RAG 步驟 5: 語義搜索")
    print("=" * 50)
    print(f"🎯 搜索查詢: '{query}'")
    
    try:
        # 連接資料庫
        print("\n📡 連接資料庫...")
        client = SupabaseClient()
        db_ops = DatabaseOperations(client.get_client())
        
        # 初始化嵌入管理器
        print("🧠 初始化嵌入模型...")
        embedding_manager = EmbeddingManager()
        
        # 生成查詢嵌入
        print("🔄 生成查詢嵌入向量...")
        query_embedding = embedding_manager.get_embedding(query)
        
        # 執行語義搜索
        print("🔍 執行語義搜索...")
        results = db_ops.semantic_search(
            query_text=query,
            query_embedding=query_embedding.tolist(),
            match_threshold=threshold,
            match_count=limit
        )
        
        if not results:
            print("❌ 沒有找到相關結果")
            print("\n💡 建議:")
            print("1. 降低相似度閾值 (--threshold)")
            print("2. 增加搜索結果數量 (--limit)")
            print("3. 嘗試不同的搜索關鍵詞")
            return False
        
        # 顯示搜索結果
        print(f"\n📊 找到 {len(results)} 個相關結果:")
        print("=" * 80)
        
        for i, result in enumerate(results, 1):
            print(f"\n[結果 {i}] 相似度: {result.get('similarity', 0):.3f}")
            print(f"📄 文章: {result.get('article_title', 'Unknown')}")
            print(f"🔗 URL: {result.get('article_url', 'Unknown')}")
            print(f"📄 分塊 #{result.get('chunk_index', 0)}")
            
            content = result.get('content', '')
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"📝 內容: {content}")
            print("-" * 80)
        
        # 記錄搜索日誌
        print("\n📝 記錄搜索日誌...")
        from database.models import SearchLogModel
        search_log = SearchLogModel(
            query=query,
            results_count=len(results),
            search_type="semantic",
            metadata={
                "threshold": threshold,
                "limit": limit,
                "has_results": len(results) > 0
            }
        )
        db_ops.create_search_log(search_log)
        
        print("✅ 搜索完成!")
        return True
        
    except Exception as e:
        print(f"❌ 搜索失敗: {e}")
        return False

def interactive_search():
    """互動式搜索模式"""
    print("🔍 互動式搜索模式")
    print("=" * 50)
    print("輸入查詢內容，或輸入 'quit' 退出")
    
    while True:
        try:
            query = input("\n🔍 請輸入搜索內容: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("👋 退出搜索模式")
                break
                
            if not query:
                print("⚠️ 請輸入有效的搜索內容")
                continue
                
            search_content(query)
            
        except KeyboardInterrupt:
            print("\n👋 退出搜索模式")
            break
        except Exception as e:
            print(f"❌ 搜索過程出錯: {e}")

def show_search_history():
    """顯示搜索歷史"""
    print("📚 搜索歷史")
    print("=" * 30)
    
    try:
        client = SupabaseClient()
        db_ops = DatabaseOperations(client.get_client())
        
        # 獲取最近的搜索記錄
        logs = db_ops.get_recent_search_logs(limit=10)
        
        if not logs:
            print("沒有搜索歷史")
            return
        
        for i, log in enumerate(logs, 1):
            print(f"{i}. '{log.query}' - {log.results_count} 個結果")
            print(f"   時間: {log.created_at}")
            
    except Exception as e:
        print(f"❌ 獲取搜索歷史失敗: {e}")

def test_search_system():
    """測試搜索系統"""
    print("🧪 測試搜索系統")
    print("=" * 30)
    
    test_queries = [
        "測試",
        "API",
        "JSON",
        "網頁"
    ]
    
    for query in test_queries:
        print(f"\n測試查詢: '{query}'")
        result = search_content(query, limit=3, threshold=0.5)
        if result:
            print("✅ 搜索成功")
        else:
            print("❌ 搜索失敗")

def main():
    """主函數"""
    import argparse
    parser = argparse.ArgumentParser(description="語義搜索工具")
    parser.add_argument("query", nargs="?", help="搜索查詢")
    parser.add_argument("--limit", type=int, default=5, help="結果數量限制")
    parser.add_argument("--threshold", type=float, default=0.7, help="相似度閾值")
    parser.add_argument("--interactive", "-i", action="store_true", help="互動式搜索")
    parser.add_argument("--history", action="store_true", help="顯示搜索歷史")
    parser.add_argument("--test", action="store_true", help="測試搜索系統")
    args = parser.parse_args()
    
    if args.test:
        test_search_system()
    elif args.history:
        show_search_history()
    elif args.interactive:
        interactive_search()
    elif args.query:
        search_content(args.query, args.limit, args.threshold)
    else:
        print("請提供搜索查詢或使用 --interactive 模式")
        print("範例: python make-search.py '您的搜索內容'")

if __name__ == "__main__":
    main()
