import logging
from websockets.server import WebSocketServerProtocol

from handlers.base import BaseHandler
from protocol.constants import MessageType
from protocol.models import AuthRequest, AuthResult

logger = logging.getLogger(__name__)


class AuthHandler(BaseHandler):
    async def handle_auth(self, websocket: WebSocketServerProtocol, data: dict) -> bool:
        device_id = data.get("device_id", "unknown")
        version = data.get("version", "unknown")

        logger.info(f"设备注册成功: {device_id} (版本: {version})")
        self.conn_mgr.add_device(device_id, websocket)

        response = AuthResult(success=True, message=f"欢迎, {device_id}")
        response_msg = self.create_message(
            MessageType.AUTH_RESULT, response.model_dump()
        )
        logger.info(
            f"准备发送注册响应给 {device_id}, 消息长度={len(response_msg)}, 类型=0x{MessageType.AUTH_RESULT:02X}"
        )
        send_result = await self._safe_send(websocket, response_msg)
        logger.info(f"_safe_send返回结果: {send_result}")
        logger.info(f"注册响应{'已成功' if send_result else '发送失败'}给 {device_id}")
        return True

    async def handle_auth_result(self, device_id: str, data: dict) -> None:
        success = data.get("success", False)
        message = data.get("message", "")

        logger.info(
            f"设备认证结果 [{device_id}]: {'成功' if success else '失败'}, {message}"
        )

        await self.broadcast_to_web_consoles(
            MessageType.AUTH_RESULT, {"device_id": device_id, **data}
        )
