#!/usr/bin/env python3
"""
Buildroot Agent Server - SQLModel Database Models
使用 SQLModel 定义数据库模型，支持多种数据库（PostgreSQL、MySQL、SQLite等）
"""

from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    Integer,
    Numeric,
    DateTime,
    Text,
    ForeignKey,
    Index,
    func,
    JSON,
)


class Device(SQLModel, table=True):
    """设备表"""

    __tablename__ = "devices"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    device_id: str = Field(
        sa_column=Column(String(64), unique=True, nullable=False, index=True)
    )
    name: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    version: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    hostname: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    kernel_version: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    ip_addr: Optional[str] = Field(default=None, sa_column=Column(String(45)))
    mac_addr: Optional[str] = Field(default=None, sa_column=Column(String(17)))

    status: str = Field(default="offline", sa_column=Column(String(50)))
    is_online: bool = Field(
        default=False, sa_column=Column(Boolean, default=False, index=True)
    )
    last_connected_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    last_disconnected_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    last_seen_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), index=True)
    )

    current_status: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    last_status_reported_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    update_channel: str = Field(default="stable", sa_column=Column(String(50)))

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        )
    )
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    total_uptime_seconds: int = Field(
        default=0, sa_column=Column(BigInteger, default=0)
    )
    connection_count: int = Field(default=0, sa_column=Column(Integer, default=0))

    __table_args__ = (Index("ix_devices_status_online", "status", "is_online"),)


class DeviceStatusHistory(SQLModel, table=True):
    """设备状态历史表"""

    __tablename__ = "device_status_history"

    __table_args__ = (
        Index("ix_device_status_history_device_time", "device_id", "reported_at"),
    )

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    reported_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    cpu_usage: Optional[float] = Field(default=None, sa_column=Column(Numeric(5, 2)))
    cpu_cores: Optional[int] = Field(default=None, sa_column=Column(Integer))
    cpu_user: Optional[float] = Field(default=None, sa_column=Column(Numeric(5, 2)))
    cpu_system: Optional[float] = Field(default=None, sa_column=Column(Numeric(5, 2)))

    mem_total: Optional[float] = Field(default=None, sa_column=Column(Numeric(10, 2)))
    mem_used: Optional[float] = Field(default=None, sa_column=Column(Numeric(10, 2)))
    mem_free: Optional[float] = Field(default=None, sa_column=Column(Numeric(10, 2)))
    mem_usage_percent: Optional[float] = Field(
        default=None, sa_column=Column(Numeric(5, 2))
    )

    disk_total: Optional[float] = Field(default=None, sa_column=Column(Numeric(12, 2)))
    disk_used: Optional[float] = Field(default=None, sa_column=Column(Numeric(12, 2)))
    disk_usage_percent: Optional[float] = Field(
        default=None, sa_column=Column(Numeric(5, 2))
    )

    load_1min: Optional[float] = Field(default=None, sa_column=Column(Numeric(5, 2)))
    load_5min: Optional[float] = Field(default=None, sa_column=Column(Numeric(5, 2)))
    load_15min: Optional[float] = Field(default=None, sa_column=Column(Numeric(5, 2)))

    uptime: Optional[int] = Field(default=None, sa_column=Column(Integer))
    net_rx_bytes: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    net_tx_bytes: Optional[int] = Field(default=None, sa_column=Column(BigInteger))

    hostname: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    kernel_version: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    ip_addr: Optional[str] = Field(default=None, sa_column=Column(String(45)))
    mac_addr: Optional[str] = Field(default=None, sa_column=Column(String(17)))

    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class PingHistory(SQLModel, table=True):
    """Ping 历史表"""

    __tablename__ = "ping_history"

    __table_args__ = (
        Index("ix_ping_history_device_time", "device_id", "reported_at"),
        Index("ix_ping_history_device_target", "device_id", "target_ip"),
    )

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    reported_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    target_ip: str = Field(sa_column=Column(String(45), nullable=False, index=True))
    status: int = Field(default=0, sa_column=Column(Integer, default=0))

    avg_time: Optional[float] = Field(default=None, sa_column=Column(Numeric(8, 3)))
    min_time: Optional[float] = Field(default=None, sa_column=Column(Numeric(8, 3)))
    max_time: Optional[float] = Field(default=None, sa_column=Column(Numeric(8, 3)))
    packet_loss: Optional[float] = Field(default=None, sa_column=Column(Numeric(5, 2)))
    packets_sent: int = Field(default=0, sa_column=Column(Integer, default=0))
    packets_received: int = Field(default=0, sa_column=Column(Integer, default=0))

    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class CommandHistory(SQLModel, table=True):
    """命令执行历史表"""

    __tablename__ = "command_history"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    console_id: Optional[str] = Field(
        default=None, sa_column=Column(String(50), index=True)
    )
    request_id: Optional[str] = Field(
        default=None, sa_column=Column(String(50), unique=True, index=True)
    )
    command: str = Field(sa_column=Column(Text, nullable=False))
    command_type: str = Field(default="shell", sa_column=Column(String(50)))

    status: str = Field(
        default="pending", sa_column=Column(String(50), default="pending", index=True)
    )
    exit_code: Optional[int] = Field(default=None, sa_column=Column(Integer))
    success: Optional[bool] = Field(default=None, sa_column=Column(Boolean))

    stdout: Optional[str] = Field(default=None, sa_column=Column(Text))
    stderr: Optional[str] = Field(default=None, sa_column=Column(Text))
    output_summary: Optional[str] = Field(default=None, sa_column=Column(Text))

    requested_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True)
    )
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    duration_seconds: Optional[int] = Field(default=None, sa_column=Column(Integer))

    script_id: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    extra_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    __table_args__ = (
        Index("ix_command_history_requested_at", "requested_at"),
        Index("ix_command_history_device_status", "device_id", "status"),
        Index("ix_command_history_device_requested", "device_id", "requested_at"),
    )


