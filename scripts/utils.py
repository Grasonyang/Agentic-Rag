#!/usr/bin/env python3
"""
utils.py - 腳本工具類別

提供通用的腳本執行功能和工具
為所有 get 腳本提供統一的日誌記錄、錯誤處理和文件管理
"""

import os
import sys
import logging
import argparse
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, Dict, List
from abc import ABC, abstractmethod

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))


class FileManager:
    """文件管理器"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / "output"
        self.logs_dir = self.base_dir / "logs"
        
        # 創建必要目錄
        self.output_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
    
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
    
    def save_json_file(self, data: Dict, filename: str) -> str:
        """保存 JSON 文件"""
        import json
        json_content = json.dumps(data, ensure_ascii=False, indent=2)
        return self.save_text_file(json_content, filename)
    
    def read_file(self, filepath: str) -> str:
        """讀取文件內容"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def file_exists(self, filepath: str) -> bool:
        """檢查文件是否存在"""
        return Path(filepath).exists()


class ScriptStats:
    """腳本統計信息"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = None
        self.success_count = 0
        self.failed_count = 0
        self.total_count = 0
        self.errors = []
        self.warnings = []
        self.custom_stats = {}
    
    def add_success(self):
        """添加成功計數"""
        self.success_count += 1
        self.total_count += 1
    
    def add_failure(self, error_msg: str = None):
        """添加失敗計數"""
        self.failed_count += 1
        self.total_count += 1
        if error_msg:
            self.errors.append(error_msg)
    
    def add_warning(self, warning_msg: str):
        """添加警告"""
        self.warnings.append(warning_msg)
    
    def set_custom_stat(self, key: str, value: Any):
        """設置自定義統計"""
        self.custom_stats[key] = value
    
    def get_duration(self) -> float:
        """獲取執行時間"""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def get_success_rate(self) -> float:
        """獲取成功率"""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100


class ScriptRunner(ABC):
    """腳本執行器基類"""
    
    def __init__(self, script_name: str):
        self.script_name = script_name
        self.stats = ScriptStats()
        
        # 設置日誌
        self.logger = self._setup_logger()
        
        # 設置文件管理器
        self.file_manager = FileManager(str(Path(__file__).parent))
        
        # 記錄腳本開始
        self.logger.info(f"=== {script_name} 腳本開始執行 ===")
        self.logger.info(f"開始時間: {self.stats.start_time.isoformat()}")
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
        timestamp = self.stats.start_time.strftime('%Y%m%d_%H%M%S')
        return str(log_dir / f"{self.script_name}_{timestamp}.log")
    
    @abstractmethod
    def setup_arguments(self, parser: argparse.ArgumentParser):
        """設置命令行參數（子類實現）"""
        pass
    
    @abstractmethod
    async def run_script(self, args: argparse.Namespace) -> bool:
        """執行腳本主邏輯（子類實現）"""
        pass
    
    def log_progress(self, message: str, current: int = None, total: int = None):
        """記錄進度"""
        if current is not None and total is not None:
            percentage = (current / total) * 100
            progress_msg = f"[{current}/{total} ({percentage:.1f}%)] {message}"
        else:
            progress_msg = message
        
        self.logger.info(progress_msg)
        print(f"📈 {progress_msg}")
    
    def log_success(self, message: str):
        """記錄成功操作"""
        self.stats.add_success()
        self.logger.info(f"✅ {message}")
        print(f"✅ {message}")
    
    def log_error(self, message: str, exception: Exception = None):
        """記錄錯誤"""
        self.stats.add_failure(message)
        if exception:
            error_details = f"{message}: {str(exception)}"
            self.logger.error(error_details)
            self.logger.debug(traceback.format_exc())
        else:
            self.logger.error(f"❌ {message}")
        print(f"❌ {message}")
    
    def log_warning(self, message: str):
        """記錄警告"""
        self.stats.add_warning(message)
        self.logger.warning(f"⚠️ {message}")
        print(f"⚠️ {message}")
    
    def log_info(self, message: str):
        """記錄信息"""
        self.logger.info(message)
        print(f"ℹ️ {message}")
    
    def print_summary(self):
        """打印執行摘要"""
        self.stats.end_time = datetime.now()
        duration = self.stats.get_duration()
        success_rate = self.stats.get_success_rate()
        
        print(f"\n{'='*60}")
        print(f"📋 {self.script_name} 執行摘要")
        print(f"{'='*60}")
        print(f"⏱️ 執行時間: {duration:.2f} 秒")
        print(f"📊 處理統計:")
        print(f"   • 總處理數: {self.stats.total_count}")
        print(f"   • 成功數: {self.stats.success_count}")
        print(f"   • 失敗數: {self.stats.failed_count}")
        print(f"   • 成功率: {success_rate:.1f}%")
        
        if self.stats.warnings:
            print(f"⚠️ 警告數: {len(self.stats.warnings)}")
        
        # 顯示自定義統計
        if self.stats.custom_stats:
            print(f"📈 詳細統計:")
            for key, value in self.stats.custom_stats.items():
                print(f"   • {key}: {value}")
        
        # 顯示錯誤摘要（最多顯示 3 個）
        if self.stats.errors:
            print(f"\n❌ 錯誤摘要 (前 3 個):")
            for i, error in enumerate(self.stats.errors[:3], 1):
                print(f"   {i}. {error}")
            
            if len(self.stats.errors) > 3:
                print(f"   ... 還有 {len(self.stats.errors) - 3} 個錯誤")
        
        print(f"📁 日誌文件: {self._get_log_file_path()}")
        print(f"{'='*60}")
        
        # 記錄到日誌
        self.logger.info(f"執行完成 - 成功: {self.stats.success_count}, 失敗: {self.stats.failed_count}, 總耗時: {duration:.2f}s")
    
    async def run(self):
        """主執行入口"""
        success = False
        try:
            # 設置命令行參數
            parser = argparse.ArgumentParser(description=f'{self.script_name} 工具')
            self.setup_arguments(parser)
            args = parser.parse_args()
            
            # 記錄運行參數
            self.logger.info(f"運行參數: {vars(args)}")
            
            # 執行腳本邏輯
            success = await self.run_script(args)
            
        except KeyboardInterrupt:
            self.log_warning("用戶中斷執行")
            success = False
        except Exception as e:
            self.log_error("腳本執行失敗", e)
            success = False
        finally:
            # 打印摘要和清理
            self.print_summary()
            self.post_run_cleanup(success)
        
        return success
    
    def post_run_cleanup(self, success: bool):
        """腳本執行後的清理工作"""
        if success:
            self.logger.info(f"=== {self.script_name} 腳本執行成功 ===")
        else:
            self.logger.info(f"=== {self.script_name} 腳本執行失敗 ===")
        
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


# 便捷函數
def run_script(script_runner_class):
    """運行腳本的便捷函數"""
    import asyncio
    
    async def main():
        runner = script_runner_class()
        return await runner.run()
    
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 腳本運行失敗: {e}")
        sys.exit(1)
