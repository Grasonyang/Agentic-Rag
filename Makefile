# Makefile for Agentic RAG System

.PHONY: help install test clean db-setup db-clear spider-test embedding-test
.PHONY: get-sitemap get-urls get-chunking get-embedding run-workflow

# Default goal
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
VENV := venv
REQUIREMENTS := requirements.txt

# URLs and files for workflow
URL ?= https://example.com
SITEMAP_LIST ?= sitemaps.txt
URL_LIST ?= urls.txt
CHUNK_LIST ?= chunks.txt

# Help target
help: ## Show this help message
	@echo "Agentic RAG System - Available Commands:"
	@echo ""
	@echo "Setup and Environment:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(install|clean|test)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""  
	@echo "Database Operations:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "db-" | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Workflow Scripts:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(get-|run-)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Testing:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "test" | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and setup
install: ## Install dependencies
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r $(REQUIREMENTS)

clean: ## Clean up temporary files and caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -f *.log
	rm -f *.txt

# Database operations
db-setup: ## Setup fresh database with all schemas
	$(PYTHON) scripts/database/make-db-fresh.py

db-clear: ## Clear all database data
	$(PYTHON) scripts/database/make-db-clear.py

db-test: ## Test database connection
	$(PYTHON) scripts/database/make-db-connect-test.py

# Workflow scripts
get-sitemap: ## Discover and analyze sitemaps from URL
	@echo "🗺️  Discovering sitemaps from: $(URL)"
	$(PYTHON) scripts/getSiteMap.py --url $(URL) --output $(SITEMAP_LIST)
	@echo "✅ Sitemap discovery complete. Output: $(SITEMAP_LIST)"

get-urls: ## Extract URLs from sitemap list  
	@echo "🔗 Extracting URLs from: $(SITEMAP_LIST)"
	$(PYTHON) scripts/getUrls.py --sitemap-list $(SITEMAP_LIST) --output $(URL_LIST)
	@echo "✅ URL extraction complete. Output: $(URL_LIST)"

get-chunking: ## Crawl URLs and create content chunks
	@echo "📄 Crawling URLs and chunking content from: $(URL_LIST)"
	$(PYTHON) scripts/getChunking.py --url-list $(URL_LIST) --output $(CHUNK_LIST)
	@echo "✅ Content chunking complete. Output: $(CHUNK_LIST)"

get-embedding: ## Generate embeddings for chunks
	@echo "🧠 Generating embeddings for: $(CHUNK_LIST)"
	$(PYTHON) scripts/getEmbedding.py --chunk-list $(CHUNK_LIST)
	@echo "✅ Embedding generation complete. RAG system ready!"

# Complete workflow
run-workflow: ## Run complete RAG workflow (sitemap → urls → chunking → embedding)
	@echo "🚀 Starting complete RAG workflow..."
	@echo ""
	@$(MAKE) get-sitemap URL=$(URL)
	@echo ""
	@$(MAKE) get-urls SITEMAP_LIST=$(SITEMAP_LIST)
	@echo ""
	@$(MAKE) get-chunking URL_LIST=$(URL_LIST)
	@echo ""
	@$(MAKE) get-embedding CHUNK_LIST=$(CHUNK_LIST)
	@echo ""
	@echo "🎉 Complete RAG workflow finished!"
	@echo "🔍 Your knowledge base is ready for semantic search."

# Testing targets
test: ## Run all tests
	$(PYTHON) -m pytest tests/ -v

spider-test: ## Test spider functionality
	$(PYTHON) scripts/test.py

embedding-test: ## Test embedding functionality
	$(PYTHON) -c "from embedding.embedding import EmbeddingManager; em = EmbeddingManager(); print('✅ Embedding system working')"

# Advanced workflow options
get-sitemap-custom: ## Custom sitemap discovery with options
	@echo "🗺️  Custom sitemap discovery..."
	$(PYTHON) scripts/getSiteMap.py --url $(URL) --output $(SITEMAP_LIST) --max-depth 3 --batch-size 10

get-chunking-custom: ## Custom chunking with semantic strategy
	@echo "📄 Custom semantic chunking..."
	$(PYTHON) scripts/getChunking.py --url-list $(URL_LIST) --output $(CHUNK_LIST) --chunker semantic --chunk-size 500 --overlap 100

get-embedding-gpu: ## Generate embeddings using GPU
	@echo "🚀 GPU-accelerated embedding generation..."
	$(PYTHON) scripts/getEmbedding.py --chunk-list $(CHUNK_LIST) --device cuda --batch-size 32

# Monitoring and logs
show-stats: ## Show processing statistics
	@echo "📊 Processing Statistics:"
	@echo "Sitemaps discovered: $$(grep -c 'Sitemap:' $(SITEMAP_LIST) 2>/dev/null || echo 0)"
	@echo "URLs extracted: $$(grep -c '^- http' $(URL_LIST) 2>/dev/null || echo 0)"  
	@echo "Chunks created: $$(grep -c '^## Chunk' $(CHUNK_LIST) 2>/dev/null || echo 0)"

show-logs: ## Show recent processing logs
	@echo "📋 Recent Processing Logs:"
	@tail -20 *.log 2>/dev/null || echo "No log files found"

# Cleanup workflow files
clean-workflow: ## Clean workflow output files
	rm -f $(SITEMAP_LIST) $(URL_LIST) $(CHUNK_LIST)
	@echo "🗑️  Workflow files cleaned"