class ScriptHistory(SQLModel, table=True):
    """脚本执行历史表"""

    __tablename__ = "script_history"

    __table_args__ = (
        Index("ix_script_history_device_requested", "device_id", "requested_at"),
        Index("ix_script_history_status", "status"),
    )

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    script_id: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    console_id: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    request_id: Optional[str] = Field(
        default=None, sa_column=Column(String(50), unique=True)
    )

    script_name: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    script_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    script_type: str = Field(default="bash", sa_column=Column(String(50)))

    status: str = Field(
        default="pending", sa_column=Column(String(50), default="pending", index=True)
    )
    exit_code: Optional[int] = Field(default=None, sa_column=Column(Integer))
    success: Optional[bool] = Field(default=None, sa_column=Column(Boolean))

    output: Optional[str] = Field(default=None, sa_column=Column(Text))
    output_summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    output_size: Optional[int] = Field(default=None, sa_column=Column(Integer))

    requested_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True)
    )
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    duration_seconds: Optional[int] = Field(default=None, sa_column=Column(Integer))

    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    extra_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class FileTransfer(SQLModel, table=True):
    """文件传输记录表"""

    __tablename__ = "file_transfers"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    transfer_id: str = Field(sa_column=Column(String(50), unique=True, nullable=False))
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    console_id: Optional[str] = Field(default=None, sa_column=Column(String(50)))

    filename: str = Field(sa_column=Column(String(64), nullable=False))
    filepath: Optional[str] = Field(default=None, sa_column=Column(String(500)))
    file_size: Optional[int] = Field(default=None, sa_column=Column(BigInteger))

    direction: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    action_type: Optional[str] = Field(default=None, sa_column=Column(String(50)))

    status: str = Field(
        default="pending", sa_column=Column(String(50), default="pending", index=True)
    )
    checksum: Optional[str] = Field(default=None, sa_column=Column(String(64)))

    chunk_size: Optional[int] = Field(default=None, sa_column=Column(Integer))
    total_chunks: Optional[int] = Field(default=None, sa_column=Column(Integer))
    transferred_chunks: int = Field(default=0, sa_column=Column(Integer, default=0))

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True)
    )
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    duration_seconds: Optional[int] = Field(default=None, sa_column=Column(Integer))

    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    request_id: Optional[str] = Field(
        default=None, sa_column=Column(String(50), index=True)
    )
    extra_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    __table_args__ = (Index("ix_file_transfers_device_status", "device_id", "status"),)


class UpdateHistory(SQLModel, table=True):
    """更新历史表"""

    __tablename__ = "update_history"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))

    old_version: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    new_version: Optional[str] = Field(
        default=None, sa_column=Column(String(50), index=True)
    )
    update_channel: Optional[str] = Field(default=None, sa_column=Column(String(50)))

    package_name: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    package_size: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    package_checksum: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    package_url: Optional[str] = Field(default=None, sa_column=Column(Text))

    status: str = Field(
        default="pending", sa_column=Column(String(30), default="pending", index=True)
    )
    mandatory: bool = Field(default=False, sa_column=Column(Boolean, default=False))

    approval_required: bool = Field(
        default=False, sa_column=Column(Boolean, default=False)
    )
    download_approved_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    install_approved_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    approval_reason: Optional[str] = Field(default=None, sa_column=Column(Text))

    check_requested_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    download_started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    download_completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    install_started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    backup_path: Optional[str] = Field(default=None, sa_column=Column(Text))
    backup_version: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    rollback_requested_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    rollback_completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    rollback_reason: Optional[str] = Field(default=None, sa_column=Column(Text))

    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    error_stage: Optional[str] = Field(default=None, sa_column=Column(String(50)))

    request_id: Optional[str] = Field(
        default=None, sa_column=Column(String(50), unique=True, index=True)
    )

    release_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    changes: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    extra_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    __table_args__ = (
        Index("ix_update_history_device_status", "device_id", "status"),
        Index("ix_update_history_device_requested", "device_id", "check_requested_at"),
    )


