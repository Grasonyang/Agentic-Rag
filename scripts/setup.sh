#!/bin/bash
# Agentic RAG System - 安裝與設定腳本

set -e

# Ensure .env exists so Makefile targets depending on it won't fail
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝  Found .env.example -> creating .env"
        cp .env.example .env
    elif [ -f .env.template ]; then
        echo "📝  Found .env.template -> creating .env"
        cp .env.template .env
    else
        echo "⚠️  No .env.example or .env.template found, creating minimal .env"
        cat > .env <<'EOF'
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=postgres
EOF
    fi
fi

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
if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start postgresql || echo "⚠️  無法啟動 PostgreSQL 服務，請確認權限。"
elif command -v service >/dev/null 2>&1; then
    sudo service postgresql start || echo "⚠️  無法啟動 PostgreSQL 服務，請確認權限。"
else
    echo "⚠️  找不到 systemctl 或 service 指令，跳過啟動步驟。"
fi

sleep 5

# 僅在服務成功啟動時設定密碼
if pg_isready -q; then
    echo "🔑  正在為 'postgres' 使用者設定預設密碼..."
    sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';" || true
    echo "ℹ️  已將 'postgres' 使用者的密碼設定為 'postgres'。"
    echo "👉  請記得在 .env 檔案中設定 DB_PASSWORD=postgres"
    echo "✅  PostgreSQL 正在運行並準備好接受連線。"
else
    echo "⚠️  PostgreSQL 未啟動，略過密碼設定。"
fi

echo "✅  PostgreSQL 安裝與設定完成。"
