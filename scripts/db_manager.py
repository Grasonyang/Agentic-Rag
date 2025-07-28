#!/usr/bin/env python3
"""
数据库管理脚本 - 使用精简架构
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.append(str(Path(__file__).parent.parent))

from database.client import SupabaseClient

def deploy_schema():
    """部署数据库架构"""
    print("🚀 开始部署精简数据库架构...")
    
    try:
        # 读取SQL文件
        schema_file = Path(__file__).parent.parent / "database" / "sql" / "schema.sql"
        
        if not schema_file.exists():
            print(f"❌ SQL文件不存在: {schema_file}")
            return False
        
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 连接数据库并执行
        db_client = SupabaseClient()
        supabase = db_client.get_client()
        
        print("📝 执行SQL脚本...")
        result = supabase.rpc('exec_sql', {'sql': sql_content})
        
        print("✅ 数据库架构部署成功！")
        
        # 获取统计信息
        stats_result = supabase.rpc('get_db_stats')
        if stats_result.data:
            print("\n📊 数据库统计信息:")
            for row in stats_result.data:
                print(f"   {row['table_name']}: {row['row_count']} 条记录, {row['table_size']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 部署失败: {e}")
        return False

def clear_data():
    """清空所有数据"""
    print("🗑️  开始清空数据...")
    
    try:
        db_client = SupabaseClient()
        supabase = db_client.get_client()
        
        result = supabase.rpc('clear_all_data')
        print("✅ 数据清空成功！")
        return True
        
    except Exception as e:
        print(f"❌ 清空失败: {e}")
        return False

def show_stats():
    """显示数据库统计"""
    print("📊 获取数据库统计信息...")
    
    try:
        db_client = SupabaseClient()
        supabase = db_client.get_client()
        
        result = supabase.rpc('get_db_stats')
        
        if result.data:
            print("\n📈 数据库统计:")
            print("-" * 50)
            for row in result.data:
                print(f"{row['table_name']:20} | {row['row_count']:>8} 行 | {row['table_size']:>10}")
            print("-" * 50)
        else:
            print("⚠️  无法获取统计信息")
        
        return True
        
    except Exception as e:
        print(f"❌ 获取统计失败: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库管理工具")
    parser.add_argument("action", choices=["deploy", "clear", "stats"], 
                       help="操作类型: deploy=部署架构, clear=清空数据, stats=显示统计")
    
    args = parser.parse_args()
    
    if args.action == "deploy":
        deploy_schema()
    elif args.action == "clear":
        clear_data()
    elif args.action == "stats":
        show_stats()
