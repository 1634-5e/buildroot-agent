#!/usr/bin/env python3
"""
Buildroot Agent Server - Database Maintenance Script
用于维护数据库：数据清理
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import text, delete, func

from database.db_manager import db_manager
from database.models import (
    DeviceStatusHistory,
    AuditLog,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cleanup_old_data(retention_days: int = 90):
    """清理旧的设备状态历史数据"""
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    try:
        async with db_manager.get_session() as session:
            result = await session.execute(
                delete(DeviceStatusHistory).where(
                    DeviceStatusHistory.reported_at < cutoff_date
                )
            )
            count = result.rowcount

        logger.info(f"Cleaned up {count} old device_status_history records")
        return count
    except Exception as e:
        logger.error(f"Error cleaning device_status_history: {e}")
        return 0


async def cleanup_old_audit_logs(retention_days: int = 180):
    """清理旧的审计日志"""
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    try:
        async with db_manager.get_session() as session:
            result = await session.execute(
                delete(AuditLog).where(AuditLog.event_time < cutoff_date)
            )
            count = result.rowcount

        logger.info(f"Cleaned up {count} old audit_logs records")
        return count
    except Exception as e:
        logger.error(f"Error cleaning audit_logs: {e}")
        return 0


async def vacuum_analyze():
    """运行VACUUM和ANALYZE (仅PostgreSQL)"""
    dialect_name = (
        db_manager._engine.dialect.name if db_manager._engine else "postgresql"
    )

    if dialect_name != "postgresql":
        logger.info("VACUUM ANALYZE only available for PostgreSQL, skipping")
        return

    tables = [
        "devices",
        "device_status_history",
        "command_history",
        "script_history",
        "file_transfers",
        "update_history",
        "update_approvals",
        "web_console_sessions",
        "pty_sessions",
        "audit_logs",
    ]

    for table in tables:
        try:
            logger.info(f"VACUUM ANALYZE {table}...")
            async with db_manager.get_session() as session:
                await session.execute(text(f"VACUUM ANALYZE {table}"))
        except Exception as e:
            logger.warning(f"VACUUM ANALYZE failed for {table}: {e}")


async def get_database_stats():
    """获取数据库统计信息"""
    from database.models import (
        Device,
        CommandHistory,
        ScriptHistory,
        FileTransfer,
        UpdateHistory,
        UpdateApproval,
        WebConsoleSession,
        PtySession,
    )

    stats = {}

    models = [
        ("devices", Device),
        ("device_status_history", DeviceStatusHistory),
        ("command_history", CommandHistory),
        ("script_history", ScriptHistory),
        ("file_transfers", FileTransfer),
        ("update_history", UpdateHistory),
        ("update_approvals", UpdateApproval),
        ("web_console_sessions", WebConsoleSession),
        ("pty_sessions", PtySession),
        ("audit_logs", AuditLog),
    ]

    for table_name, model in models:
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(func.count(model.id))
                count = result.scalar()
                stats[table_name] = count
        except Exception as e:
            logger.warning(f"Failed to get stats for {table_name}: {e}")
            stats[table_name] = "N/A"

    return stats


async def main():
    """主函数"""
    logger.info("Starting database maintenance...")

    # 初始化数据库连接
    await db_manager.initialize()

    try:
        # 清理旧数据
        logger.info("=" * 50)
        logger.info("Cleaning old device_status_history data (older than 90 days)...")
        await cleanup_old_data(retention_days=90)

        logger.info("=" * 50)
        logger.info("Cleaning old audit_logs (older than 180 days)...")
        await cleanup_old_audit_logs(retention_days=180)

        # 运行VACUUM ANALYZE
        logger.info("=" * 50)
        logger.info("Running VACUUM ANALYZE...")
        await vacuum_analyze()

        # 获取统计信息
        logger.info("=" * 50)
        logger.info("Database statistics:")
        stats = await get_database_stats()
        for table, count in stats.items():
            logger.info(
                f"  {table}: {count if count == 'N/A' else f'{count:,}'} records"
            )

        logger.info("=" * 50)
        logger.info("Database maintenance completed successfully!")

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
