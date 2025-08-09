# Agentic RAG System Makefile
# 為新的模組化腳本流程設計

.PHONY: help install test clean
.PHONY: discover crawl embed search run-pipeline
.PHONY: db-check db-fresh db-clear db-tables

# --- 變數定義 ---
# 可在命令列中覆寫, 例如: make discover DOMAIN=https://www.gemini.com
PYTHON := python3
DOMAIN ?= https://www.lepoint.fr
QUERY ?= "What is Retrieval-Augmented Generation?"
LIMIT ?= 100

# --- 核心 RAG 流程 ---

discover:
	@echo "🗺️  步驟 1: 發現 $(DOMAIN) 的所有 URL..."
	@$(PYTHON) -m scripts.1_discover_urls --domains $(DOMAIN)

crawl:
	@echo "📄  步驟 2: 爬取已發現的 URL 內容 (上限: $(LIMIT))..."
	@$(PYTHON) -m scripts.2_crawl_content --limit $(LIMIT)

embed:
	@echo "🧠  步驟 3: 為新文章生成向量嵌入 (上限: $(LIMIT))..."
	@$(PYTHON) -m scripts.3_process_and_embed --limit $(LIMIT)

search:
	@echo "🔍  步驟 4: 執行語義搜索..."
	@echo "查詢: $(QUERY)"
	@$(PYTHON) -m scripts.4_semantic_search --query $(QUERY)

run-pipeline:
	@echo "🚀  執行完整的數據導入流程 for $(DOMAIN)..."
	@make discover DOMAIN=$(DOMAIN)
	@make crawl
	@make embed
	@echo "✅  數據導入流程完成！"

# --- 資料庫維護 ---

db-check:
	@echo "🩺  執行資料庫健康檢查..."
	@$(PYTHON) -m scripts.database.make-db-check

db-fresh:
	@echo "🔄  重新初始化資料庫 (將刪除所有數據)..."
	@$(PYTHON) -m scripts.database.make-fresh

db-clear:
	@echo "🔥  清空所有資料庫表中的數據..."
	@$(PYTHON) -m scripts.database.make-clear

db-tables:
	@echo "📊  檢查資料庫各表記錄數..."
	@$(PYTHON) -c "import sys; sys.path.append('.'); from database.operations import get_database_operations; db_ops = get_database_operations(); [print(f'{table}: {db_ops.get_table_count(table)} 條記錄') for table in ['sitemaps', 'discovered_urls', 'articles', 'article_chunks']] if db_ops"

# --- 專案管理 ---

install:
	@echo "📦  安裝 Python 依賴..."
	@pip install -r requirements.txt
	@echo "✅  依賴安裝完成。"

clean:
	@echo "🧹  清理 pycache 檔案..."
	@find . -type f -name '*.pyc' -delete
	@find . -type d -name '__pycache__' -delete
	@echo "✅  清理完成。"

test:
	@echo "🧪  運行專案測試..."
	@$(PYTHON) -m pytest

help:
	@echo "Agentic RAG 系統 - 可用命令:"
	@echo "---------------------------------------------------"
	@echo "  核心流程:"
	@echo "    make discover     - 發現目標網站的所有 URL。可設置 DOMAIN。"
	@echo "    make crawl        - 爬取已發現的 URL 內容。可設置 LIMIT。"
	@echo "    make embed        - 為新文章生成向量嵌入。可設置 LIMIT。"
	@echo "    make search       - 執行語義搜索。可設置 QUERY。"
	@echo "    make run-pipeline - 完整執行 discover -> crawl -> embed 流程。"
	@echo "
  資料庫維護:"
	@echo "    make db-check     - 檢查資料庫連接和結構。"
	@echo "    make db-fresh     - 重建所有資料表 (警告: 刪除所有數據)。"
	@echo "    make db-clear     - 清空所有資料表中的數據。"
	@echo "    make db-tables    - 顯示核心表格的記錄數。"
	@echo "
  專案管理:"
	@echo "    make install      - 安裝所有 Python 依賴。"
	@echo "    make clean        - 清理專案中的 .pyc 和 __pycache__ 檔案。"
	@echo "    make test         - 運行所有測試。"
	@echo "    make help         - 顯示此幫助訊息。"
	@echo "
  使用範例:"
	@echo "    make run-pipeline DOMAIN=https://www.your-site.com"
	@echo "    make search QUERY=\"我關心的問題是什麼？\""
	@echo "---------------------------------------------------"

.DEFAULT_GOAL := help