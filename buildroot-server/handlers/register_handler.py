import logging
from datetime import datetime
from typing import Any, Optional

from database.repositories import DeviceRepository, AuditLogRepository
from handlers.base import BaseHandler
from protocol.constants import MessageType
from protocol.codec import MessageCodec

logger = logging.getLogger(__name__)


class RegisterHandler(BaseHandler):
    """设备注册处理器"""

    async def handle_device_connect(
        self,
        connection: Any,
        device_id: str,
        version: str,
        conn_type: str = "websocket",
    ) -> bool:
        """处理设备连接（注册模式）"""
        logger.info(
            f"[REGISTER] 开始处理设备连接: {device_id} (版本: {version}, 类型: {conn_type})"
        )

        # 步骤1: 首先添加到连接管理器（必须在发送响应前完成）
        logger.info(f"[REGISTER] 步骤1: 添加到连接管理器 - {device_id}")
        await self.conn_mgr.add_device(device_id, connection, conn_type)
        logger.info(f"[REGISTER] 步骤1完成: 设备已添加到连接管理器 - {device_id}")

        # 步骤2: 立即发送注册响应（避免数据库操作延迟影响）
        logger.info(f"[REGISTER] 步骤2: 准备发送注册响应 - {device_id}")
        response = MessageCodec.encode(
            MessageType.REGISTER_RESULT, {"success": True, "message": "注册成功"}
        )

        try:
            if hasattr(connection, "send") and callable(
                getattr(connection, "send", None)
            ):
                logger.info(
                    f"[REGISTER] 正在发送注册响应给 {device_id}, 响应大小={len(response)} bytes"
                )
                await connection.send(response)
                logger.info(f"[REGISTER] 注册响应发送完成: {device_id}")
            else:
                logger.error(f"[REGISTER] 连接对象没有send方法: {device_id}")
                return False
        except Exception as e:
            import traceback

            logger.error(f"[REGISTER] 发送注册响应失败: {device_id}, {e}")
            logger.error(f"[REGISTER] 异常堆栈: {traceback.format_exc()}")
            return False

        # 步骤3: 异步执行数据库操作（不阻塞响应发送）
        logger.info(f"[REGISTER] 步骤3: 开始数据库操作 - {device_id}")
        try:
            await DeviceRepository.create_or_update(
                device_id=device_id,
                version=version,
                last_connected_at=datetime.now(),
            )
            await DeviceRepository.update_connection_status(
                device_id=device_id,
                status="online",
                is_online=True,
                last_seen_at=datetime.now(),
            )

            # 记录审计日志
            remote_addr = self._get_remote_address(connection, conn_type)
            await AuditLogRepository.insert(
                event_type="device_connect",
                action="connect",
                actor_type="device",
                actor_id=device_id,
                device_id=device_id,
                resource_type="device",
                resource_id=device_id,
                status="success",
                details={
                    "version": version,
                    "conn_type": conn_type,
                    "remote_addr": remote_addr,
                },
            )

            logger.info(f"[REGISTER] 步骤3完成: 数据库操作成功 - {device_id}")
        except Exception as e:
            import traceback

            logger.error(f"[REGISTER] 数据库操作失败: {device_id}, {e}")
            logger.error(f"[REGISTER] 异常堆栈: {traceback.format_exc()}")
            # 数据库操作失败不影响注册成功，因为连接已经建立

        logger.info(f"[REGISTER] 设备连接处理完成: {device_id}")
        return True

    def _get_remote_address(self, connection: Any, conn_type: str) -> Optional[str]:
        """获取远程地址"""
        try:
            if conn_type == "websocket":
                remote = getattr(connection, "remote_address", "unknown")
                return remote[0] if isinstance(remote, tuple) else str(remote)
            elif conn_type == "socket":
                writer = connection
                addr = writer.get_extra_info("peername")
                return f"{addr[0]}:{addr[1]}" if addr else "unknown"
            else:
                return "unknown"
        except Exception:
            return "unknown"
