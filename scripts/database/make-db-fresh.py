import psycopg2
import shutil
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Get DB credentials
USER = os.getenv("DB_USER", "postgres")
PASSWORD = os.getenv("DB_PASSWORD", "your-super-secret-and-long-postgres-password")
HOST = os.getenv("DB_HOST", "host.docker.internal")
PORT = os.getenv("DB_PORT", "5432")
DBNAME = os.getenv("DB_NAME", "postgres")

print(f"📋 Database Configuration:")
print(f"   Host: {HOST}")
print(f"   Port: {PORT}")
print(f"   Database: {DBNAME}")
print(f"   User: {USER}")

# SQL 文件順序（可調整）
sql_files = [
    "schema_core.sql",      # 基礎類型和函數
    "schema_content.sql",   # 內容管理表格
    "schema_crawl.sql",     # 爬取管理表格
    "schema_logs.sql",      # 日誌表格
    "schema_functions.sql"  # 所有函數
]

def copy_schema_files():
    """複製 schema 檔案到當前目錄"""
    print("📋 Step 1: Copying schema files...")
    
    # 獲取當前腳本的絕對路徑，然後計算相對路徑
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent.parent
    source_dir = project_root / "database" / "sql"
    target_dir = script_dir / "schemas"
    
    # 創建目標目錄
    target_dir.mkdir(exist_ok=True)
    
    print(f"  📂 Source directory: {source_dir}")
    print(f"  📂 Target directory: {target_dir}")
    
    copied_files = []
    for fname in sql_files:
        source_file = source_dir / fname
        target_file = target_dir / fname
        
        try:
            if source_file.exists():
                shutil.copy2(source_file, target_file)
                print(f"  ✅ Copied {fname}")
                copied_files.append(str(target_file))
            else:
                print(f"  ❌ Source file not found: {source_file}")
        except Exception as e:
            print(f"  ❌ Error copying {fname}: {e}")
    
    return copied_files

def get_all_tables(cursor):
    """獲取所有用戶表格"""
    print("📋 Step 2: Getting all existing tables...")
    
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  📊 Found {len(tables)} tables: {tables}")
        return tables
        
    except Exception as e:
        print(f"  ❌ Error getting tables: {e}")
        return []

def drop_all_tables(cursor, tables):
    """清理所有表格和相關物件"""
    print("📋 Step 3: Dropping all tables and objects...")
    
    if not tables:
        print("  ℹ️  No tables to drop")
    else:
        try:
            # 先關閉外鍵約束檢查，然後一次性刪除所有表格
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f"  🗑️  Dropped {table}")
                
            print(f"  ✅ Successfully dropped {len(tables)} tables")
            
        except Exception as e:
            print(f"  ❌ Error dropping tables: {e}")
    
    # 更激進的清理方式 - 刪除整個 public schema 並重建
    try:
        print("  🧹 Performing complete schema cleanup...")
        cursor.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")
        cursor.execute("GRANT ALL ON SCHEMA public TO postgres;")
        cursor.execute("GRANT ALL ON SCHEMA public TO public;")
        print("  ✅ Schema completely reset")
        
        # 重新啟用必需的擴展
        cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("  ✅ Extensions re-enabled")
        
    except Exception as e:
        print(f"  ⚠️ Warning during schema reset: {e}")

def import_schema_files(cursor, conn, schema_files):
    """匯入 schema 檔案"""
    print("📋 Step 4: Importing schema files...")
    
    success_count = 0
    for schema_file in schema_files:
        try:
            print(f"  📂 Executing: {Path(schema_file).name}")
            
            with open(schema_file, "r", encoding="utf-8") as f:
                sql_content = f.read()
            
            # 檢查檔案內容（移除註解和空白後）
            sql_lines = [line.strip() for line in sql_content.split('\n') 
                        if line.strip() and not line.strip().startswith('--')]
            
            if not sql_lines:
                print(f"  ⏭️  Skipping file with only comments: {Path(schema_file).name}")
                continue
            
            # 直接執行整個檔案內容，讓 PostgreSQL 處理語句分割
            try:
                cursor.execute(sql_content)
                conn.commit()
                print(f"  ✅ Successfully executed: {Path(schema_file).name}")
                success_count += 1
            except Exception as file_error:
                print(f"  ❌ Failed to execute {Path(schema_file).name}: {str(file_error)[:200]}...")
                conn.rollback()
                # 嘗試繼續處理下一個檔案
                continue
            
        except Exception as e:
            print(f"  ❌ Error reading {Path(schema_file).name}: {e}")
            conn.rollback()
    
    print(f"  📊 Summary: {success_count}/{len(schema_files)} files executed successfully")
    return success_count

def verify_installation(cursor):
    """驗證安裝結果"""
    print("📋 Step 5: Verifying installation...")
    
    try:
        # 檢查表格
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  📊 Created tables: {tables}")
        
        # 檢查函數
        cursor.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_type = 'FUNCTION'
            ORDER BY routine_name;
        """)
        functions = [row[0] for row in cursor.fetchall()]
        print(f"  ⚙️  Created functions: {functions}")
        
        # 測試一個核心函數
        if 'get_all_tables' in functions:
            cursor.execute("SELECT * FROM get_all_tables() LIMIT 3;")
            result = cursor.fetchall()
            print(f"  🧪 Function test result: {len(result)} rows returned")
        
        return len(tables), len(functions)
        
    except Exception as e:
        print(f"  ❌ Verification error: {e}")
        return 0, 0

def main():
    """主要執行流程"""
    print("🚀 Starting Database Fresh Setup")
    print("=" * 50)
    
    try:
        # Step 1: 複製 schema 檔案
        copied_files = copy_schema_files()
        if not copied_files:
            print("❌ No schema files copied. Aborting.")
            return
        
        # Step 2: 連接資料庫
        print(f"\n🔗 Connecting to {HOST}:{PORT}/{DBNAME}...")
        conn = psycopg2.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=PASSWORD,
            dbname=DBNAME
        )
        cursor = conn.cursor()
        print("✅ Database connection successful!")
        
        # Step 3: 獲取現有表格
        existing_tables = get_all_tables(cursor)
        
        # Step 4: 清理現有表格和物件
        if existing_tables or True:  # 總是執行清理
            drop_all_tables(cursor, existing_tables)
            conn.commit()
        
        # Step 5: 匯入 schema 檔案
        success_count = import_schema_files(cursor, conn, copied_files)
        
        # Step 6: 驗證安裝
        table_count, function_count = verify_installation(cursor)
        
        # 清理工作
        cursor.close()
        conn.close()
        
        # 最終報告
        print("\n" + "=" * 50)
        print("🎉 Database Fresh Setup Complete!")
        print(f"📊 Summary:")
        print(f"   - Schema files copied: {len(copied_files)}")
        print(f"   - Schema files executed: {success_count}")
        print(f"   - Tables created: {table_count}")
        print(f"   - Functions created: {function_count}")
        
        if success_count == len(copied_files) and table_count > 0:
            print("✅ All operations completed successfully!")
        else:
            print("⚠️  Some operations may have failed. Please check the logs above.")
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        print("💡 Please check your database connection and credentials.")

if __name__ == "__main__":
    main()
