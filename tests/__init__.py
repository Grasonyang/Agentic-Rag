"""
測試配置和共用工具
"""

import os
import sys
import logging
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 測試日誌配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 測試用的 URL 列表
TEST_URLS = [
    "https://httpbin.org/json",
    "https://httpbin.org/html", 
    "https://example.com",
    "https://httpbin.org/xml",
    "https://httpbin.org/status/200",
    "https://httpbin.org/user-agent",
    "https://httpbin.org/headers",
    "https://jsonplaceholder.typicode.com/posts/1",
    "https://httpbin.org/robots.txt",
    "https://httpbin.org/delay/1"
]

# 測試配置
TEST_CONFIG = {
    "max_concurrent": 3,
    "timeout": 30,
    "retry_attempts": 2,
    "test_batch_size": 5
}

def print_test_header(title: str, width: int = 60):
    """打印測試標題"""
    print("=" * width)
    print(f"🧪 {title}")
    print("=" * width)

def print_test_result(test_name: str, success: bool, details: str = ""):
    """打印測試結果"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"   {details}")

def print_test_summary(passed: int, total: int):
    """打印測試總結"""
    print("\n" + "=" * 40)
    print(f"📊 測試總結: {passed}/{total} 通過")
    if passed == total:
        print("🎉 所有測試通過！")
    else:
        print(f"⚠️ {total - passed} 個測試失敗")
    print("=" * 40)
