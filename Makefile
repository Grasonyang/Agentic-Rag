# Agentic RAG Framework Makefile
# 5-step RAG workflow automation

.PHONY: help rag-full db-setup crawl chunk embed search clean test stats

# Default target
help:
	@echo "Agentic RAG Framework - 5-step RAG workflow"
	@echo "=============================================="
	@echo ""
	@echo "Complete RAG workflow:"
	@echo "  rag-full        - Execute complete RAG pipeline (steps 1-5)"
	@echo ""
	@echo "Individual steps:"
	@echo "  1. db-setup     - Database setup and validation"
	@echo "  2. crawl        - Complete crawling (robot + data)"
	@echo "     crawl-robot  - Phase 1: Robot analysis & link discovery"
	@echo "     crawl-data   - Phase 2: Content crawling"
	@echo "     crawl-dfs    - DFS deep crawling strategy"
	@echo "     crawl-bfs    - BFS broad crawling strategy"
	@echo "  3. chunk        - Text chunking and processing"
	@echo "  4. embed        - Generate embedding vectors"
	@echo "  5. search       - Semantic search and query"
	@echo ""
	@echo "Utilities:"
	@echo "  clean           - Clean temporary files"
	@echo "  test            - Run system tests"
	@echo "  help            - Show this help message"

# Complete RAG workflow
rag-full: db-setup crawl-robot crawl-data chunk embed search
	@echo "✅ Complete RAG workflow finished!"

# Step 1: Database setup
db-setup:
	@echo "🔧 Step 1: Database setup..."
	python scripts/make-database-setup.py
	@echo "✅ Step 1 completed: Database setup"

# Step 2: Data crawling (Two-phase approach)
crawl: crawl-robot crawl-data
	@echo "✅ 完整爬取流程完成: Robot 解析 + 資料爬取"

# Phase 1: Robot analysis and link discovery
crawl-robot:
	@echo "🤖 階段 1: Robot 解析與連結發現..."
	python scripts/make-crawl-robot.py
	@echo "✅ 階段 1 完成: Robot 解析"

# Phase 2: Data content crawling
crawl-data:
	@echo "📊 階段 2: 資料內容爬取..."
	python scripts/make-crawl-data.py
	@echo "✅ 階段 2 完成: 資料爬取"

# Alternative crawling strategies
crawl-dfs:
	@echo "🌊 使用 DFS 深度優先策略爬取..."
	python scripts/make-crawl-data.py --strategy dfs
	@echo "✅ DFS 爬取完成"

crawl-bfs:
	@echo "🌐 使用 BFS 廣度優先策略爬取..."
	python scripts/make-crawl-data.py --strategy bfs
	@echo "✅ BFS 爬取完成"

# Step 3: Data chunking
chunk:
	@echo "📄 Step 3: Chunking data..."
	python scripts/make-chunk-data.py
	@echo "✅ Step 3 completed: Data chunking"

# Step 4: Generate embeddings
embed:
	@echo "🔢 Step 4: Generating embeddings..."
	python scripts/make-embedding.py
	@echo "✅ Step 4 completed: Embeddings"

# Step 5: Search and query
search:
	@echo "🔍 Step 5: Search and query..."
	python scripts/make-search.py
	@echo "✅ Step 5 completed: Search"

# Clean temporary files
clean:
	@echo "🧹 Cleaning temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	@echo "✅ Cleanup completed"

# Run system tests
test:
	@echo "🧪 Running system tests..."
	python -m pytest tests/ -v
	@echo "✅ Tests completed"

# Show database statistics
stats:
	@echo "📊 Database statistics..."
	python scripts/make-database-setup.py --stats
	@echo "✅ Statistics displayed"
