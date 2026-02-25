#!/usr/bin/env python3
"""
Buildroot Agent Server - System Handler with Database Integration
处理器示例，展示如何集成数据库操作
"""

import logging
from datetime import datetime

from database.repositories import (
    DeviceRepository,
    DeviceStatusHistoryRepository,
    CommandHistoryRepository,
    AuditLogRepository,
)

logger = logging.getLogger(__name__)


class SystemHandlerWithDB:
    """带数据库集成的系统处理器示例"""

    async def handle_system_status(self, device_id: str, data: dict) -> None:
        """处理设备系统状态更新"""
        # 更新设备的当前状态（实时数据）
        await DeviceRepository.update_current_status(
            device_id=device_id,
            current_status=data,
        )

        # 保存状态历史记录
        await DeviceStatusHistoryRepository.insert(
            device_id=device_id,
            cpu_usage=data.get("cpu_usage", 0),
            cpu_cores=data.get("cpu_cores", 1),
            cpu_user=data.get("cpu_user", 0),
            cpu_system=data.get("cpu_system", 0),
            mem_total=data.get("mem_total", 0),
            mem_used=data.get("mem_used", 0),
            mem_free=data.get("mem_free", 0),
            disk_total=data.get("disk_total", 0),
            disk_used=data.get("disk_used", 0),
            load_1min=data.get("load_1min", 0),
            load_5min=data.get("load_5min", 0),
            load_15min=data.get("load_15min", 0),
            uptime=data.get("uptime", 0),
            net_rx_bytes=data.get("net_rx_bytes", 0),
            net_tx_bytes=data.get("net_tx_bytes", 0),
            hostname=data.get("hostname"),
            kernel_version=data.get("kernel_version"),
            ip_addr=data.get("ip_addr"),
            mac_addr=data.get("mac_addr"),
            raw_data=data,
        )

        # 记录审计日志
        await AuditLogRepository.insert(
            event_type="system_status",
            action="report_status",
            actor_type="device",
            actor_id=device_id,
            device_id=device_id,
            status="success",
            details={"cpu_usage": data.get("cpu_usage")},
        )

        logger.info(
            f"[DB] Saved status for device {device_id}: "
            f"CPU={data.get('cpu_usage', 0):.1f}%"
        )

    async def handle_script_result(self, device_id: str, data: dict) -> None:
        """处理脚本执行结果"""
        script_id = data.get("script_id", "unknown")
        request_id = data.get("request_id")
        exit_code = data.get("exit_code", -1)
        success = data.get("success", False)
        stdout = data.get("output", "")
        stderr = data.get("error", "")

        # 更新命令执行结果
        if request_id:
            status = "completed" if success else "failed"
            await CommandHistoryRepository.update_result(
                request_id=request_id,
                status=status,
                exit_code=exit_code,
                success=success,
                stdout=stdout,
                stderr=stderr,
            )

        # 记录审计日志
        await AuditLogRepository.insert(
            event_type="script_execution",
            action="execute_script",
            actor_type="device",
            actor_id=device_id,
            device_id=device_id,
            resource_type="script",
            resource_id=script_id,
            status="success" if success else "failure",
            result_message=f"Exit code: {exit_code}",
        )

        logger.info(f"[DB] Script execution result saved: {script_id} - {success}")
