#!/usr/bin/env python3
"""
專案健康檢查腳本
檢查專案的各項配置和功能是否正常
"""

import os
import sys
import subprocess
from typing import List, Tuple, Dict
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class HealthChecker:
    """專案健康檢查器"""
    
    def __init__(self):
        self.results: List[Tuple[str, bool, str]] = []
    
    def check_python_version(self) -> bool:
        """檢查 Python 版本"""
        try:
            version = sys.version_info
            if version.major >= 3 and version.minor >= 8:
                self.results.append(("Python 版本", True, f"{version.major}.{version.minor}.{version.micro}"))
                return True
            else:
                self.results.append(("Python 版本", False, f"需要 3.8+，當前: {version.major}.{version.minor}"))
                return False
        except Exception as e:
            self.results.append(("Python 版本", False, f"檢查失敗: {e}"))
            return False
    
    def check_required_files(self) -> bool:
        """檢查必要文件是否存在"""
        required_files = [
            "config.py", "embedding.py", "chunking.py", "supabase_db.py",
            "spider.py", "requirements.txt", ".env.template", "README.md"
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if not missing_files:
            self.results.append(("必要文件", True, "所有文件存在"))
            return True
        else:
            self.results.append(("必要文件", False, f"缺失: {', '.join(missing_files)}"))
            return False
    
    def check_dependencies(self) -> bool:
        """檢查依賴是否安裝"""
        try:
            # 檢查主要依賴
            import dotenv
            import supabase
            import sentence_transformers
            import crawl4ai
            
            self.results.append(("Python 依賴", True, "主要依賴已安裝"))
            return True
        except ImportError as e:
            self.results.append(("Python 依賴", False, f"缺失依賴: {e}"))
            return False
        except Exception as e:
            self.results.append(("Python 依賴", False, f"檢查失敗: {e}"))
            return False
    
    def check_environment_config(self) -> bool:
        """檢查環境配置"""
        try:
            from config import Config
            
            # 檢查 .env 文件
            env_exists = os.path.exists('.env')
            template_exists = os.path.exists('.env.template')
            
            if not env_exists and template_exists:
                self.results.append(("環境配置", False, ".env 文件不存在，請從模板創建"))
                return False
            elif not env_exists and not template_exists:
                self.results.append(("環境配置", False, "缺少環境配置文件"))
                return False
            
            # 驗證配置
            is_valid = Config.validate_config()
            if is_valid:
                self.results.append(("環境配置", True, "配置驗證通過"))
                return True
            else:
                self.results.append(("環境配置", False, "配置驗證失敗"))
                return False
                
        except Exception as e:
            self.results.append(("環境配置", False, f"檢查失敗: {e}"))
            return False
    
    def check_directories(self) -> bool:
        """檢查必要目錄"""
        required_dirs = ["ex_result", "user_data"]
        missing_dirs = []
        
        for dir_name in required_dirs:
            if not os.path.exists(dir_name):
                try:
                    os.makedirs(dir_name)
                    logger.info(f"創建目錄: {dir_name}")
                except Exception as e:
                    missing_dirs.append(f"{dir_name} ({e})")
        
        if not missing_dirs:
            self.results.append(("必要目錄", True, "所有目錄存在"))
            return True
        else:
            self.results.append(("必要目錄", False, f"問題: {', '.join(missing_dirs)}"))
            return False
    
    def check_modules(self) -> bool:
        """檢查模組功能"""
        try:
            # 測試分塊器
            from chunking import SlidingWindowChunking
            chunker = SlidingWindowChunking(window_size=5, step=3)
            chunks = chunker.chunk("測試 分塊 功能 是否 正常 運行")
            
            if len(chunks) > 0:
                self.results.append(("分塊模組", True, f"正常運行，生成 {len(chunks)} 個塊"))
            else:
                self.results.append(("分塊模組", False, "分塊功能異常"))
                return False
            
            # 測試配置模組
            from config import Config
            config_dict = Config.get_config_dict()
            if config_dict:
                self.results.append(("配置模組", True, f"正常運行，載入 {len(config_dict)} 個配置"))
            else:
                self.results.append(("配置模組", False, "配置載入失敗"))
                return False
            
            return True
            
        except Exception as e:
            self.results.append(("模組功能", False, f"檢查失敗: {e}"))
            return False
    
    def check_database_connection(self) -> bool:
        """檢查資料庫連接"""
        try:
            from supabase_db import get_supabase_client
            client = get_supabase_client()
            
            if client:
                self.results.append(("資料庫連接", True, "Supabase 客戶端創建成功"))
                return True
            else:
                self.results.append(("資料庫連接", False, "無法創建 Supabase 客戶端"))
                return False
                
        except Exception as e:
            self.results.append(("資料庫連接", False, f"檢查失敗: {e}"))
            return False
    
    def check_embedding_model(self) -> bool:
        """檢查嵌入模型（可選）"""
        try:
            from embedding import model, get_embedding_dimension
            
            if model is not None:
                dim = get_embedding_dimension()
                self.results.append(("嵌入模型", True, f"模型載入成功，維度: {dim}"))
                return True
            else:
                self.results.append(("嵌入模型", False, "模型載入失敗"))
                return False
                
        except Exception as e:
            self.results.append(("嵌入模型", False, f"檢查失敗: {e}"))
            return False
    
    def run_all_checks(self) -> Dict[str, int]:
        """運行所有檢查"""
        logger.info("🔍 開始專案健康檢查...")
        
        checks = [
            self.check_python_version,
            self.check_required_files,
            self.check_dependencies,
            self.check_directories,
            self.check_environment_config,
            self.check_modules,
            self.check_database_connection,
            # self.check_embedding_model,  # 可選檢查，可能需要較長時間
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                logger.error(f"檢查過程中發生錯誤: {e}")
        
        return self.generate_report()
    
    def generate_report(self) -> Dict[str, int]:
        """生成檢查報告"""
        passed = sum(1 for _, status, _ in self.results if status)
        failed = len(self.results) - passed
        
        print("\n" + "="*60)
        print("📊 專案健康檢查報告")
        print("="*60)
        
        for check_name, status, details in self.results:
            status_icon = "✅" if status else "❌"
            print(f"{status_icon} {check_name:<15}: {details}")
        
        print("="*60)
        print(f"📈 總結: {passed} 通過, {failed} 失敗, 總計 {len(self.results)} 項檢查")
        
        if failed == 0:
            print("🎉 恭喜！所有檢查都通過了！")
        elif failed <= 2:
            print("⚠️  有少數問題需要處理")
        else:
            print("🚨 需要解決多個問題才能正常運行")
        
        print("="*60)
        
        return {"passed": passed, "failed": failed, "total": len(self.results)}

def main():
    """主函數"""
    checker = HealthChecker()
    results = checker.run_all_checks()
    
    # 設置退出碼
    exit_code = 0 if results["failed"] == 0 else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
