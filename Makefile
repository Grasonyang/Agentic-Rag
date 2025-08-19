# Agentic RAG System Makefile
# 為新的模組化腳本流程設計

include .env

.PHONY: help install test clean
.PHONY: discover crawl embed search run-pipeline
.PHONY: db-check db-fresh db-clear db-tables db-reset-pending
.PHONY: migrate-supabase

# --- 變數定義 ---
# 可在命令列中覆寫, 例如: make discover DOMAIN=https://www.gemini.com
PYTHON := python3
DOMAIN ?= $(TARGET_URL)
QUERY ?= "What is Retrieval-Augmented Generation?"
LIMIT ?= 100
BATCH_SIZE ?= 10  # 每批處理的 URL 數量

# --- 核心 RAG 流程 ---

discover:
	@echo "🗺️  步驟 1: 發現 $(DOMAIN) 的所有 URL..."
	@$(PYTHON) -m scripts.1_discover_urls --domains $(DOMAIN)

crawl:
	@echo "📄  步驟 2: 爬取已發現的 URL 內容..."
	@$(PYTHON) -m scripts.2_crawl_content --domain $(DOMAIN) --batch_size $(BATCH_SIZE)

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
	@make crawl DOMAIN=$(DOMAIN)
	@make embed
	@echo "✅  數據導入流程完成！"

# --- 資料庫維護 ---

db-check:
	@echo "🩺  執行資料庫健康檢查..."
	@$(PYTHON) -m scripts.database.make-db-check

db-reset-pending:
	@echo "🔄  重設 'error' 和 'null' 狀態的 URL 為 'pending'..."
	@$(PYTHON) -m scripts.database.make-reset-pending --force

db-fresh:
	@echo "🔄  重新初始化資料庫 (將刪除所有數據)..."
	@$(PYTHON) -m scripts.database.make-fresh

db-clear:
	@echo "🔥  清空所有資料庫表中的數據..."
	@$(PYTHON) -m scripts.database.make-clear --force

db-tables:
	@echo "📊  檢查資料庫各表記錄數..."
	@$(PYTHON) -m scripts.database.make-tables

migrate-supabase:
	@echo "🚚  將 PostgreSQL 資料遷移至 Supabase..."
	@$(PYTHON) -m scripts.database.migrate_to_supabase

# --- 專案管理 ---

install:
	@echo "🚀  執行專案安裝與設定腳本..."
	@bash scripts/setup.sh
	@echo "✅  安裝流程結束。"

clean:
	@echo "🧹  清理 pycache 檔案..."
	@find . -type f -name '*.pyc' -delete
	@find . -type d -name '__pycache__' -delete
	@echo "✅  清理完成。"

test:
	@echo "🧪  運行專案測試 (含 scripts/ 與 spider/tests)..."
	@$(PYTHON) -m pytest scripts spider/tests tests

help:
	@echo "Agentic RAG 系統 - 可用命令:"
	@echo "---------------------------------------------------"
	@echo "  專案設定:"
	@echo "    make install      - 安裝所有 Python 依賴並設定爬蟲環境。"
	@echo "    make test         - 運行所有測試。"
	@echo "    make clean        - 清理專案中的 .pyc 和 __pycache__ 檔案。"
	@echo ""
	@echo "  數據導入 (完整流程):"
	@echo "    make run-pipeline - 完整執行 1-3 步，導入一個新網站的數據。"
	@echo ""
	@echo "  數據導入 (單步執行):"
	@echo "    make discover     - 步驟 1: 發現目標網站的所有 URL。"
	@echo "    make crawl        - 步驟 2: 爬取已發現的 URL 內容。"
	@echo "    make embed        - 步驟 3: 為新文章生成向量嵌入。"
	@echo ""
	@echo "  數據查詢:"
	@echo "    make search       - 步驟 4: 執行語義搜索。"
	@echo ""
	@echo "  資料庫維護:"
	@echo "    make db-check     - 檢查資料庫連接和結構。"
	@echo "    make db-tables    - 顯示核心表格的記錄數。"
	@echo "    make db-fresh     - (危險) 重建所有資料表，將刪除所有數據。"
	@echo "    make db-clear     - (危險) 清空所有資料表中的數據。"
	@echo ""
	@echo "  使用範例:"
	@echo "    make run-pipeline DOMAIN=https://www.your-site.com"
	@echo '    make search QUERY="我關心的問題是什麼？"'
	@echo "---------------------------------------------------"

.DEFAULT_GOAL := help
