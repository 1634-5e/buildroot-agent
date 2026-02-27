import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from database.repositories import (
    DeviceRepository,
    DeviceStatusHistoryRepository,
    ScriptHistoryRepository,
    AuditLogRepository,
)
from database.batch_buffer import get_status_history_buffer, get_audit_log_buffer
from handlers.base import BaseHandler
from protocol.constants import MessageType
from protocol.models import Heartbeat, SystemStatus, LogUpload, ScriptRecv, ScriptResult

logger = logging.getLogger(__name__)


class SystemHandler(BaseHandler):
    async def handle_heartbeat(self, device_id: str, data: dict) -> None:
        logger.debug(f"收到心跳: {device_id}")

        try:
            await DeviceRepository.update_connection_status(
                device_id=device_id,
                status="online",
                is_online=True,
                last_seen_at=datetime.now(),
            )
            logger.debug(f"[DB] 心跳已更新: {device_id}")
        except Exception as e:
            logger.error(f"[DB] 更新心跳失败: {e}")

    async def handle_system_status(self, device_id: str, data: dict) -> None:
        logger.info(
            f"设备状态 [{device_id}]: "
            f"CPU={data.get('cpu_usage', 0):.1f}%, "
            f"MEM={data.get('mem_used', 0):.0f}/{data.get('mem_total', 0):.0f}MB, "
            f"Load={data.get('load_1min', 0):.2f}"
        )

        request_id = data.get("request_id")

        try:
            await DeviceRepository.update_current_status(
                device_id=device_id,
                current_status=data,
            )
            logger.debug(f"[DB] 设备当前状态已更新: {device_id}")
        except Exception as e:
            logger.error(f"[DB] 更新设备状态失败: {e}")

        try:
            await DeviceRepository.update_device_info(
                device_id=device_id,
                hostname=data.get("hostname"),
                kernel_version=data.get("kernel_version"),
                ip_addr=data.get("ip_addr"),
                mac_addr=data.get("mac_addr"),
            )
            logger.debug(f"[DB] 设备基本信息已同步: {device_id}")
        except Exception as e:
            logger.error(f"[DB] 同步设备基本信息失败: {e}")

        try:
            uptime = data.get("uptime", 0)
            if uptime > 0:
                await DeviceRepository.update_uptime_seconds(
                    device_id=device_id,
                    uptime_seconds=uptime,
                )
                logger.debug(f"[DB] 运行时间已更新: {device_id}, uptime={uptime}s")
        except Exception as e:
            logger.error(f"[DB] 更新运行时间失败: {e}")

        buffer = get_status_history_buffer()
        asyncio.create_task(
            buffer.add_status(
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
        )

        buffer = get_audit_log_buffer()
        asyncio.create_task(
            buffer.add_log(
                event_type="system_status",
                action="report_status",
                actor_type="device",
                actor_id=device_id,
                device_id=device_id,
                status="success",
                details={
                    "cpu_usage": data.get("cpu_usage", 0),
                    "mem_usage_percent": (
                        (data.get("mem_used", 0) / data.get("mem_total", 1) * 100)
                        if data.get("mem_total", 0) > 0
                        else 0
                    ),
                },
            )
        )

        if request_id:
            status_data = {"device_id": device_id, **data}
            await self.unicast_by_request_id(
                MessageType.SYSTEM_STATUS,
                status_data,
                request_id,
            )

    async def handle_log_upload(self, device_id: str, data: dict) -> None:
        filepath = data.get("filepath", "unknown")
        if "chunk" in data:
            chunk = data.get("chunk", 0)
            total = data.get("total_chunks", 1)
            logger.info(f"收到日志分片 [{device_id}]: {filepath} ({chunk + 1}/{total})")
        elif "line" in data:
            line = data.get("line", "")
            logger.info(f"实时日志 [{device_id}] {filepath}: {line}")
        elif "lines" in data:
            lines = data.get("lines", 0)
            logger.info(f"收到日志 [{device_id}]: {filepath} ({lines} 行)")

        buffer = get_audit_log_buffer()
        asyncio.create_task(
            buffer.add_log(
                event_type="log_upload",
                action="upload_log",
                actor_type="device",
                actor_id=device_id,
                device_id=device_id,
                resource_type="log_file",
                resource_id=filepath,
                status="success",
                details={
                    "filepath": filepath,
                    "lines": data.get("lines"),
                    "chunk": data.get("chunk"),
                },
            )
        )

    async def handle_script_result(self, device_id: str, data: dict) -> None:
        script_id = data.get("script_id", "unknown")
        request_id = data.get("request_id")
        exit_code = data.get("exit_code", -1)
        success = data.get("success", False)
        output = data.get("output", "")
        error = data.get("error", "")

        status = "成功" if success else "失败"
        logger.info(f"脚本执行{status} [{device_id}]: {script_id}, 退出码={exit_code}")
        if output:
            logger.info(f"输出:\n{output[:500]}")
        if error:
            logger.error(f"错误:\n{error}")

        if request_id:
            try:
                await ScriptHistoryRepository.update_result(
                    script_id=script_id,
                    status="completed" if success else "failed",
                    exit_code=exit_code,
                    success=success,
                    output=output,
                    error_message=error,
                )
                logger.info(f"[DB] 脚本执行结果已更新: {script_id}")
            except Exception as e:
                logger.error(f"[DB] 更新脚本执行结果失败: {e}")

        buffer = get_audit_log_buffer()
        asyncio.create_task(
            buffer.add_log(
                event_type="script_execution",
                action="execute_script",
                actor_type="device",
                actor_id=device_id,
                device_id=device_id,
                resource_type="script",
                resource_id=script_id,
                status="success" if success else "failure",
                result_message=f"Exit code: {exit_code}",
                details={
                    "script_id": script_id,
                    "exit_code": exit_code,
                    "output_length": len(output) if output else 0,
                },
            )
        )
