import logging
import time
import websockets
from typing import Optional
from websockets.server import WebSocketServerProtocol

from protocol.constants import MessageType
from protocol.codec import MessageCodec
from protocol.models import DeviceList

logger = logging.getLogger(__name__)


class BaseHandler:
    """Handler 基类"""

    def __init__(self, conn_mgr):
        self.conn_mgr = conn_mgr

    @staticmethod
    def create_message(msg_type: int, data: dict) -> bytes:
        return MessageCodec.encode(msg_type, data)

    async def _safe_send(self, websocket, message: bytes) -> bool:
        try:
            if hasattr(websocket, "state"):
                if websocket.state.name != "OPEN":
                    logger.debug("WebSocket连接未开启，跳过发送")
                    return False

            if hasattr(websocket, "send") and callable(
                getattr(websocket, "send", None)
            ):
                await websocket.send(message)
                logger.debug(f"消息已发送，长度={len(message)}")
                return True
            else:
                logger.error("WebSocket对象没有send方法")
                return False
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket连接已关闭: code={e.code}, reason={e.reason}")
            return False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def send_to_device(self, device_id: str, msg_type: int, data: dict) -> bool:
        if not self.conn_mgr.is_device_connected(device_id):
            logger.warning(f"设备未连接: {device_id}")
            return False

        try:
            dev_info = self.conn_mgr.get_device(device_id)
            if not dev_info:
                logger.error(f"设备连接为空: {device_id}")
                return False

            conn_type = dev_info["type"]
            connection = dev_info["connection"]

            message = self.create_message(msg_type, data)
            logger.debug(
                f"[SEND_TO_DEVICE] device={device_id}, type=0x{msg_type:02X}, msg_hex={message.hex()[:50]}...{message.hex()[-30:] if len(message.hex()) > 80 else ''}, total_len={len(message)}"
            )

            if conn_type == "websocket":
                if hasattr(connection, "state") and connection.state.name != "OPEN":
                    logger.warning(f"设备WebSocket连接未开启: {device_id}")
                    self.conn_mgr.remove_device(device_id)
                    return False

                if not hasattr(connection, "send") or not callable(
                    getattr(connection, "send", None)
                ):
                    logger.error(f"设备WebSocket无效: {device_id}")
                    return False

                await connection.send(message)
                return True

            elif conn_type == "socket":
                if hasattr(connection, "send") and callable(
                    getattr(connection, "send", None)
                ):
                    await connection.send(message)
                    return True
                else:
                    logger.error(f"设备Socket无效: {device_id}")
                    return False

            else:
                logger.warning(f"未知的连接类型: {conn_type}")
                return False

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(
                f"设备连接已关闭: {device_id}, code={e.code}, reason={e.reason}"
            )
            self.conn_mgr.remove_device(device_id)
            return False
        except Exception as e:
            logger.error(f"发送失败: {e}")
            return False

    async def broadcast_to_web_consoles(
        self,
        msg_type: int,
        data: dict,
        target_console_id: Optional[str] = None,
        target_device_id: Optional[str] = None,
    ) -> None:
        if not self.conn_mgr.web_consoles:
            return

        try:
            message = self.create_message(msg_type, data)
            to_remove = []

            for console in list(self.conn_mgr.web_consoles):
                try:
                    if hasattr(console, "state") and console.state.name != "OPEN":
                        logger.debug("Web控制台连接未开启，移除连接")
                        to_remove.append(console)
                        continue

                    console_info = self.conn_mgr.get_console_info(console)
                    if not console_info:
                        to_remove.append(console)
                        continue

                    if (
                        target_console_id
                        and console_info.get("console_id") != target_console_id
                    ):
                        continue

                    if (
                        target_device_id
                        and console_info.get("device_id") is not None
                        and console_info.get("device_id") != target_device_id
                    ):
                        continue

                    if hasattr(console, "send") and callable(
                        getattr(console, "send", None)
                    ):
                        await console.send(message)
                    else:
                        logger.warning("Web控制台没有send方法")
                        to_remove.append(console)
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(
                        f"Web控制台连接已关闭: code={e.code}, reason={e.reason}"
                    )
                    to_remove.append(console)
                except Exception as e:
                    logger.warning(f"向web控制台发送失败: {e}")
                    to_remove.append(console)

            for console in to_remove:
                self.conn_mgr.remove_console(console)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")

    async def unicast_by_request_id(
        self,
        msg_type: int,
        data: dict,
        request_id: str,
    ) -> None:
        target_console = self.conn_mgr.get_console_by_request(request_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            try:
                message = self.create_message(msg_type, data)
                await target_console.send(message)
                logger.debug(
                    f"单播消息 [0x{msg_type:02X}] by request_id={request_id} to console={target_console_id}"
                )
            except Exception as e:
                logger.warning(f"单播消息失败: {e}")
        else:
            logger.warning(f"未找到request_id对应的console: request_id={request_id}")

    async def notify_device_list_update(self) -> None:
        device_list = self.conn_mgr.get_all_devices()
        await self.broadcast_to_web_consoles(
            MessageType.DEVICE_LIST,
            DeviceList(devices=device_list, count=len(device_list)).model_dump(),
        )

    async def notify_device_disconnect(
        self, device_id: str, reason: str = "disconnect"
    ) -> None:
        """通知设备断开，仅发送给已连接该设备的 web 控制台"""
        data = {
            "device_id": device_id,
            "reason": reason,
            "timestamp": int(time.time() * 1000),
        }
        await self.broadcast_to_web_consoles(
            MessageType.DEVICE_DISCONNECT, data, target_device_id=device_id
        )
