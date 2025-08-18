#!/bin/bash
# Agentic RAG System - 安裝與設定腳本

set -e

# --- 步驟 0: 更新系統套件並安裝必要的開發工具 ---
echo "🔄  正在更新 apt 套件列表..."
sudo apt-get update

echo "🛠️  正在安裝 build-essential, libpq-dev, python3-dev, pkg-config..."
sudo apt-get install -y build-essential libpq-dev python3-dev pkg-config

# --- 步驟 1: 安裝 Python 依賴 ---
echo "📦  正在從 requirements.txt 安裝 Python 依賴..."

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "✅  所有 Python 依賴安裝完成。"

# --- 步驟 2: 設定 crawl4ai ---
echo "🤖  正在設定 crawl4ai，這將會下載必要的瀏覽器..."

# 執行 crawl4ai 的設定命令
# 這會下載 Playwright 的瀏覽器，是執行爬蟲所必需的
crawl4ai-setup

echo "✅  crawl4ai 設定完成。"

# --- 完成 ---
echo "🎉  專案環境安裝與設定全部完成！"
echo "現在您可以開始使用 make 命令 (例如: make run-pipeline) 來執行工作流程。"

# --- 步驟 3: 安裝並設定 PostgreSQL ---
echo "🐘  正在安裝並設定 PostgreSQL 資料庫..."

# 更新 apt 套件列表 (再次確認，以防萬一)
sudo apt-get update

# 安裝 PostgreSQL 及其 contrib 模組
sudo apt-get install -y postgresql postgresql-contrib

# --- 在非 systemd 環境中啟動 PostgreSQL ---
echo "🚀  正在啟動 PostgreSQL 服務..."
# 使用 service 命令啟動，適用於無 systemd 的環境
service postgresql start

# 等待幾秒鐘確保服務完全啟動
sleep 5

# --- 設定資料庫 ---
# 為 'postgres' 使用者設定密碼，並提示使用者更新 .env 檔案
echo "🔑  正在為 'postgres' 使用者設定預設密碼..."
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"

echo "ℹ️  已將 'postgres' 使用者的密碼設定為 'postgres'。"
echo "👉  請記得在 .env 檔案中設定 DB_PASSWORD=postgres"

# --- 檢查服務狀態 ---
# 使用 pg_isready 工具檢查 PostgreSQL 是否準備好接受連線
echo "ℹ️  正在檢查 PostgreSQL 服務狀態..."
if pg_isready -q; then
    echo "✅  PostgreSQL 正在運行並準備好接受連線。"
else
    echo "❌  PostgreSQL 啟動失敗或未準備好。"
    echo "   請檢查 PostgreSQL 日誌以進行排錯:"
    # 顯示日誌以幫助排錯
    tail -n 30 /var/log/postgresql/postgresql-*.log || true
    exit 1
fi

echo "✅  PostgreSQL 安裝與設定完成。"