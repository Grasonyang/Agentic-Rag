"""
配置管理模組

職責:
- 載入專案根目錄下的 .env 檔案中的環境變數。
- 提供一個簡單的函數來執行此操作。

使用方式:
在應用程式的入口點（例如每個腳本的開頭）調用 `load_config()` 即可。
之後，在程式的任何地方都可以使用 `os.getenv('VARIABLE_NAME')` 來獲取配置。
"""

import os
import logging
from dotenv import load_dotenv

# 設置日誌
logger = logging.getLogger(__name__)

def load_config():
    """
    載入 .env 檔案到環境變數中。

    會自動尋找專案目錄中的 .env 檔案。
    如果 .env 檔案存在且成功載入，返回 True。
    """
    # `find_dotenv` 會從當前檔案位置向上搜索 .env 檔案
    # `override=True` 表示如果環境中已存在同名變數，.env 中的值會覆蓋它
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    
    if not os.path.exists(env_path):
        logger.warning(f".env 檔案未找到於: {env_path}")
        print(f"警告: .env 檔案未找到於 {env_path}。請確保您已將 .env.template 複製為 .env 並填寫了必要的配置。")
        return False

    try:
        load_dotenv(dotenv_path=env_path, override=True)
        logger.info("成功從 .env 檔案載入配置。")
        return True
    except Exception as e:
        logger.error(f"從 .env 檔案載入配置時發生錯誤: {e}")
        return False

# 在模組被導入時，可以選擇性地自動載入一次
# load_config()