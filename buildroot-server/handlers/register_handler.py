import logging
from typing import Any

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
        self.conn_mgr.add_device(device_id, connection, conn_type)

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
