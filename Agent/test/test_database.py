# File: test_database.py
"""
数据库连接测试脚本
用于验证 Supabase 连接和表结构是否正确
"""
import sys
import os
import time  # ← 新增：导入 time 模块

# 添加父目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import db
from dotenv import load_dotenv

load_dotenv()


def test_database_connection():
    """测试数据库连接"""
    print("=" * 60)
    print("Supabase 数据库连接测试")
    print("=" * 60)

    try:
        # 测试 1: 检查环境变量
        print("\n[测试 1] 检查环境变量...")
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        if not supabase_url:
            print("❌ SUPABASE_URL 未配置")
            return False
        if not supabase_key:
            print("❌ SUPABASE_KEY 未配置")
            return False

        print(f"✅ SUPABASE_URL: {supabase_url[:30]}...")
        print(f"✅ SUPABASE_KEY: {supabase_key[:10]}...{supabase_key[-5:]}")

        # 测试 2: 尝试连接
        print("\n[测试 2] 测试数据库连接...")
        result = db.client.table('task_executions').select('id').limit(1).execute()
        print("✅ 数据库连接成功")

        # 测试 3: 检查表是否存在
        print("\n[测试 3] 检查表结构...")
        tables_to_check = [
            'task_executions',
            'step_executions',
            'decisions',
            'reflect_verifications',
            'error_logs',
            'system_configs'
        ]

        for table in tables_to_check:
            try:
                result = db.client.table(table).select('id').limit(1).execute()
                print(f"✅ 表 {table} 存在")
            except Exception as e:
                print(f"❌ 表 {table} 不存在或无法访问：{str(e)}")

        # 测试 4: 插入测试数据
        print("\n[测试 4] 插入测试数据...")
        test_task = db.create_task(
            task_id='test_' + str(int(time.time())),
            instruction='数据库连接测试',
            total_steps=1
        )
        print(f"✅ 测试数据插入成功：{test_task['id']}")

        # 测试 5: 查询测试数据
        print("\n[测试 5] 查询测试数据...")
        recent_tasks = db.get_recent_tasks(limit=5)
        print(f"✅ 查询成功，最近 {len(recent_tasks)} 条任务")

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！数据库配置正确。")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ 测试失败：{str(e)}")
        print("\n可能的原因：")
        print("1. .env 文件未配置或配置错误")
        print("2. Supabase 表未创建")
        print("3. 网络连接问题")
        print("4. API Key 权限不足")
        return False


if __name__ == '__main__':
    import time

    success = test_database_connection()
    sys.exit(0 if success else 1)
