# 使用官方 Python 3.12 基礎映像
FROM python:3.12-slim

# 設置工作目錄
WORKDIR /app

# 設置環境變數
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案文件
COPY . .

# 創建必要的目錄
RUN mkdir -p ex_result user_data logs

# 設置權限
RUN chmod +x install.sh

# 暴露端口（如果需要）
# EXPOSE 8000

# 設置健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from config import Config; Config.validate_config()" || exit 1

# 預設命令
CMD ["python", "test.py"]
