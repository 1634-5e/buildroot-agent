import asyncio
import logging
from typing import Any
from datetime import datetime

from database.repositories import CommandHistoryRepository, AuditLogRepository
from handlers.base import BaseHandler
from protocol.constants import MessageType

logger = logging.getLogger(__name__)


class CommandHandler(BaseHandler):
    async def handle_cmd_request(
        self, device_id: str, data: dict, websocket: Any
    ) -> None:
        """处理命令请求"""
        command = data.get("command", "")
        request_id = data.get("request_id")
        console_id = data.get("console_id")

        logger.info(f"收到命令请求 [{device_id}]: {command[:100]}")

        # 数据库操作：记录命令执行请求
        if request_id:
            try:
                result = await CommandHistoryRepository.insert(
                    device_id=device_id,
                    command=command,
                    console_id=console_id,
                    request_id=request_id,
                )
                logger.info(
                    f"[DB] 命令执行已记录: request_id={request_id}, result_id={result.get('id')}"
                )
            except Exception as e:
                logger.error(f"[DB] 记录命令执行失败: {e}")

            # 记录审计日志（异步，不阻塞主流程）
            asyncio.create_task(
                AuditLogRepository.insert(
                    event_type="command_execution",
                    action="execute_command",
                    actor_type="web_console",
                    actor_id=console_id,
                    device_id=device_id,
                    resource_type="command",
                    resource_id=request_id,
                    status="pending",
                    details={
                        "command": command[:200],
                        "request_id": request_id,
                    },
                )
            )

        # 转发命令到设备
        if device_id and await self.conn_mgr.is_device_connected(device_id):
            await self.send_to_device(device_id, MessageType.CMD_REQUEST, data)
        else:
            logger.warning(f"设备未连接，无法执行命令: {device_id}")

    async def handle_cmd_response(self, device_id: str, data: dict) -> None:
        """处理命令响应"""
        request_id = data.get("request_id")
        status = data.get("status", "unknown")
        exit_code = data.get("exit_code")
        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")

        logger.info(
            f"收到命令响应 [{device_id}]: request_id={request_id}, status={status}"
        )

        # 数据库操作：更新命令执行结果
        if request_id:
            try:
                success = exit_code == 0 if exit_code is not None else None
                await CommandHistoryRepository.update_result(
                    request_id=request_id,
                    status=status,
                    exit_code=exit_code,
                    success=success,
                    stdout=stdout,
                    stderr=stderr,
                    completed_at=datetime.now(),
                )
                logger.info(f"[DB] 命令执行结果已更新: request_id={request_id}")
            except Exception as e:
                logger.error(f"[DB] 更新命令执行结果失败: {e}")

            # 记录审计日志（异步，不阻塞主流程）
            asyncio.create_task(
                AuditLogRepository.insert(
                    event_type="command_execution",
                    action="command_completed",
                    actor_type="device",
                    actor_id=device_id,
                    device_id=device_id,
                    resource_type="command",
                    resource_id=request_id,
                    status="success" if exit_code == 0 else "failure",
                    result_message=f"Exit code: {exit_code}",
                    details={
                        "exit_code": exit_code,
                        "stdout_length": len(stdout) if stdout else 0,
                        "stderr_length": len(stderr) if stderr else 0,
                    },
                )
            )
        else:
            logger.warning("CMD_RESPONSE缺少request_id，不发送")
