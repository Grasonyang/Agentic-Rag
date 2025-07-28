#!/usr/bin/env python3
"""
make-clear.py - 清空資料庫腳本

功能：
1. 安全地清空所有表格數據
2. 保留表格結構和索引
3. 提供確認機制防止誤操作
4. 記錄清理過程和結果
5. 處理外鍵約束問題

使用方法：
    python scripts/database/make-clear.py
    python scripts/database/make-clear.py --force  # 跳過確認
    make db-clear
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.utils import ScriptRunner
from database.postgres_client import PostgreSQLClient


class DatabaseCleaner(ScriptRunner):
    """資料庫清理器"""
    
    def __init__(self, force: bool = False):
        super().__init__("db_cleaner")
        self.force = force
        self.pg_client = None
        
        # 按照外鍵依賴順序定義清理順序
        self.tables_order = [
            "article_chunks",    # 依賴 articles
            "articles",          # 依賴 discovered_urls
            "discovered_urls",   # 獨立表格
            "sitemaps"          # 獨立表格
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
    
    def get_table_stats(self) -> Dict[str, int]:
        """獲取表格統計信息"""
        self.logger.info("📊 獲取表格統計信息...")
        
        stats = {}
        total_records = 0
        
        for table in self.tables_order:
            try:
                count = self.pg_client.get_table_count(table)
                stats[table] = count
                total_records += count
                self.logger.info(f"  - {table}: {count} 筆記錄")
            except Exception as e:
                self.logger.error(f"❌ 無法獲取表格 {table} 統計: {e}")
                stats[table] = 0
        
        stats["total"] = total_records
        self.logger.info(f"📈 總計: {total_records} 筆記錄")
        
        return stats
    
    def confirm_deletion(self, stats: Dict[str, int]) -> bool:
        """確認刪除操作"""
        if self.force:
            self.logger.info("🔥 強制模式：跳過確認")
            return True
        
        if stats["total"] == 0:
            self.logger.info("ℹ️ 資料庫已經是空的")
            return True
        
        print("\n" + "="*60)
        print("⚠️  警告：即將清空資料庫")
        print("="*60)
        print(f"總記錄數: {stats['total']}")
        print("\n詳細統計:")
        for table, count in stats.items():
            if table != "total" and count > 0:
                print(f"  - {table}: {count} 筆記錄")
        print("\n❗ 此操作不可逆轉！")
        print("="*60)
        
        while True:
            response = input("\n確定要清空資料庫嗎？輸入 'YES' 確認，或 'no' 取消: ").strip()
            
            if response == "YES":
                return True
            elif response.lower() in ["no", "n"]:
                return False
            else:
                print("請輸入 'YES' 或 'no'")
    
    def clear_table(self, table_name: str) -> Dict[str, Any]:
        """清空單個表格"""
        self.logger.info(f"🧹 清空表格: {table_name}")
        
        try:
            # 獲取清空前的記錄數
            before_count = self.pg_client.get_table_count(table_name)
            
            if before_count == 0:
                self.logger.info(f"ℹ️ 表格 {table_name} 已經是空的")
                return {
                    "table": table_name,
                    "status": "success",
                    "before_count": 0,
                    "after_count": 0,
                    "deleted_count": 0,
                    "message": "表格已經是空的"
                }
            
            # 臨時禁用 RLS 以確保能夠清空
            self.pg_client.disable_rls(table_name)
            
            # 執行清空操作
            if self.pg_client.clear_table(table_name):
                # 獲取清空後的記錄數
                after_count = self.pg_client.get_table_count(table_name)
                deleted_count = before_count - after_count
                
                if after_count == 0:
                    self.logger.info(f"✅ 表格 {table_name} 清空成功，刪除了 {deleted_count} 筆記錄")
                    return {
                        "table": table_name,
                        "status": "success",
                        "before_count": before_count,
                        "after_count": after_count,
                        "deleted_count": deleted_count,
                        "message": f"成功刪除 {deleted_count} 筆記錄"
                    }
                else:
                    self.logger.warning(f"⚠️ 表格 {table_name} 部分清空，剩餘 {after_count} 筆記錄")
                    return {
                        "table": table_name,
                        "status": "partial",
                        "before_count": before_count,
                        "after_count": after_count,
                        "deleted_count": deleted_count,
                        "message": f"部分刪除，剩餘 {after_count} 筆記錄"
                    }
            else:
                return {
                    "table": table_name,
                    "status": "error",
                    "before_count": before_count,
                    "after_count": before_count,
                    "deleted_count": 0,
                    "message": "清空操作失敗"
                }
                
        except Exception as e:
            self.logger.error(f"❌ 清空表格 {table_name} 失敗: {e}")
            return {
                "table": table_name,
                "status": "error",
                "before_count": 0,
                "after_count": 0,
                "deleted_count": 0,
                "error": str(e),
                "message": f"清空失敗: {e}"
            }
    
    def reset_sequences(self) -> List[Dict[str, Any]]:
        """重置序列（如果需要）"""
        self.logger.info("🔄 檢查序列重置...")
        
        results = []
        
        try:
            # 對於使用 UUID 的表格，通常不需要重置序列
            # 但如果有其他自增字段，可以在這裡處理
            
            # 這裡可以添加序列重置邏輯
            # 例如：ALTER SEQUENCE sequence_name RESTART WITH 1;
            
            self.logger.info("ℹ️ 當前架構使用 UUID，無需重置序列")
            
            results.append({
                "action": "sequence_reset",
                "status": "skipped",
                "message": "使用 UUID，無需重置序列"
            })
            
        except Exception as e:
            self.logger.error(f"❌ 序列重置檢查失敗: {e}")
            results.append({
                "action": "sequence_reset",
                "status": "error",
                "error": str(e)
            })
        
        return results
    
    def verify_cleanup(self) -> Dict[str, Any]:
        """驗證清理結果"""
        self.logger.info("🔍 驗證清理結果...")
        
        verification = {
            "status": "success",
            "tables": {},
            "total_remaining": 0,
            "errors": []
        }
        
        try:
            for table in self.tables_order:
                try:
                    count = self.pg_client.get_table_count(table)
                    verification["tables"][table] = count
                    verification["total_remaining"] += count
                    
                    if count > 0:
                        self.logger.warning(f"⚠️ 表格 {table} 仍有 {count} 筆記錄")
                    else:
                        self.logger.info(f"✅ 表格 {table} 已清空")
                        
                except Exception as e:
                    verification["errors"].append(f"表格 {table} 驗證失敗: {e}")
                    self.logger.error(f"❌ 表格 {table} 驗證失敗: {e}")
            
            if verification["total_remaining"] == 0 and not verification["errors"]:
                self.logger.info("🎉 資料庫清空驗證成功！")
            elif verification["total_remaining"] > 0:
                verification["status"] = "partial"
                self.logger.warning(f"⚠️ 資料庫部分清空，剩餘 {verification['total_remaining']} 筆記錄")
            else:
                verification["status"] = "error"
                self.logger.error("❌ 資料庫清空驗證失敗")
                
        except Exception as e:
            verification["status"] = "error"
            verification["errors"].append(f"驗證過程失敗: {e}")
            self.logger.error(f"❌ 驗證過程失敗: {e}")
        
        return verification
    
    def generate_cleanup_report(self, 
                              before_stats: Dict[str, int],
                              cleanup_results: List[Dict[str, Any]],
                              verification: Dict[str, Any]) -> str:
        """生成清理報告"""
        self.logger.info("📋 生成清理報告...")
        
        report_lines = [
            "# 資料庫清理報告",
            f"清理時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 清理前統計"
        ]
        
        for table, count in before_stats.items():
            if table != "total":
                report_lines.append(f"- {table}: {count} 筆記錄")
        
        report_lines.extend([
            f"- **總計**: {before_stats.get('total', 0)} 筆記錄",
            "",
            "## 清理結果"
        ])
        
        total_deleted = 0
        for result in cleanup_results:
            if result.get("deleted_count"):
                total_deleted += result["deleted_count"]
            
            status_icon = {"success": "✅", "partial": "⚠️", "error": "❌"}.get(
                result.get("status"), "❓"
            )
            
            table = result.get("table", "unknown")
            deleted = result.get("deleted_count", 0)
            message = result.get("message", "")
            
            report_lines.append(f"- {status_icon} {table}: {deleted} 筆記錄已刪除 - {message}")
        
        report_lines.extend([
            f"- **總刪除**: {total_deleted} 筆記錄",
            "",
            "## 清理後驗證"
        ])
        
        for table, count in verification.get("tables", {}).items():
            status_icon = "✅" if count == 0 else "⚠️"
            report_lines.append(f"- {status_icon} {table}: {count} 筆記錄")
        
        verification_status = verification.get("status", "unknown")
        status_icon = {"success": "✅", "partial": "⚠️", "error": "❌"}.get(verification_status, "❓")
        
        report_lines.extend([
            f"- **驗證結果**: {status_icon} {verification_status}",
            f"- **剩餘記錄**: {verification.get('total_remaining', 0)}",
            ""
        ])
        
        if verification.get("errors"):
            report_lines.append("## 錯誤記錄")
            for error in verification["errors"]:
                report_lines.append(f"- ❌ {error}")
        
        report_content = "\n".join(report_lines)
        
        # 保存報告
        report_path = self.file_manager.save_text_file(
            report_content, 
            "db_cleanup_report.md"
        )
        
        self.logger.info(f"📋 清理報告已保存: {report_path}")
        return report_content
    
    async def run_cleanup(self):
        """執行完整清理流程"""
        self.logger.info("🚀 開始資料庫清理")
        
        try:
            # 1. 連接資料庫
            if not self.connect_database():
                self.post_run_cleanup(False)
                return
            
            # 2. 獲取清理前統計
            before_stats = self.get_table_stats()
            
            # 3. 確認清理操作
            if not self.confirm_deletion(before_stats):
                self.logger.info("🚫 清理操作已取消")
                self.disconnect_database()
                self.post_run_cleanup(True)
                return
            
            # 4. 執行清理
            self.logger.info("🧹 開始清理資料庫...")
            cleanup_results = []
            
            for table in self.tables_order:
                result = self.clear_table(table)
                cleanup_results.append(result)
            
            # 5. 重置序列（如果需要）
            sequence_results = self.reset_sequences()
            cleanup_results.extend(sequence_results)
            
            # 6. 驗證清理結果
            verification = self.verify_cleanup()
            
            # 7. 生成報告
            report = self.generate_cleanup_report(before_stats, cleanup_results, verification)
            
            # 8. 判斷清理是否成功
            if verification["status"] == "success":
                self.logger.info("🎉 資料庫清理完成！")
                self.post_run_cleanup(True)
            elif verification["status"] == "partial":
                self.logger.warning("⚠️ 資料庫部分清理完成")
                self.post_run_cleanup(True)
            else:
                self.logger.error("❌ 資料庫清理失敗")
                self.post_run_cleanup(False)
                
        except Exception as e:
            self.logger.error(f"❌ 清理過程中發生錯誤: {e}")
            self.post_run_cleanup(False)
        finally:
            # 確保斷開連接
            self.disconnect_database()


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="清空資料庫")
    parser.add_argument("--force", action="store_true", help="跳過確認直接清理")
    
    args = parser.parse_args()
    
    cleaner = DatabaseCleaner(force=args.force)
    await cleaner.run_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
