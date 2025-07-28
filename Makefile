# Makefile for Agentic RAG System Database Management

.PHONY: db-check db-status db-fresh db-clear db-form db-tables db-fresh-force db-clear-force
.PHONY: logs-show logs-clean output-show help install test spider-run db-test
.PHONY: get-sitemap get-urls get-chunking get-embedding run-workflow

# Default goal
.DEFAULT_GOAL := help

# Variables for workflow
URL ?= https://example.com
SITEMAP_LIST ?= sitemaps.txt
URL_LIST ?= urls.txt
MAX_URLS ?= 1000
CHUNK_SIZE ?= 200

db-check:
	python3 scripts/database/make-db-check.py

db-status:
	@echo '🔍 快速資料庫狀態檢查...'
	@python3 -c "import sys; sys.path.append('.'); from database.postgres_client import PostgreSQLClient; client = PostgreSQLClient(); client.connect(); print('✅ 資料庫連接正常'); client.disconnect()" 2>/dev/null || echo '❌ 資料庫連接失敗'

db-fresh:
	@echo "🔄 重新初始化資料庫..."
	@python3 scripts/database/make-fresh.py

db-clear:
	python3 scripts/database/make-clear.py

# Additional database commands
db-form:
	@echo "📄 獲取資料庫表單數據..."
	@python3 scripts/database/make-db-check.py | grep -A 1000 "資料庫表單 JSON 數據:" | tail -n +3

db-tables:
	@echo "📋 資料庫表格信息..."
	@python3 -c "import sys; sys.path.append('.'); from database.postgres_client import PostgreSQLClient; client = PostgreSQLClient(); client.connect(); tables = ['discovered_urls', 'articles', 'article_chunks', 'sitemaps']; [print(f'📊 {table}: {client.get_table_count(table) if client.table_exists(table) else \"不存在\"} 筆記錄') for table in tables]; client.disconnect()"

db-fresh-force:
	@echo "🔥 強制重新初始化資料庫..."
	@python3 scripts/database/make-fresh.py --force

db-clear-force:
	@echo "🔥 強制清空資料庫數據..."
	@python3 scripts/database/make-clear.py --force

# Utility commands
logs-show:
	@echo "📋 最近的腳本日誌:"
	@ls -la scripts/logs/ 2>/dev/null | tail -10 || echo "沒有日誌目錄"

logs-clean:
	@echo "🧹 清理舊日誌文件..."
	@find scripts/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true
	@echo "✅ 日誌清理完成"

output-show:
	@echo "📁 最近生成的輸出文件:"
	@ls -la scripts/output/ 2>/dev/null | tail -10 || echo "沒有輸出文件"

help:
	@echo "可用的資料庫指令:"
	@echo "  db-check        - 執行完整的資料庫健康檢查"
	@echo "  db-status       - 快速資料庫狀態檢查"
	@echo "  db-fresh        - 重新初始化資料庫"
	@echo "  db-fresh-force  - 強制重新初始化資料庫"
	@echo "  db-clear        - 清空資料庫數據"
	@echo "  db-clear-force  - 強制清空資料庫數據"
	@echo "  db-form         - 獲取資料庫表單數據 (JSON)"
	@echo "  db-tables       - 顯示資料庫表格信息"
	@echo ""
	@echo "RAG 工作流程指令:"
	@echo "  get-sitemap     - 獲取網站 Sitemap 列表"
	@echo "  get-urls        - 從 Sitemap 提取 URL"
	@echo "  get-chunking    - 爬取內容並分塊"
	@echo "  get-embedding   - 生成嵌入向量"
	@echo "  run-workflow    - 執行完整 RAG 流程"
	@echo ""
	@echo "使用範例:"
	@echo "  make run-workflow URL=https://docs.python.org"
	@echo "  make get-sitemap URL=https://example.com"
	@echo "  make get-urls SITEMAP_LIST=sitemaps.txt MAX_URLS=500"
	@echo ""
	@echo "日誌和維護指令:"
	@echo "  logs-show       - 顯示最近的日誌"
	@echo "  logs-clean      - 清理舊日誌文件"
	@echo "  output-show     - 顯示最近的輸出文件"
	@echo ""
	@echo "項目設置指令:"
	@echo "  install         - 安裝 Python 依賴"
	@echo "  test            - 運行測試"
	@echo "  spider-run      - 運行爬蟲測試"
	@echo "  db-test         - 測試資料庫完整流程"

