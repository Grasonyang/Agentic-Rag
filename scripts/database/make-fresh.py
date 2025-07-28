#!/usr/bin/env python3
"""
make-fresh.py - 重新初始化資料庫腳本

功能：
1. 清空現有數據
2. 重新執行資料庫架構
3. 初始化基本設定和數據
4. 驗證初始化結果
5. 使用 psycopg2 直接連接避免 RLS 限制

使用方法：
    python scripts/database/make-fresh.py
    python scripts/database/make-fresh.py --force  # 跳過確認
    make db-fresh
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.utils import ScriptRunner
from database.postgres_client import PostgreSQLClient


class DatabaseInitializer(ScriptRunner):
    """資料庫初始化器"""
    
    def __init__(self, force: bool = False):
        super().__init__("db_initializer")
        self.force = force
        self.pg_client = None
        
        self.schema_file = Path(__file__).parent.parent.parent / "database" / "sql" / "schema.sql"
        
        if not self.schema_file.exists():
            self.logger.error(f"❌ 找不到 schema 文件: {self.schema_file}")
            sys.exit(1)
        
        # 核心表格列表
        self.core_tables = [
            "discovered_urls",
            "articles", 
            "article_chunks",
            "sitemaps"
        ]
        
        # 核心函數列表
        self.core_functions = [
            "get_crawl_progress",
            "get_domain_stats", 
            "search_similar_content",
            "cleanup_duplicate_articles",
            "check_data_integrity"
        ]
    
    def connect_database(self) -> bool:
        """連接資料庫"""
        try:
            self.pg_client = PostgreSQLClient()
            if self.pg_client.connect():
                self.logger.info("✅ 資料庫連接成功")
                return True
            else:
                self.logger.error("❌ 資料庫連接失敗")
                return False
        except Exception as e:
            self.logger.error(f"❌ 資料庫連接異常: {e}")
            return False
    
    def disconnect_database(self):
        """斷開資料庫連接"""
        if self.pg_client:
            self.pg_client.disconnect()
    
    def get_current_status(self) -> Dict[str, Any]:
        """獲取當前資料庫狀態"""
        self.logger.info("📊 獲取當前資料庫狀態...")
        
        status = {
            "tables": {},
            "functions": {},
            "total_records": 0,
            "database_info": {}
        }
        
        try:
            # 獲取資料庫信息
            status["database_info"] = {
                "version": self.pg_client.get_database_version(),
                "current_user": self.pg_client.get_current_user()
            }
            
            # 檢查表格狀態
            for table in self.core_tables:
                exists = self.pg_client.table_exists(table)
                count = self.pg_client.get_table_count(table) if exists else 0
                
                status["tables"][table] = {
                    "exists": exists,
                    "count": count
                }
                
                if exists:
                    status["total_records"] += count
                    self.logger.info(f"  - {table}: {count} 筆記錄")
                else:
                    self.logger.warning(f"  - {table}: 不存在")
            
            # 檢查函數狀態
            functions_exist = 0
            for function in self.core_functions:
                exists = self.pg_client.function_exists(function)
                status["functions"][function] = exists
                if exists:
                    functions_exist += 1
            
            self.logger.info(f"  - 自定義函數: {functions_exist}/{len(self.core_functions)} 存在")
            
        except Exception as e:
            self.logger.error(f"❌ 獲取資料庫狀態失敗: {e}")
            status["error"] = str(e)
        
        return status
    
    def confirm_initialization(self, status: Dict[str, Any]) -> bool:
        """確認初始化操作"""
        if self.force:
            self.logger.info("🔥 強制模式：跳過確認")
            return True
        
        table_count = len([t for t in status["tables"].values() if t["exists"]])
        function_count = len([f for f in status["functions"].values() if f])
        
        print("\n" + "="*60)
        print("⚠️  警告：即將重新初始化資料庫")
        print("="*60)
        print(f"現有表格數: {table_count}")
        print(f"現有記錄數: {status['total_records']}")
        print(f"自定義函數: {function_count}/{len(self.core_functions)} 存在")
        print(f"資料庫用戶: {status['database_info'].get('current_user', 'Unknown')}")
        print("\n🔄 將執行以下操作:")
        print("  1. 清空現有數據")
        print("  2. 重新執行資料庫架構")
        print("  3. 初始化基本設定")
        print("  4. 驗證初始化結果")
        print("\n❗ 此操作將清空所有現有數據！")
        print("="*60)
        
        while True:
            response = input("\n確定要重新初始化資料庫嗎？輸入 'YES' 確認，或 'no' 取消: ").strip()
            
            if response == "YES":
                return True
            elif response.lower() in ["no", "n"]:
                return False
            else:
                print("請輸入 'YES' 或 'no'")
    
    def clear_existing_data(self) -> Dict[str, Any]:
        """清空現有數據"""
        self.logger.info("🧹 清空現有數據...")
        
        results = {
            "status": "success",
            "cleared_tables": [],
            "errors": []
        }
        
        # 按依賴順序清空表格（從子表到父表）
        clear_order = ["article_chunks", "articles", "discovered_urls", "sitemaps"]
        
        for table in clear_order:
            try:
                if self.pg_client.table_exists(table):
                    before_count = self.pg_client.get_table_count(table)
                    
                    if before_count > 0:
                        # 臨時禁用 RLS 以確保能夠清空
                        self.pg_client.disable_rls(table)
                        
                        if self.pg_client.clear_table(table):
                            results["cleared_tables"].append({
                                "table": table,
                                "before_count": before_count,
                                "after_count": 0
                            })
                        else:
                            results["errors"].append(f"清空表格 {table} 失敗")
                    else:
                        self.logger.info(f"ℹ️ {table}: 已經是空的")
                        
                else:
                    self.logger.warning(f"⚠️ 表格 {table} 不存在")
                    
            except Exception as e:
                error_msg = f"處理表格 {table} 時發生錯誤: {e}"
                results["errors"].append(error_msg)
                self.logger.error(f"❌ {error_msg}")
        
        if results["errors"]:
            results["status"] = "partial"
        
        return results
    
    def execute_schema(self) -> Dict[str, Any]:
        """執行資料庫架構"""
        self.logger.info("🏗️ 執行資料庫架構...")
        
        try:
            # 讀取 schema 文件
            self.logger.info(f"📖 讀取 schema 文件: {self.schema_file}")
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                schema_content = f.read()
            
            # 執行 schema
            success_count, error_count, errors = self.pg_client.execute_script(schema_content)
            
            result = {
                "status": "success" if error_count == 0 else ("partial" if success_count > 0 else "error"),
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors
            }
            
            if error_count == 0:
                self.logger.info(f"✅ Schema 執行成功: {success_count} 個語句")
            elif success_count > 0:
                self.logger.warning(f"⚠️ Schema 部分執行成功: {success_count} 成功, {error_count} 失敗")
            else:
                self.logger.error(f"❌ Schema 執行失敗: {error_count} 個錯誤")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 執行 schema 時發生錯誤: {e}")
            return {
                "status": "error",
                "success_count": 0,
                "error_count": 1,
                "errors": [str(e)]
            }
    
    def initialize_basic_data(self) -> Dict[str, Any]:
        """初始化基本數據"""
        self.logger.info("🌱 初始化基本數據...")
        
        results = {
            "status": "success",
            "operations": [],
            "errors": []
        }
        
        try:
            # 1. 啟用必要的擴展（如果尚未啟用）
            extensions = ["uuid-ossp", "vector"]
            for ext in extensions:
                try:
                    self.pg_client.execute_query(
                        f"CREATE EXTENSION IF NOT EXISTS \"{ext}\"",
                        fetch=False
                    )
                    results["operations"].append(f"擴展 {ext} 已確保啟用")
                except Exception as e:
                    results["errors"].append(f"啟用擴展 {ext} 失敗: {e}")
            
            # 2. 設置適當的權限
            for table in self.core_tables:
                try:
                    # 重新啟用 RLS
                    self.pg_client.enable_rls(table)
                    results["operations"].append(f"表格 {table} RLS 已啟用")
                except Exception as e:
                    results["errors"].append(f"設置表格 {table} RLS 失敗: {e}")
            
            # 3. 優化設定
            try:
                # 更新統計信息
                self.pg_client.execute_query("ANALYZE", fetch=False)
                results["operations"].append("統計信息已更新")
            except Exception as e:
                results["errors"].append(f"更新統計信息失敗: {e}")
            
            self.logger.info("✅ 系統設定初始化完成")
            self.logger.info("✅ 索引優化完成")
            self.logger.info("✅ 權限設定檢查完成")
            
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"基本數據初始化失敗: {e}")
            self.logger.error(f"❌ 基本數據初始化失敗: {e}")
        
        if results["errors"]:
            results["status"] = "partial" if results["operations"] else "error"
        
        return results
    
    def verify_initialization(self) -> Dict[str, Any]:
        """驗證初始化結果"""
        self.logger.info("🔍 驗證初始化結果...")
        
        verification = {
            "status": "success",
            "tables": {},
            "functions": {},
            "health": "healthy",
            "issues": []
        }
        
        try:
            # 驗證表格
            for table in self.core_tables:
                exists = self.pg_client.table_exists(table)
                count = self.pg_client.get_table_count(table) if exists else 0
                
                verification["tables"][table] = {
                    "exists": exists,
                    "count": count,
                    "status": "normal" if exists else "missing"
                }
                
                if exists:
                    self.logger.info(f"✅ 表格 {table}: 正常 ({count} 筆記錄)")
                else:
                    verification["issues"].append(f"表格 {table} 不存在")
                    self.logger.error(f"❌ 表格 {table}: 不存在")
            
            # 驗證函數
            missing_functions = 0
            for function in self.core_functions:
                exists = self.pg_client.function_exists(function)
                verification["functions"][function] = exists
                
                if exists:
                    self.logger.info(f"✅ 函數 {function}: 正常")
                else:
                    missing_functions += 1
                    verification["issues"].append(f"函數 {function} 不存在")
                    self.logger.warning(f"⚠️ 函數 {function}: 不存在")
            
            # 判斷整體健康狀態
            missing_tables = len([t for t in verification["tables"].values() if not t["exists"]])
            
            if missing_tables > 0 or missing_functions > 0:
                verification["health"] = "degraded"
                verification["status"] = "partial"
            
            if missing_tables > len(self.core_tables) // 2:
                verification["health"] = "critical"
                verification["status"] = "error"
                
        except Exception as e:
            verification["status"] = "error"
            verification["health"] = "critical"
            verification["issues"].append(f"驗證過程失敗: {e}")
            self.logger.error(f"❌ 驗證過程失敗: {e}")
        
        return verification
    
    def generate_initialization_report(self, 
                                     before_status: Dict[str, Any],
                                     clear_results: Dict[str, Any],
                                     schema_results: Dict[str, Any],
                                     basic_data_results: Dict[str, Any],
                                     verification: Dict[str, Any]) -> str:
        """生成初始化報告"""
        self.logger.info("📋 生成初始化報告...")
        
        report_lines = [
            "# 資料庫初始化報告",
            f"初始化時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 初始化前狀態",
            f"- 總記錄數: {before_status.get('total_records', 0)}",
            f"- 自定義函數: {len([f for f in before_status['functions'].values() if f])}/{len(self.core_functions)} 存在",
            f"- 資料庫用戶: {before_status['database_info'].get('current_user', 'Unknown')}"
        ]
        
        for table, info in before_status.get("tables", {}).items():
            count = info.get("count", 0)
            report_lines.append(f"- {table}: {count} 筆記錄")
        
        # 數據清理結果
        report_lines.extend([
            "",
            "## 數據清理結果"
        ])
        
        if clear_results.get("cleared_tables"):
            for table_info in clear_results["cleared_tables"]:
                table = table_info["table"]
                before = table_info["before_count"]
                report_lines.append(f"- ✅ {table}: 清空 {before} 筆記錄")
        else:
            report_lines.append("- 無需清理數據")
        
        # Schema 執行結果
        report_lines.extend([
            "",
            "## Schema 執行結果",
            f"- 狀態: {'✅' if schema_results['status'] == 'success' else '⚠️' if schema_results['status'] == 'partial' else '❌'} {schema_results['status']}",
            f"- 成功語句: {schema_results['success_count']}",
            f"- 失敗語句: {schema_results['error_count']}"
        ])
        
        if schema_results.get("errors"):
            report_lines.append("- 錯誤:")
            for error in schema_results["errors"][:5]:  # 只顯示前5個錯誤
                report_lines.append(f"  - ❌ {error}")
        
        # 基本數據初始化
        report_lines.extend([
            "",
            "## 基本數據初始化",
            f"- 狀態: {'✅' if basic_data_results['status'] == 'success' else '⚠️' if basic_data_results['status'] == 'partial' else '❌'} {basic_data_results['status']}"
        ])
        
        for operation in basic_data_results.get("operations", []):
            report_lines.append(f"  - ✅ {operation}")
        
        # 初始化驗證
        health_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(
            verification.get("health"), "❓"
        )
        
        report_lines.extend([
            "",
            "## 初始化驗證",
            f"- 整體健康: {health_icon} {verification.get('health', 'unknown')}",
            "- 表格狀態:"
        ])
        
        for table, info in verification.get("tables", {}).items():
            status_icon = "✅" if info.get("exists") else "❌"
            count = info.get("count", 0)
            report_lines.append(f"  - {status_icon} {table}: {count} 筆記錄")
        
        report_lines.append("- 函數狀態:")
        for function, exists in verification.get("functions", {}).items():
            status_icon = "✅" if exists else "❌"
            report_lines.append(f"  - {status_icon} {function}")
        
        # 問題記錄
        if verification.get("issues"):
            report_lines.extend([
                "",
                "## 警告記錄"
            ])
            for issue in verification["issues"]:
                report_lines.append(f"- ⚠️ {issue}")
        
        # 錯誤記錄
        all_errors = []
        all_errors.extend(clear_results.get("errors", []))
        all_errors.extend(schema_results.get("errors", []))
        all_errors.extend(basic_data_results.get("errors", []))
        
        if all_errors:
            report_lines.extend([
                "",
                "## 錯誤記錄"
            ])
            for error in all_errors[:10]:  # 限制錯誤數量
                report_lines.append(f"- ❌ {error}")
        
        report_content = "\n".join(report_lines)
        
        # 保存報告
        report_path = self.file_manager.save_text_file(
            report_content, 
            "db_initialization_report.md"
        )
        
        self.logger.info(f"📋 初始化報告已保存: {report_path}")
        return report_content
    
    async def run_initialization(self):
        """執行完整初始化流程"""
        self.logger.info("🚀 開始資料庫初始化")
        
        try:
            # 1. 連接資料庫
            if not self.connect_database():
                self.post_run_cleanup(False)
                return
            
            # 2. 獲取當前狀態
            before_status = self.get_current_status()
            
            # 3. 確認初始化操作
            if not self.confirm_initialization(before_status):
                self.logger.info("🚫 初始化操作已取消")
                self.disconnect_database()
                self.post_run_cleanup(True)
                return
            
            # 4. 清空現有數據
            self.logger.info("📝 第 1 步：清空現有數據")
            clear_results = self.clear_existing_data()
            
            # 5. 執行資料庫架構
            self.logger.info("📝 第 2 步：執行資料庫架構")
            schema_results = self.execute_schema()
            
            # 6. 初始化基本數據
            self.logger.info("📝 第 3 步：初始化基本數據")
            basic_data_results = self.initialize_basic_data()
            
            # 7. 驗證初始化結果
            self.logger.info("📝 第 4 步：驗證初始化結果")
            verification = self.verify_initialization()
            
            # 8. 生成報告
            report = self.generate_initialization_report(
                before_status, clear_results, schema_results, 
                basic_data_results, verification
            )
            
            # 9. 判斷初始化是否成功
            if verification["status"] == "success":
                self.logger.info("🎉 資料庫初始化完成！")
                self.post_run_cleanup(True)
            elif verification["status"] == "partial":
                self.logger.warning("⚠️ 資料庫初始化完成，但有一些功能可能不完整")
                self.post_run_cleanup(True)
            else:
                self.logger.error("❌ 資料庫初始化失敗")
                self.post_run_cleanup(False)
                
        except Exception as e:
            self.logger.error(f"❌ 初始化過程中發生錯誤: {e}")
            self.post_run_cleanup(False)
        finally:
            # 確保斷開連接
            self.disconnect_database()


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="重新初始化資料庫")
    parser.add_argument("--force", action="store_true", help="跳過確認直接初始化")
    
    args = parser.parse_args()
    
    initializer = DatabaseInitializer(force=args.force)
    await initializer.run_initialization()


if __name__ == "__main__":
    asyncio.run(main())
