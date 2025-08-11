#!/bin/bash
#
# Agentic RAG System - 安裝與設定腳本
#

# 遇到錯誤時立即退出
set -e

# --- 步驟 0: 更新系統套件並安裝必要的開發工具 ---
echo "🔄  正在更新 apt 套件列表..."
apt-get update

echo "🛠️  正在安裝 build-essential, libpq-dev, python3-dev, pkg-config..."
apt-get install -y build-essential libpq-dev python3-dev pkg-config

# --- 步驟 1: 安裝 Python 依賴 ---
echo "📦  正在從 requirements.txt 安裝 Python 依賴..."

# 使用 pip 安裝所有依賴
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "✅  所有 Python 依賴安裝完成。"

# --- 步驟 2: 設定 crawl4ai ---
echo "
🤖  正在設定 crawl4ai，這將會下載必要的瀏覽器..."

# 執行 crawl4ai 的設定命令
# 這會下載 Playwright 的瀏覽器，是執行爬蟲所必需的
crawl4ai-setup

echo "✅  crawl4ai 設定完成。"

# --- 完成 ---
echo "
🎉  專案環境安裝與設定全部完成！"
echo "現在您可以開始使用 make 命令 (例如: make run-pipeline) 來執行工作流程。"