class UpdateApproval(SQLModel, table=True):
    """更新批准记录表"""

    __tablename__ = "update_approvals"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    update_history_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("update_history.id", ondelete="CASCADE"), index=True
        ),
    )

    action_type: str = Field(sa_column=Column(String(50), nullable=False))
    action: str = Field(sa_column=Column(String(50), nullable=False))

    version: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    file_size: Optional[int] = Field(default=None, sa_column=Column(BigInteger))

    approval_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True)
    )
    console_id: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    reason: Optional[str] = Field(default=None, sa_column=Column(String(64)))

    approved_by: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    approved_by_ip: Optional[str] = Field(default=None, sa_column=Column(String(45)))

    request_id: Optional[str] = Field(
        default=None, sa_column=Column(String(50), index=True)
    )
    extra_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class WebConsoleSession(SQLModel, table=True):
    """Web控制台会话表"""

    __tablename__ = "web_console_sessions"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    console_id: str = Field(
        sa_column=Column(String(50), unique=True, nullable=False, index=True)
    )

    connected_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True)
    )
    disconnected_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    device_id: Optional[str] = Field(
        default=None, sa_column=Column(String(64), index=True)
    )

    remote_addr: Optional[str] = Field(default=None, sa_column=Column(String(45)))
    user_agent: Optional[str] = Field(default=None, sa_column=Column(Text))

    pty_sessions_count: int = Field(default=0, sa_column=Column(Integer, default=0))
    commands_sent: int = Field(default=0, sa_column=Column(Integer, default=0))

    is_active: bool = Field(
        default=True, sa_column=Column(Boolean, default=True, index=True)
    )

    user_id: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    __table_args__ = (
        Index("ix_web_console_sessions_device_active", "device_id", "is_active"),
    )


class PtySession(SQLModel, table=True):
    """PTY会话表"""

    __tablename__ = "pty_sessions"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    session_id: int = Field(sa_column=Column(Integer, nullable=False))
    device_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    console_id: Optional[str] = Field(
        default=None, sa_column=Column(String(50), nullable=True, index=True)
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True)
    )
    closed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    closed_reason: Optional[str] = Field(default=None, sa_column=Column(String(50)))

    rows: int = Field(default=24, sa_column=Column(Integer, default=24))
    cols: int = Field(default=80, sa_column=Column(Integer, default=80))

    bytes_sent: int = Field(default=0, sa_column=Column(BigInteger, default=0))
    bytes_received: int = Field(default=0, sa_column=Column(BigInteger, default=0))

    status: str = Field(
        default="active", sa_column=Column(String(50), default="active", index=True)
    )

    created_by: Optional[str] = Field(default=None, sa_column=Column(String(50)))

    __table_args__ = (
        Index("ix_pty_sessions_device_session", "device_id", "session_id", unique=True),
        Index("ix_pty_sessions_device_status", "device_id", "status"),
        Index("ix_pty_sessions_console_status", "console_id", "status"),
    )


class AuditLog(SQLModel, table=True):
    """审计日志表"""

    __tablename__ = "audit_logs"

    id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )

    event_type: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    event_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    actor_type: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    actor_id: Optional[str] = Field(
        default=None, sa_column=Column(String(64), index=True)
    )
    device_id: Optional[str] = Field(
        default=None, sa_column=Column(String(64), index=True)
    )
    console_id: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    user_id: Optional[str] = Field(default=None, sa_column=Column(String(50)))

    action: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    resource_type: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    resource_id: Optional[str] = Field(default=None, sa_column=Column(String(64)))

    status: str = Field(default="success", sa_column=Column(String(50)))
    result_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    ip_address: Optional[str] = Field(default=None, sa_column=Column(String(45)))
    user_agent: Optional[str] = Field(default=None, sa_column=Column(Text))

    details: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    __table_args__ = (
        Index("ix_audit_logs_event_time", "event_time"),
        Index("ix_audit_logs_device_id", "device_id"),
        Index("ix_audit_logs_event_action", "event_type", "action"),
        Index("ix_audit_logs_device_time", "device_id", "event_time"),
        Index("ix_audit_logs_event_type_time", "event_type", "event_time"),
        Index(
            "ix_audit_logs_device_event_time", "device_id", "event_type", "event_time"
        ),
    )
