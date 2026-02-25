#!/usr/bin/env python3
"""
Buildroot Agent Server - Database Integration for ConnectionManager
为现有的ConnectionManager添加数据库支持
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database.repositories import (
    DeviceRepository,
    DeviceStatusHistoryRepository,
    CommandHistoryRepository,
    UpdateHistoryRepository,
    AuditLogRepository,
)

logger = logging.getLogger(__name__)


class ConnectionManagerDBMixin:
    """ConnectionManager数据库集成混入类"""

    async def add_device_to_db(
        self,
        device_id: str,
        version: str = None,
        hostname: str = None,
        kernel_version: str = None,
        ip_addr: str = None,
        mac_addr: str = None,
    ) -> Optional[Dict[str, Any]]:
        """添加设备到数据库"""
        try:
            device = await DeviceRepository.create_or_update(
                device_id=device_id,
                version=version,
                hostname=hostname,
                kernel_version=kernel_version,
                ip_addr=ip_addr,
                mac_addr=mac_addr,
            )
            logger.info(f"[DB] Device added to database: {device_id}")
            return device
        except Exception as e:
            logger.error(f"[DB] Failed to add device to database: {e}")
            return None

    async def update_device_connection_status(
        self,
        device_id: str,
        is_online: bool,
        remote_addr: str = None,
    ) -> bool:
        """更新设备连接状态"""
        try:
            status = "online" if is_online else "offline"
            await DeviceRepository.update_connection_status(
                device_id=device_id,
                status=status,
                is_online=is_online,
                last_seen_at=datetime.now(),
                remote_addr=remote_addr,
            )
            return True
        except Exception as e:
            logger.error(f"[DB] Failed to update device status: {e}")
            return False

    async def save_device_status_history(
        self,
        device_id: str,
        status_data: Dict[str, Any],
    ) -> bool:
        """保存设备状态历史"""
        try:
            await DeviceStatusHistoryRepository.insert(
                device_id=device_id,
                cpu_usage=status_data.get("cpu_usage", 0),
                cpu_cores=status_data.get("cpu_cores", 1),
                cpu_user=status_data.get("cpu_user", 0),
                cpu_system=status_data.get("cpu_system", 0),
                mem_total=status_data.get("mem_total", 0),
                mem_used=status_data.get("mem_used", 0),
                mem_free=status_data.get("mem_free", 0),
                disk_total=status_data.get("disk_total", 0),
                disk_used=status_data.get("disk_used", 0),
                load_1min=status_data.get("load_1min", 0),
                load_5min=status_data.get("load_5min", 0),
                load_15min=status_data.get("load_15min", 0),
                uptime=status_data.get("uptime", 0),
                net_rx_bytes=status_data.get("net_rx_bytes", 0),
                net_tx_bytes=status_data.get("net_tx_bytes", 0),
                hostname=status_data.get("hostname"),
                kernel_version=status_data.get("kernel_version"),
                ip_addr=status_data.get("ip_addr"),
                mac_addr=status_data.get("mac_addr"),
                raw_data=status_data,
            )
            return True
        except Exception as e:
            logger.error(f"[DB] Failed to save device status history: {e}")
            return False

    async def log_command_execution(
        self,
        device_id: str,
        command: str,
        console_id: str = None,
        request_id: str = None,
    ) -> Optional[int]:
        """记录命令执行"""
        try:
            result = await CommandHistoryRepository.insert(
                device_id=device_id,
                command=command,
                console_id=console_id,
                request_id=request_id,
            )
            return result.get("id")
        except Exception as e:
            logger.error(f"[DB] Failed to log command execution: {e}")
            return None

    async def update_command_result(
        self,
        request_id: str,
        status: str,
        exit_code: int = None,
        success: bool = None,
        stdout: str = None,
        stderr: str = None,
    ) -> bool:
        """更新命令执行结果"""
        try:
            output_summary = (
                (stdout or stderr or "")[:500] if (stdout or stderr) else None
            )
            await CommandHistoryRepository.update_result(
                request_id=request_id,
                status=status,
                exit_code=exit_code,
                success=success,
                stdout=stdout,
                stderr=stderr,
                output_summary=output_summary,
                completed_at=datetime.now(),
            )
            return True
        except Exception as e:
            logger.error(f"[DB] Failed to update command result: {e}")
            return False

    async def log_update_check(
        self,
        device_id: str,
        current_version: str,
        new_version: str = None,
        request_id: str = None,
    ) -> Optional[int]:
        """记录更新检查"""
        try:
            if not new_version:
                return None

            result = await UpdateHistoryRepository.insert(
                device_id=device_id,
                old_version=current_version,
                new_version=new_version,
                request_id=request_id,
            )
            return result.get("id")
        except Exception as e:
            logger.error(f"[DB] Failed to log update check: {e}")
            return None

    async def log_audit_event(
        self,
        event_type: str,
        action: str,
        actor_type: str = None,
        actor_id: str = None,
        device_id: str = None,
        console_id: str = None,
        resource_type: str = None,
        resource_id: str = None,
        status: str = "success",
        details: Dict[str, Any] = None,
    ) -> bool:
        """记录审计事件"""
        try:
            await AuditLogRepository.insert(
                event_type=event_type,
                action=action,
                actor_type=actor_type,
                actor_id=actor_id,
                device_id=device_id,
                console_id=console_id,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                details=details,
            )
            return True
        except Exception as e:
            logger.error(f"[DB] Failed to log audit event: {e}")
            return False

    async def get_devices_from_db(
        self,
        status: str = None,
        tags: list = None,
        limit: int = 100,
    ) -> list:
        """从数据库获取设备列表"""
        try:
            devices = await DeviceRepository.list_devices(
                status=status,
                tags=tags,
                limit=limit,
            )
            return devices
        except Exception as e:
            logger.error(f"[DB] Failed to get devices from database: {e}")
            return []


class EnhancedConnectionManager(ConnectionManagerDBMixin):
    """增强的连接管理器，集成数据库功能"""

    def __init__(self):
        pass
