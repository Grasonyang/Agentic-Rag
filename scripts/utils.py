#!/usr/bin/env python3
"""
utils.py - 腳本工具類別

提供通用的腳本執行功能和工具
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional


class FileManager:
    """文件管理器"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
    
    def save_text_file(self, content: str, filename: str) -> str:
        """保存文本文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = Path(filename).stem
        extension = Path(filename).suffix
        
        # 如果沒有時間戳，添加時間戳
        if timestamp not in filename:
            filename_with_timestamp = f"{base_name}_{timestamp}{extension}"
        else:
            filename_with_timestamp = filename
        
        file_path = self.output_dir / filename_with_timestamp
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)


class ScriptRunner:
    """腳本執行器基類"""
    
    def __init__(self, script_name: str):
        self.script_name = script_name
        self.start_time = datetime.now()
        
        # 設置日誌
        self.logger = self._setup_logger()
        
        # 設置文件管理器
        self.file_manager = FileManager(str(Path(__file__).parent))
        
        # 記錄腳本開始
        self.logger.info(f"=== {script_name} 腳本開始執行 ===")
        self.logger.info(f"日誌文件: {self._get_log_file_path()}")
    
    def _setup_logger(self) -> logging.Logger:
        """設置日誌記錄器"""
        logger = logging.getLogger(self.script_name)
        logger.setLevel(logging.INFO)
        
        # 清除現有的處理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 創建日誌目錄
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 文件處理器
        log_file = self._get_log_file_path()
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 控制台處理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 設置格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _get_log_file_path(self) -> str:
        """獲取日誌文件路徑"""
        log_dir = Path(__file__).parent / "logs"
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        return str(log_dir / f"{self.script_name}_{timestamp}.log")
    
    def post_run_cleanup(self, success: bool):
        """腳本執行後的清理工作"""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        if success:
            self.logger.info(f"=== {self.script_name} 腳本執行成功 ===")
        else:
            self.logger.info(f"=== {self.script_name} 腳本執行失敗 ===")
        
        self.logger.info(f"執行時間: {duration.total_seconds():.2f} 秒")
        
        # 輸出日誌文件位置
        log_file = self._get_log_file_path()
        print(f"\n📋 詳細日誌已保存到: {log_file}")
        
        # 如果失敗，顯示最後幾行日誌
        if not success:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if len(lines) > 10:
                        print("\n📝 最後幾行日誌:")
                        for line in lines[-5:]:
                            print(f"  {line.strip()}")
            except Exception:
                pass
