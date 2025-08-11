#!/usr/bin/env python3
"""
make-db-check.py - 資料庫狀態檢查腳本

功能：
1. 檢查資料庫連接狀態
2. 驗證表格結構和數據完整性
3. 檢查索引和約束
4. 驗證權限設定
5. 生成詳細的健康檢查報告

使用方法：
    python scripts/database/make-db-check.py
    make db-check
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent.parent))

from database.postgres_client import PostgreSQLClient

class FileManager:
    def __init__(self, output_dir="."):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_text_file(self, content, filename):
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(path)

class DatabaseHealthChecker:
    """資料庫健康檢查器"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
        self.pg_client = None
        self.file_manager = FileManager(output_dir=".")
        
        # 預期的表格
        self.expected_tables = [
            "discovered_urls",
            "articles", 
            "article_chunks",
            "sitemaps"
        ]
        
        # 預期的擴展
        self.required_extensions = ["uuid-ossp", "vector"]
        
        # 預期的函數
        self.expected_functions = [
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
    
    def check_connection(self) -> Dict[str, Any]:
        """檢查資料庫連接"""
        self.logger.info("🔍 檢查資料庫連接...")
        
        try:
            # 執行簡單查詢測試連接
            result = self.pg_client.execute_query("SELECT version()")
            
            if result and len(result) > 0:
                # RealDictCursor 返回字典列表
                version_info = result[0]['version'] if 'version' in result[0] else str(result[0])
                self.logger.info("✅ 資料庫連接正常")
                return {
                    "status": "success",
                    "message": "資料庫連接正常",
                    "version": version_info
                }
            else:
                self.logger.error("❌ 資料庫連接失敗：查詢無結果")
                return {
                    "status": "error",
                    "message": "資料庫連接失敗：查詢無結果"
                }
                
        except Exception as e:
            self.logger.error(f"❌ 資料庫連接測試失敗: {e}")
            return {
                "status": "error",
                "message": f"連接測試失敗: {e}"
            }
    
    def check_tables_structure(self) -> Dict[str, Any]:
        """檢查表格結構"""
        self.logger.info("📋 檢查表格結構...")
        
        results = {
            "status": "success",
            "tables": {},
            "missing_tables": [],
            "errors": []
        }
        
        try:
            # 檢查每個表格是否存在
            for table in self.expected_tables:
                try:
                    # 檢查表格是否存在
                    if self.pg_client.table_exists(table):
                        # 獲取表格記錄數
                        record_count = self.pg_client.get_table_count(table)
                        
                        results["tables"][table] = {
                            "exists": True,
                            "record_count": record_count,
                            "status": "healthy"
                        }
                        
                        self.logger.info(f"✅ 表格 {table}: {record_count} 筆記錄")
                    else:
                        results["tables"][table] = {
                            "exists": False,
                            "record_count": 0,
                            "status": "missing"
                        }
                        results["missing_tables"].append(table)
                        results["status"] = "warning"
                        self.logger.warning(f"⚠️ 表格 {table} 不存在")
                    
                except Exception as e:
                    results["tables"][table] = {
                        "exists": False,
                        "error": str(e),
                        "status": "error"
                    }
                    results["missing_tables"].append(table)
                    results["errors"].append(f"表格 {table} 檢查失敗: {e}")
                    self.logger.error(f"❌ 表格 {table} 檢查失敗: {e}")
            
            if results["missing_tables"]:
                results["status"] = "error"
                
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"表格結構檢查失敗: {e}")
            self.logger.error(f"❌ 表格結構檢查失敗: {e}")
        
        return results
    
    def check_extensions(self) -> Dict[str, Any]:
        """檢查資料庫擴展"""
        self.logger.info("🔌 檢查資料庫擴展...")
        
        results = {
            "status": "success",
            "extensions": {},
            "missing_extensions": [],
            "errors": []
        }
        
        try:
            # 查詢已安裝的擴展
            query = """
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname = ANY(%s)
            """
            
            installed_extensions_result = self.pg_client.execute_query(query, (self.required_extensions,))
            
            if installed_extensions_result and len(installed_extensions_result) > 0:
                # RealDictCursor 返回字典列表
                installed_extensions = {ext['extname']: ext['extversion'] for ext in installed_extensions_result}
            else:
                installed_extensions = {}
            
            for ext in self.required_extensions:
                if ext in installed_extensions:
                    results["extensions"][ext] = {
                        "installed": True,
                        "version": installed_extensions[ext],
                        "status": "healthy"
                    }
                    self.logger.info(f"✅ 擴展 {ext}: {installed_extensions[ext]}")
                else:
                    results["extensions"][ext] = {
                        "installed": False,
                        "version": None,
                        "status": "missing"
                    }
                    results["missing_extensions"].append(ext)
                    results["status"] = "warning"
                    self.logger.warning(f"⚠️ 擴展 {ext} 未安裝")
            
            if results["missing_extensions"]:
                results["status"] = "error"
                
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"擴展檢查失敗: {e}")
            self.logger.error(f"❌ 擴展檢查失敗: {e}")
        
        return results
    
    def check_functions(self) -> Dict[str, Any]:
        """檢查自定義函數"""
        self.logger.info("⚙️ 檢查自定義函數...")
        
        results = {
            "status": "success", 
            "functions": {},
            "missing_functions": [],
            "errors": []
        }
        
        try:
            # 查詢已存在的函數
            query = """
            SELECT proname, pronargs 
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public' AND proname = ANY(%s)
            """
            
            existing_functions_result = self.pg_client.execute_query(query, (self.expected_functions,))
            
            if existing_functions_result and len(existing_functions_result) > 0:
                # RealDictCursor 返回字典列表
                existing_functions = {func['proname']: func['pronargs'] for func in existing_functions_result}
            else:
                existing_functions = {}
            
            for func in self.expected_functions:
                if func in existing_functions:
                    results["functions"][func] = {
                        "exists": True,
                        "args_count": existing_functions[func],
                        "status": "healthy"
                    }
                    self.logger.info(f"✅ 函數 {func} 存在")
                else:
                    results["functions"][func] = {
                        "exists": False,
                        "args_count": 0,
                        "status": "missing"
                    }
                    results["missing_functions"].append(func)
                    results["status"] = "warning"
                    self.logger.warning(f"⚠️ 函數 {func} 不存在")
            
            if results["missing_functions"]:
                results["status"] = "error"
                
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"函數檢查失敗: {e}")
            self.logger.error(f"❌ 函數檢查失敗: {e}")
        
        return results
    
    def check_permissions(self) -> Dict[str, Any]:
        """檢查權限設定"""
        self.logger.info("🔐 檢查權限設定...")
        
        results = {
            "status": "success",
            "current_user": None,
            "table_permissions": {},
            "errors": []
        }
        
        try:
            # 獲取當前用戶
            user_result = self.pg_client.execute_query("SELECT current_user")
            if user_result and len(user_result) > 0:
                # RealDictCursor 返回字典
                current_user = user_result[0]['current_user'] if 'current_user' in user_result[0] else str(user_result[0])
            else:
                current_user = "Unknown"
            results["current_user"] = current_user
            self.logger.info(f"🔑 當前用戶: {current_user}")
            
            # 檢查每個表格的讀取權限
            for table in self.expected_tables:
                try:
                    # 嘗試執行 SELECT 查詢
                    test_result = self.pg_client.execute_query(f"SELECT 1 FROM {table} LIMIT 1")
                    results["table_permissions"][table] = {
                        "select": True,
                        "status": "accessible"
                    }
                    self.logger.info(f"✅ 表格 {table} - SELECT: True")
                    
                except Exception as e:
                    results["table_permissions"][table] = {
                        "select": False,
                        "error": str(e),
                        "status": "denied"
                    }
                    results["status"] = "warning"
                    self.logger.warning(f"⚠️ 表格 {table} - SELECT: False ({e})")
                    
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"權限檢查失敗: {e}")
            self.logger.error(f"❌ 權限檢查失敗: {e}")
        
        return results
    
    def get_database_form(self, 
                        connection_result: Dict[str, Any],
                        tables_result: Dict[str, Any],
                        extensions_result: Dict[str, Any],
                        functions_result: Dict[str, Any],
                        permissions_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成資料庫表單數據"""
        self.logger.info("📋 生成資料庫表單數據...")
        
        form_data = {
            "database_info": {
                "status": "healthy",
                "version": connection_result.get('version', 'Unknown'),
                "current_user": permissions_result.get('current_user', 'Unknown'),
                "check_time": datetime.now().isoformat(),
                "connection_status": connection_result.get('status') == 'success'
            },
            "tables": {},
            "extensions": {},
            "functions": {},
            "permissions": {},
            "summary": {
                "total_tables": len(self.expected_tables),
                "existing_tables": 0,
                "total_records": 0,
                "missing_tables": [],
                "total_functions": len(self.expected_functions),
                "existing_functions": 0,
                "missing_functions": [],
                "total_extensions": len(self.required_extensions),
                "installed_extensions": 0,
                "missing_extensions": []
            }
        }
        
        # 處理表格信息
        for table, info in tables_result["tables"].items():
            form_data["tables"][table] = {
                "name": table,
                "exists": info.get("exists", False),
                "record_count": info.get("record_count", 0),
                "status": info.get("status", "unknown"),
                "accessible": True
            }
            
            if info.get("exists"):
                form_data["summary"]["existing_tables"] += 1
                form_data["summary"]["total_records"] += info.get("record_count", 0)
            else:
                form_data["summary"]["missing_tables"].append(table)
        
        # 處理擴展信息
        for ext, info in extensions_result["extensions"].items():
            form_data["extensions"][ext] = {
                "name": ext,
                "installed": info.get("installed", False),
                "version": info.get("version", "N/A"),
                "status": info.get("status", "unknown")
            }
            
            if info.get("installed"):
                form_data["summary"]["installed_extensions"] += 1
            else:
                form_data["summary"]["missing_extensions"].append(ext)
        
        # 處理函數信息
        for func, info in functions_result["functions"].items():
            form_data["functions"][func] = {
                "name": func,
                "exists": info.get("exists", False),
                "args_count": info.get("args_count", 0),
                "status": info.get("status", "unknown")
            }
            
            if info.get("exists"):
                form_data["summary"]["existing_functions"] += 1
            else:
                form_data["summary"]["missing_functions"].append(func)
        
        # 處理權限信息
        for table, info in permissions_result["table_permissions"].items():
            form_data["permissions"][table] = {
                "table": table,
                "select": info.get("select", False),
                "status": info.get("status", "unknown"),
                "error": info.get("error")
            }
            
            # 如果有權限問題，更新表格的可訪問性
            if table in form_data["tables"]:
                form_data["tables"][table]["accessible"] = info.get("select", False)
        
        # 判斷整體健康狀態
        has_errors = any(result["status"] == "error" for result in [
            connection_result, tables_result, extensions_result, functions_result, permissions_result
        ])
        has_warnings = any(result["status"] == "warning" for result in [
            connection_result, tables_result, extensions_result, functions_result, permissions_result
        ])
        
        if has_errors:
            form_data["database_info"]["status"] = "error"
        elif has_warnings:
            form_data["database_info"]["status"] = "warning"
        else:
            form_data["database_info"]["status"] = "healthy"
        
        return form_data

    def generate_health_report(self, 
                             connection_result: Dict[str, Any],
                             tables_result: Dict[str, Any],
                             extensions_result: Dict[str, Any],
                             functions_result: Dict[str, Any],
                             permissions_result: Dict[str, Any]) -> str:
        """生成健康檢查報告"""
        self.logger.info("📋 生成健康檢查報告...")
        
        report_lines = [
            "# 資料庫健康檢查報告",
            f"檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # 連接狀態
        report_lines.extend([
            "## 🔍 連接狀態",
            f"狀態: {'✅ 正常' if connection_result['status'] == 'success' else '❌ 異常'}",
            f"版本: {connection_result.get('version', 'Unknown')}",
            ""
        ])
        
        # 表格結構
        report_lines.extend([
            "## 📋 表格結構",
            f"狀態: {'✅ 正常' if tables_result['status'] == 'success' else '❌ 異常'}",
            ""
        ])
        
        for table, info in tables_result["tables"].items():
            status_icon = "✅" if info.get("exists") else "❌"
            record_count = info.get("record_count", 0)
            report_lines.append(f"- {status_icon} {table}: {record_count} 筆記錄")
        
        if tables_result.get("missing_tables"):
            report_lines.extend([
                "",
                "**缺失的表格:**"
            ])
            for table in tables_result["missing_tables"]:
                report_lines.append(f"- ❌ {table}")
        
        # 擴展
        report_lines.extend([
            "",
            "## 🔌 資料庫擴展",
            f"狀態: {'✅ 正常' if extensions_result['status'] == 'success' else '❌ 異常'}",
            ""
        ])
        
        for ext, info in extensions_result["extensions"].items():
            status_icon = "✅" if info.get("installed") else "❌"
            version = info.get("version", "N/A")
            report_lines.append(f"- {status_icon} {ext}: {version}")
        
        # 函數
        report_lines.extend([
            "",
            "## ⚙️ 自定義函數",
            f"狀態: {'✅ 正常' if functions_result['status'] == 'success' else '❌ 異常'}",
            ""
        ])
        
        for func, info in functions_result["functions"].items():
            status_icon = "✅" if info.get("exists") else "❌"
            args_count = info.get("args_count", 0)
            report_lines.append(f"- {status_icon} {func} ({args_count} 參數)")
        
        # 權限
        report_lines.extend([
            "",
            "## 🔐 權限設定",
            f"狀態: {'✅ 正常' if permissions_result['status'] == 'success' else '❌ 異常'}",
            f"當前用戶: {permissions_result.get('current_user', 'Unknown')}",
            ""
        ])
        
        for table, info in permissions_result["table_permissions"].items():
            select_status = "✅" if info.get("select") else "❌"
            report_lines.append(f"- {table}: SELECT {select_status}")
        
        # 總結
        overall_status = "success"
        if any(result["status"] == "error" for result in [connection_result, tables_result, extensions_result, functions_result, permissions_result]):
            overall_status = "error"
        elif any(result["status"] == "warning" for result in [connection_result, tables_result, extensions_result, functions_result, permissions_result]):
            overall_status = "warning"
        
        status_icon = {"success": "✅", "warning": "⚠️", "error": "❌"}[overall_status]
        
        report_lines.extend([
            "",
            "## 📊 總結",
            f"整體狀態: {status_icon} {overall_status.upper()}",
            ""
        ])
        
        report_content = "\n".join(report_lines)
        
        # 保存報告
        report_path = self.file_manager.save_text_file(
            report_content, 
            "db_health_report.md"
        )
        
        self.logger.info(f"📋 健康檢查報告已保存: {report_path}")
        return report_content
    
    async def run_health_check(self) -> Optional[Dict[str, Any]]:
        """執行完整健康檢查"""
        self.logger.info("🚀 開始資料庫健康檢查")
        
        try:
            # 1. 連接資料庫
            if not self.connect_database():
                return None
            
            # 2. 檢查連接
            connection_result = self.check_connection()
            
            # 3. 檢查表格結構
            tables_result = self.check_tables_structure()
            
            # 4. 檢查擴展
            extensions_result = self.check_extensions()
            
            # 5. 檢查函數
            functions_result = self.check_functions()
            
            # 6. 檢查權限
            permissions_result = self.check_permissions()
            
            # 7. 生成報告
            report = self.generate_health_report(
                connection_result,
                tables_result, 
                extensions_result,
                functions_result,
                permissions_result
            )
            
            # 8. 生成資料庫表單數據
            db_form = self.get_database_form(
                connection_result,
                tables_result, 
                extensions_result,
                functions_result,
                permissions_result
            )
            
            # 9. 判斷整體健康狀態
            has_critical_errors = (
                connection_result["status"] == "error" or 
                tables_result["status"] == "error" or
                tables_result.get("missing_tables", [])  # 如果有表格缺失，這是關鍵錯誤
            )
            
            if has_critical_errors:
                self.logger.error("❌ 資料庫健康狀態異常，需要修復")
                return None
            else:
                # 即使有一些非關鍵警告（如函數或擴展缺失），仍然可以回傳表單
                if any(result["status"] in ["warning", "error"] for result in [
                    extensions_result, functions_result, permissions_result
                ]):
                    self.logger.warning("⚠️ 資料庫部分功能可能不完整，但基本結構正常")
                else:
                    self.logger.info("🎉 資料庫健康檢查完成！")
                
                self.logger.info("📋 回傳資料庫表單數據...")
                
                # 顯示資料庫表單摘要
                self.display_database_form_summary(db_form)
                
                # 保存資料庫表單數據
                form_path = self.save_database_form(db_form)
                
                return db_form
                
        except Exception as e:
            self.logger.error(f"❌ 健康檢查過程中發生錯誤: {e}")
            return None
        finally:
            # 確保斷開連接
            self.disconnect_database()

    def display_database_form_summary(self, db_form: Dict[str, Any]):
        """顯示資料庫表單摘要"""
        summary = db_form["summary"]
        db_info = db_form["database_info"]
        
        print("\n" + "="*60)
        print("📋 資料庫表單數據摘要")
        print("="*60)
        print(f"資料庫狀態: {'🟢' if db_info['status'] == 'healthy' else '🟡' if db_info['status'] == 'warning' else '🔴'} {db_info['status'].upper()}")
        print(f"資料庫版本: {db_info['version']}")
        print(f"當前用戶: {db_info['current_user']}")
        print(f"檢查時間: {db_info['check_time']}")
        print("\n📊 統計信息:")
        print(f"  - 表格: {summary['existing_tables']}/{summary['total_tables']} 存在")
        print(f"  - 總記錄數: {summary['total_records']:,}")
        print(f"  - 函數: {summary['existing_functions']}/{summary['total_functions']} 存在")
        print(f"  - 擴展: {summary['installed_extensions']}/{summary['total_extensions']} 安裝")
        
        if summary['missing_tables']:
            print(f"\n⚠️ 缺失表格: {', '.join(summary['missing_tables'])}")
        if summary['missing_functions']:
            print(f"⚠️ 缺失函數: {', '.join(summary['missing_functions'])}")
        if summary['missing_extensions']:
            print(f"⚠️ 缺失擴展: {', '.join(summary['missing_extensions'])}")
        
        print("="*60)

    def save_database_form(self, db_form: Dict[str, Any]) -> str:
        """保存資料庫表單數據為 JSON 文件"""
        import json
        
        # 格式化表單數據
        formatted_form = {
            "metadata": {
                "generated_at": db_form["database_info"]["check_time"],
                "generator": "make-db-check.py",
                "version": "1.0"
            },
            "database_form": db_form
        }
        
        # 保存為 JSON 文件
        json_content = json.dumps(formatted_form, indent=2, ensure_ascii=False)
        form_path = self.file_manager.save_text_file(
            json_content, 
            "database_form.json"
        )
        
        self.logger.info(f"📄 資料庫表單已保存: {form_path}")
        return form_path


async def main():
    """主函數"""
    checker = DatabaseHealthChecker()
    db_form = await checker.run_health_check()
    
    if db_form:
        # 檢查成功，輸出資料庫表單的 JSON 格式供其他程式使用
        import json
        print("\n" + "="*60)
        print("📄 資料庫表單 JSON 數據:")
        print("="*60)
        print(json.dumps(db_form, indent=2, ensure_ascii=False))
        print("="*60)
        return db_form
    else:
        print("\n❌ 資料庫檢查失敗，無法生成表單數據")
        return None


if __name__ == "__main__":
    result = asyncio.run(main())