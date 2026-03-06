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
        logger.info(f"设备已连接: {device_id} (版本: {version}, 类型: {conn_type})")

        # 添加到连接管理器（内存）
        await self.conn_mgr.add_device(device_id, connection, conn_type)

        # 数据库操作：创建或更新设备信息
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

            logger.info(f"[DB] 设备信息已保存: {device_id}")
        except Exception as e:
            import traceback

            logger.error(f"[DB] 保存设备信息失败: {e}\n{traceback.format_exc()}")

        # 发送注册结果响应
        response = MessageCodec.encode(
            MessageType.REGISTER_RESULT, {"success": True, "message": "注册成功"}
        )

        try:
            if hasattr(connection, "send") and callable(
                getattr(connection, "send", None)
            ):
                await connection.send(response)
                logger.info(f"注册结果已发送: {device_id}")
            else:
                logger.error(f"连接对象没有send方法: {device_id}")
                return False
        except Exception as e:
            logger.error(f"发送注册结果失败: {device_id}, {e}")
            return False

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
