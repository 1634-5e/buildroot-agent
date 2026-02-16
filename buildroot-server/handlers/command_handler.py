import logging

from handlers.base import BaseHandler
from protocol.constants import MessageType

logger = logging.getLogger(__name__)


class CommandHandler(BaseHandler):
    async def handle_cmd_request(self, device_id: str, data: dict, websocket) -> None:
        if device_id and self.conn_mgr.is_device_connected(device_id):
            await self.send_to_device(device_id, MessageType.CMD_REQUEST, data)
        else:
            logger.warning(f"设备未连接，无法执行命令: {device_id}")

    async def handle_cmd_response(self, device_id: str, data: dict) -> None:
        logger.info(f"收到命令响应 [{device_id}]: {data}")
        request_id = data.get("request_id")
        if request_id:
            await self.unicast_by_request_id(
                MessageType.CMD_RESPONSE,
                {"device_id": device_id, **data},
                request_id,
            )
        else:
            logger.warning(f"CMD_RESPONSE缺少request_id，不发送")
