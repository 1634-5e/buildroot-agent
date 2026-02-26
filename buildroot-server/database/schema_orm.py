#!/usr/bin/env python3
"""
Buildroot Agent Server - SQLAlchemy Schema Initialization
使用SQLAlchemy Core创建数据库表结构
"""

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB


def create_tables(metadata: MetaData) -> None:
    """创建所有数据库表"""

    # devices - 设备主表
    devices = Table(
        "devices",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("device_id", String(64), nullable=False, unique=True),
        Column("name", String(64)),
        Column("version", String(50)),
        Column("hostname", String(64)),
        Column("kernel_version", String(50)),
        Column("ip_addr", String(45)),
        Column("mac_addr", String(17)),
        Column("status", String(50), default="offline"),
        Column("is_online", Boolean, default=False),
        Column("last_connected_at", DateTime(timezone=True)),
        Column("last_disconnected_at", DateTime(timezone=True)),
        Column("last_seen_at", DateTime(timezone=True)),
        Column("last_heartbeat_at", DateTime(timezone=True)),
        Column("current_status", JSONB, nullable=True),
        Column("last_status_reported_at", DateTime(timezone=True)),
        Column("update_channel", String(50), default="stable"),
        Column("auto_update", Boolean, default=False),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now()),
        Column("tags", JSONB, nullable=True),
        Column("total_uptime_seconds", BigInteger, default=0),
        Column("connection_count", Integer, default=0),
        Index("idx_devices_device_id", "device_id"),
        Index("idx_devices_status", "status"),
        Index("idx_devices_is_online", "is_online"),
        Index("idx_devices_last_seen", "last_seen_at"),
        Index("idx_devices_created", "created_at"),
    )

    # device_status_history - 设备状态历史表
    device_status_history = Table(
        "device_status_history",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("device_id", String(64), nullable=False),
        Column(
            "reported_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        Column("cpu_usage", Numeric(5, 2)),
        Column("cpu_cores", Integer),
        Column("cpu_user", Numeric(5, 2)),
        Column("cpu_system", Numeric(5, 2)),
        Column("mem_total", Numeric(10, 2)),
        Column("mem_used", Numeric(10, 2)),
        Column("mem_free", Numeric(10, 2)),
        Column("mem_usage_percent", Numeric(5, 2)),
        Column("disk_total", Numeric(12, 2)),
        Column("disk_used", Numeric(12, 2)),
        Column("disk_usage_percent", Numeric(5, 2)),
        Column("load_1min", Numeric(5, 2)),
        Column("load_5min", Numeric(5, 2)),
        Column("load_15min", Numeric(5, 2)),
        Column("uptime", Integer),
        Column("net_rx_bytes", BigInteger),
        Column("net_tx_bytes", BigInteger),
        Column("hostname", String(64)),
        Column("kernel_version", String(50)),
        Column("ip_addr", String(45)),
        Column("mac_addr", String(17)),
        Column("raw_data", JSONB, nullable=True),
        Index("idx_device_status_history_device_id", "device_id"),
        Index("idx_device_status_history_reported_at", "reported_at"),
        Index("idx_device_status_history_device_reported", "device_id", "reported_at"),
    )

    # ping_history - Ping历史表
    ping_history = Table(
        "ping_history",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("device_id", String(64), nullable=False),
        Column(
            "reported_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        Column("target_ip", String(45), nullable=False),
        Column("status", Integer, default=0),
        Column("avg_time", Numeric(8, 3)),
        Column("min_time", Numeric(8, 3)),
        Column("max_time", Numeric(8, 3)),
        Column("packet_loss", Numeric(5, 2)),
        Column("packets_sent", Integer, default=0),
        Column("packets_received", Integer, default=0),
        Column("raw_data", JSONB, nullable=True),
        Index("idx_ping_history_device_id", "device_id"),
        Index("idx_ping_history_target_ip", "target_ip"),
        Index("idx_ping_history_reported_at", "reported_at"),
        Index("idx_ping_history_device_reported", "device_id", "reported_at"),
        Index("idx_ping_history_device_target", "device_id", "target_ip"),
        Index("idx_ping_history_status", "status"),
    )

    # web_console_sessions - Web控制台会话表

    # web_console_sessions - Web控制台会话表
    web_console_sessions = Table(
        "web_console_sessions",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("console_id", String(50), unique=True, nullable=False),
        Column("connected_at", DateTime(timezone=True), server_default=func.now()),
        Column("disconnected_at", DateTime(timezone=True)),
        Column("device_id", String(64)),
        Column("remote_addr", String(45)),
        Column("user_agent", Text),
        Column("pty_sessions_count", Integer, default=0),
        Column("commands_sent", Integer, default=0),
        Column("is_active", Boolean, default=True),
        Column("user_id", String(50)),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Index("idx_web_console_sessions_console_id", "console_id"),
        Index("idx_web_console_sessions_device_id", "device_id"),
        Index("idx_web_console_sessions_is_active", "is_active"),
        Index("idx_web_console_sessions_connected_at", "connected_at"),
    )

    # pty_sessions - PTY会话表
    pty_sessions = Table(
        "pty_sessions",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("session_id", Integer, nullable=False),
        Column("device_id", String(64), nullable=False),
        Column("console_id", String(50), nullable=False),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("closed_at", DateTime(timezone=True)),
        Column("closed_reason", String(50)),
        Column("rows", Integer, default=24),
        Column("cols", Integer, default=80),
        Column("bytes_sent", BigInteger, default=0),
        Column("bytes_received", BigInteger, default=0),
        Column("status", String(50), default="active"),
        Column("created_by", String(50)),
        Index("idx_pty_sessions_device_id", "device_id"),
        Index("idx_pty_sessions_console_id", "console_id"),
        Index("idx_pty_sessions_created_at", "created_at"),
        Index("idx_pty_sessions_status", "status"),
    )

    # command_history - 命令执行历史表
    command_history = Table(
        "command_history",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("device_id", String(64), nullable=False),
        Column("console_id", String(50)),
        Column("request_id", String(50), unique=True),
        Column("command", Text, nullable=False),
        Column("command_type", String(50), default="shell"),
        Column("status", String(50), default="pending"),
        Column("exit_code", Integer),
        Column("success", Boolean),
        Column("stdout", Text),
        Column("stderr", Text),
        Column("output_summary", Text),
        Column("requested_at", DateTime(timezone=True), server_default=func.now()),
        Column("started_at", DateTime(timezone=True)),
        Column("completed_at", DateTime(timezone=True)),
        Column("duration_seconds", Integer),
        Column("script_id", String(50)),
        Column("metadata", JSONB, nullable=True),
        Column("error_message", Text),
        Index("idx_command_history_device_id", "device_id"),
        Index("idx_command_history_console_id", "console_id"),
        Index("idx_command_history_request_id", "request_id"),
        Index("idx_command_history_status", "status"),
        Index("idx_command_history_requested_at", "requested_at"),
        Index("idx_command_history_command_type", "command_type"),
    )

    # script_history - 脚本执行历史表
    script_history = Table(
        "script_history",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("script_id", String(50), nullable=False),
        Column("device_id", String(64), nullable=False),
        Column("console_id", String(50)),
        Column("request_id", String(50), unique=True),
        Column("script_name", String(64)),
        Column("script_content", Text),
        Column("script_type", String(50), default="bash"),
        Column("status", String(50), default="pending"),
        Column("exit_code", Integer),
        Column("success", Boolean),
        Column("output", Text),
        Column("output_summary", Text),
        Column("output_size", Integer),
        Column("requested_at", DateTime(timezone=True), server_default=func.now()),
        Column("started_at", DateTime(timezone=True)),
        Column("completed_at", DateTime(timezone=True)),
        Column("duration_seconds", Integer),
        Column("error_message", Text),
        Column("metadata", JSONB, nullable=True),
        Index("idx_script_history_script_id", "script_id"),
        Index("idx_script_history_device_id", "device_id"),
        Index("idx_script_history_requested_at", "requested_at"),
        Index("idx_script_history_status", "status"),
    )

    # file_transfers - 文件传输记录表
    file_transfers = Table(
        "file_transfers",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("transfer_id", String(50), unique=True, nullable=False),
        Column("device_id", String(64), nullable=False),
        Column("console_id", String(50)),
        Column("filename", String(64), nullable=False),
        Column("filepath", String(500)),
        Column("file_size", BigInteger),
        Column("direction", String(50), nullable=False),
        Column("action_type", String(50)),
        Column("status", String(50), default="pending"),
        Column("checksum", String(64)),
        Column("checksum_verified", Boolean, default=False),
        Column("chunk_size", Integer),
        Column("total_chunks", Integer),
        Column("transferred_chunks", Integer, default=0),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("started_at", DateTime(timezone=True)),
        Column("completed_at", DateTime(timezone=True)),
        Column("duration_seconds", Integer),
        Column("error_message", Text),
        Column("retry_count", Integer, default=0),
        Column("request_id", String(50)),
        Column("metadata", JSONB, nullable=True),
        Index("idx_file_transfers_transfer_id", "transfer_id"),
        Index("idx_file_transfers_device_id", "device_id"),
        Index("idx_file_transfers_status", "status"),
        Index("idx_file_transfers_direction", "direction"),
        Index("idx_file_transfers_created_at", "created_at"),
    )

    # update_history - 更新历史表
    update_history = Table(
        "update_history",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("device_id", String(64), nullable=False),
        Column("old_version", String(50)),
        Column("new_version", String(50)),
        Column("update_channel", String(50)),
        Column("package_name", String(64)),
        Column("package_size", BigInteger),
        Column("package_checksum", String(64)),
        Column("package_url", Text),
        Column("status", String(30), default="pending"),
        Column("mandatory", Boolean, default=False),
        Column("approval_required", Boolean, default=False),
        Column("download_approved_at", DateTime(timezone=True)),
        Column("install_approved_at", DateTime(timezone=True)),
        Column("approval_reason", Text),
        Column("check_requested_at", DateTime(timezone=True)),
        Column("download_started_at", DateTime(timezone=True)),
        Column("download_completed_at", DateTime(timezone=True)),
        Column("install_started_at", DateTime(timezone=True)),
        Column("completed_at", DateTime(timezone=True)),
        Column("backup_path", Text),
        Column("backup_version", String(50)),
        Column("rollback_requested_at", DateTime(timezone=True)),
        Column("rollback_completed_at", DateTime(timezone=True)),
        Column("rollback_reason", Text),
        Column("error_message", Text),
        Column("error_stage", String(50)),
        Column("request_id", String(50), unique=True),
        Column("release_notes", Text),
        Column("changes", JSONB, nullable=True),
        Column("metadata", JSONB, nullable=True),
        Index("idx_update_history_device_id", "device_id"),
        Index("idx_update_history_status", "status"),
        Index("idx_update_history_new_version", "new_version"),
        Index("idx_update_history_completed_at", "completed_at"),
        Index("idx_update_history_request_id", "request_id"),
    )

    # update_approvals - 更新批准记录表
    update_approvals = Table(
        "update_approvals",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("device_id", String(64), nullable=False),
        Column(
            "update_history_id",
            BigInteger,
            ForeignKey("update_history.id", ondelete="CASCADE"),
        ),
        Column("action_type", String(50), nullable=False),
        Column("action", String(50), nullable=False),
        Column("version", String(50)),
        Column("file_size", BigInteger),
        Column("approval_time", DateTime(timezone=True), server_default=func.now()),
        Column("console_id", String(50)),
        Column("reason", String(64)),
        Column("approved_by", String(50)),
        Column("approved_by_ip", String(45)),
        Column("request_id", String(50)),
        Column("metadata", JSONB, nullable=True),
        Index("idx_update_approvals_device_id", "device_id"),
        Index("idx_update_approvals_update_history_id", "update_history_id"),
        Index("idx_update_approvals_action", "action"),
        Index("idx_update_approvals_approval_time", "approval_time"),
    )

    # audit_logs - 审计日志表
    audit_logs = Table(
        "audit_logs",
        metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("event_type", String(50), nullable=False),
        Column(
            "event_time",
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        Column("actor_type", String(50)),
        Column("actor_id", String(64)),
        Column("device_id", String(64)),
        Column("console_id", String(50)),
        Column("user_id", String(50)),
        Column("action", String(50), nullable=False),
        Column("resource_type", String(50)),
        Column("resource_id", String(64)),
        Column("status", String(50), default="success"),
        Column("result_message", Text),
        Column("ip_address", String(45)),
        Column("user_agent", Text),
        Column("details", JSONB, nullable=True),
        Index("idx_audit_logs_event_type", "event_type"),
        Index("idx_audit_logs_device_id", "device_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_event_time", "event_time"),
        Index("idx_audit_logs_actor", "actor_type", "actor_id"),
    )


def init_database():
    """初始化数据库表和结构"""
    from sqlalchemy import create_engine
    from config.settings import settings

    # 获取同步引擎用于创建表结构
    sync_url = settings.db_url.replace("+asyncpg", "")
    sync_engine = create_engine(sync_url)

    metadata = MetaData()
    create_tables(metadata)

    metadata.create_all(sync_engine, checkfirst=True)

    import logging

    logger = logging.getLogger(__name__)
    logger.info("Database schema initialized successfully")

    sync_engine.dispose()


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    logging.info("Creating database tables...")

    init_database()
