#!/usr/bin/env python3
"""
Buildroot Agent Server - SQLAlchemy Models
使用SQLAlchemy ORM定义数据库模型，支持多种数据库
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    Session as SQLAlchemySession,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    pass


class Device(Base):
    """设备表"""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(64))
    version: Mapped[Optional[str]] = mapped_column(String(50))
    hostname: Mapped[Optional[str]] = mapped_column(String(64))
    kernel_version: Mapped[Optional[str]] = mapped_column(String(50))
    ip_addr: Mapped[Optional[str]] = mapped_column(String(45))
    mac_addr: Mapped[Optional[str]] = mapped_column(String(17))

    status: Mapped[str] = mapped_column(String(50), default="offline")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_disconnected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    current_status: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    last_status_reported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    update_channel: Mapped[str] = mapped_column(String(50), default="stable")
    auto_update: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    total_uptime_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    connection_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_devices_status_online", "status", "is_online"),
    )


class DeviceStatusHistory(Base):
    """设备状态历史表"""

    __tablename__ = "device_status_history"

    __table_args__ = (
        Index("ix_device_status_history_device_time", "device_id", "reported_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    cpu_usage: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    cpu_cores: Mapped[Optional[int]] = mapped_column(Integer)
    cpu_user: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    cpu_system: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    mem_total: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    mem_used: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    mem_free: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    mem_usage_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    disk_total: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    disk_used: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    disk_usage_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    load_1min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    load_5min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    load_15min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    uptime: Mapped[Optional[int]] = mapped_column(Integer)
    net_rx_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    net_tx_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)

    hostname: Mapped[Optional[str]] = mapped_column(String(64))
    kernel_version: Mapped[Optional[str]] = mapped_column(String(50))
    ip_addr: Mapped[Optional[str]] = mapped_column(String(45))
    mac_addr: Mapped[Optional[str]] = mapped_column(String(17))

    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class PingHistory(Base):
    """Ping 历史表"""

    __tablename__ = "ping_history"

    __table_args__ = (
        Index("ix_ping_history_device_time", "device_id", "reported_at"),
        Index("ix_ping_history_device_target", "device_id", "target_ip"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    target_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    status: Mapped[int] = mapped_column(Integer, default=0)

    avg_time: Mapped[Optional[float]] = mapped_column(Numeric(8, 3))
    min_time: Mapped[Optional[float]] = mapped_column(Numeric(8, 3))
    max_time: Mapped[Optional[float]] = mapped_column(Numeric(8, 3))
    packet_loss: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    packets_sent: Mapped[int] = mapped_column(Integer, default=0)
    packets_received: Mapped[int] = mapped_column(Integer, default=0)

    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class CommandHistory(Base):
    """命令执行历史表"""

    __tablename__ = "command_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    console_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    request_id: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, index=True
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    command_type: Mapped[str] = mapped_column(String(50), default="shell")

    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[Optional[bool]] = mapped_column(Boolean)

    stdout: Mapped[Optional[str]] = mapped_column(Text)
    stderr: Mapped[Optional[str]] = mapped_column(Text)
    output_summary: Mapped[Optional[str]] = mapped_column(Text)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    script_id: Mapped[Optional[str]] = mapped_column(String(50))
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("ix_command_history_requested_at", "requested_at"),
        Index("ix_command_history_device_status", "device_id", "status"),
        Index("ix_command_history_device_requested", "device_id", "requested_at"),
    )


class ScriptHistory(Base):
    """脚本执行历史表"""

    __tablename__ = "script_history"

    __table_args__ = (
        Index("ix_script_history_device_requested", "device_id", "requested_at"),
        Index("ix_script_history_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    script_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    console_id: Mapped[Optional[str]] = mapped_column(String(50))
    request_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True)

    script_name: Mapped[Optional[str]] = mapped_column(String(64))
    script_content: Mapped[Optional[str]] = mapped_column(Text)
    script_type: Mapped[str] = mapped_column(String(50), default="bash")

    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[Optional[bool]] = mapped_column(Boolean)

    output: Mapped[Optional[str]] = mapped_column(Text)
    output_summary: Mapped[Optional[str]] = mapped_column(Text)
    output_size: Mapped[Optional[int]] = mapped_column(Integer)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    error_message: Mapped[Optional[str]] = mapped_column(Text)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class FileTransfer(Base):
    """文件传输记录表"""

    __tablename__ = "file_transfers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transfer_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    console_id: Mapped[Optional[str]] = mapped_column(String(50))

    filename: Mapped[str] = mapped_column(String(64), nullable=False)
    filepath: Mapped[Optional[str]] = mapped_column(String(500))
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)

    direction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[Optional[str]] = mapped_column(String(50))

    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64))
    checksum_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    chunk_size: Mapped[Optional[int]] = mapped_column(Integer)
    total_chunks: Mapped[Optional[int]] = mapped_column(Integer)
    transferred_chunks: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    request_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("ix_file_transfers_device_status", "device_id", "status"),)


class UpdateHistory(Base):
    """更新历史表"""

    __tablename__ = "update_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    old_version: Mapped[Optional[str]] = mapped_column(String(50))
    new_version: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    update_channel: Mapped[Optional[str]] = mapped_column(String(50))

    package_name: Mapped[Optional[str]] = mapped_column(String(64))
    package_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    package_checksum: Mapped[Optional[str]] = mapped_column(String(64))
    package_url: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)

    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    download_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    install_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    approval_reason: Mapped[Optional[str]] = mapped_column(Text)

    check_requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    download_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    download_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    install_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    backup_path: Mapped[Optional[str]] = mapped_column(Text)
    backup_version: Mapped[Optional[str]] = mapped_column(String(50))
    rollback_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    rollback_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    rollback_reason: Mapped[Optional[str]] = mapped_column(Text)

    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_stage: Mapped[Optional[str]] = mapped_column(String(50))

    request_id: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, index=True
    )

    release_notes: Mapped[Optional[str]] = mapped_column(Text)
    changes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_update_history_device_status", "device_id", "status"),
        Index("ix_update_history_device_requested", "device_id", "check_requested_at"),
    )


class UpdateApproval(Base):
    """更新批准记录表"""

    __tablename__ = "update_approvals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    update_history_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("update_history.id", ondelete="CASCADE"), index=True
    )

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    version: Mapped[Optional[str]] = mapped_column(String(50))
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)

    approval_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    console_id: Mapped[Optional[str]] = mapped_column(String(50))
    reason: Mapped[Optional[str]] = mapped_column(String(64))

    approved_by: Mapped[Optional[str]] = mapped_column(String(50))
    approved_by_ip: Mapped[Optional[str]] = mapped_column(String(45))

    request_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class WebConsoleSession(Base):
    """Web控制台会话表"""

    __tablename__ = "web_console_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    console_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    device_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    remote_addr: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    pty_sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    commands_sent: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    user_id: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    __table_args__ = (
        Index("ix_web_console_sessions_device_active", "device_id", "is_active"),
    )


class PtySession(Base):
    """PTY会话表"""

    __tablename__ = "pty_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    console_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_reason: Mapped[Optional[str]] = mapped_column(String(50))

    rows: Mapped[int] = mapped_column(Integer, default=24)
    cols: Mapped[int] = mapped_column(Integer, default=80)

    bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0)

    status: Mapped[str] = mapped_column(String(50), default="active", index=True)

    created_by: Mapped[Optional[str]] = mapped_column(String(50))

    __table_args__ = (
        Index("ix_pty_sessions_device_session", "device_id", "session_id", unique=True),
        Index("ix_pty_sessions_device_status", "device_id", "status"),
        Index("ix_pty_sessions_console_status", "console_id", "status"),
    )


class AuditLog(Base):
    """审计日志表"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    actor_type: Mapped[Optional[str]] = mapped_column(String(50))
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    console_id: Mapped[Optional[str]] = mapped_column(String(50))
    user_id: Mapped[Optional[str]] = mapped_column(String(50))

    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[str]] = mapped_column(String(64))

    status: Mapped[str] = mapped_column(String(50), default="success")
    result_message: Mapped[Optional[str]] = mapped_column(Text)

    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

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