# Project setup commands
install:
	@echo "📦 安裝 Python 依賴..."
	@pip3 install -r requirements.txt
	@echo "✅ 依賴安裝完成"

test:
	@echo "🧪 運行測試..."
	@python3 -m pytest scripts/database/test_db_check.py -v
	@echo "✅ 測試完成"

spider-run:
	@echo "🕷️ 運行爬蟲測試..."
	@python3 -c "import sys; sys.path.append('.'); from spider.rag_spider import RAGSpider; spider = RAGSpider(); print('🚀 爬蟲初始化成功')"

# Database testing command
db-test:
	@echo "🧪 測試資料庫完整流程..."
	@echo "1️⃣ 檢查資料庫狀態..."
	@make db-status
	@echo "2️⃣ 執行健康檢查..."
	@make db-check > /dev/null
	@echo "3️⃣ 顯示表格信息..."
	@make db-tables
	@echo "✅ 資料庫測試完成！"

# RAG Workflow Commands
get-sitemap:
	@echo "🗺️ 獲取 Sitemap 列表..."
	@echo "目標網站: $(URL)"
	@python3 -c "import sys; sys.path.append('.'); from spider.rag_spider import discover_sitemaps; discover_sitemaps('$(URL)', '$(SITEMAP_LIST)')"

# 使用 .env 中的 TARGET_URLS 進行完整工作流程
run-env-workflow:
	@echo "🚀 使用 .env 設定執行 RAG 工作流程..."
	@echo "====================================="
	@python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(f'目標 URLs: {os.getenv(\"TARGET_URLS\", \"未設定\")}')"
	@echo "====================================="
	@echo ""
	@echo "步驟 1: 從 .env 讀取並發現 Sitemap"
	@python3 -c "import sys, os; sys.path.append('.'); from dotenv import load_dotenv; load_dotenv(); from spider.rag_spider import discover_sitemaps; target_urls = os.getenv('TARGET_URLS', ''); [discover_sitemaps(url.strip(), 'sitemaps.txt') for url in target_urls.split(',') if url.strip()]"
	@echo ""
	@echo "步驟 2: 提取 URL"
	@make get-urls SITEMAP_LIST=$(SITEMAP_LIST) MAX_URLS=$(MAX_URLS)
	@echo ""
	@echo "步驟 3: 爬取和分塊"
	@make get-chunking URL_LIST=$(URL_LIST) CHUNK_SIZE=$(CHUNK_SIZE)
	@echo ""
	@echo "步驟 4: 生成嵌入"
	@make get-embedding
	@echo ""
	@echo "✅ RAG 工作流程完成！"
	@make db-tables

get-urls:
	@echo "🔗 從 Sitemap 提取 URL 列表..."
	@echo "Sitemap 清單: $(SITEMAP_LIST)"
	@echo "最大 URL 數: $(MAX_URLS)"
	@python3 -c "import sys; sys.path.append('.'); from spider.rag_spider import extract_urls_from_sitemaps; extract_urls_from_sitemaps('$(SITEMAP_LIST)', '$(URL_LIST)', $(MAX_URLS))"

get-chunking:
	@echo "📄 爬取網頁內容並進行分塊..."
	@echo "URL 清單: $(URL_LIST)"
	@echo "塊大小: $(CHUNK_SIZE)"
	@python3 -c "import sys; sys.path.append('.'); from spider.rag_spider import crawl_and_chunk_urls; crawl_and_chunk_urls('$(URL_LIST)', $(CHUNK_SIZE))"

get-embedding:
	@echo "🧠 生成內容嵌入向量..."
	@python3 -c "import sys; sys.path.append('.'); print('⚠️ 嵌入功能開發中...')"

run-workflow:
	@echo "🚀 執行完整 RAG 工作流程..."
	@echo "====================================="
	@echo "目標網站: $(URL)"
	@echo "====================================="
	@echo ""
	@echo "步驟 1: 發現 Sitemap"
	@make get-sitemap URL=$(URL)
	@echo ""
	@echo "步驟 2: 提取 URL"
	@make get-urls SITEMAP_LIST=$(SITEMAP_LIST) MAX_URLS=$(MAX_URLS)
	@echo ""
	@echo "步驟 3: 爬取和分塊"
	@make get-chunking URL_LIST=$(URL_LIST) CHUNK_SIZE=$(CHUNK_SIZE)
	@echo ""
	@echo "步驟 4: 生成嵌入"
	@make get-embedding
	@echo ""
	@echo "✅ RAG 工作流程完成！"
	@make db-tables
