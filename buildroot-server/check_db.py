#!/usr/bin/env python3
"""
检查和修复数据库表结构
"""

import asyncio
import sqlite3

DB_PATH = "buildroot_agent.db.db"


async def check_tables():
    """检查数据库表结构"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    print("=" * 60)
    print("数据库表检查")
    print("=" * 60)

    for (table_name,) in tables:
        print(f"\n表: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(
                f"  - {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''} {'PRIMARY KEY' if col[5] else ''}"
            )

    conn.close()


if __name__ == "__main__":
    asyncio.run(check_tables())
