import asyncio
import json
import logging
from websockets.server import WebSocketServerProtocol

from protocol.constants import MessageType

logger = logging.getLogger(__name__)


class SocketHandler:
    """Agent Socket 连接处理器"""

    def __init__(self, connection_manager, message_handler):
        self.conn_mgr = connection_manager
        self.msg_handler = message_handler

    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        try:
            addr = writer.get_extra_info("peername")
            logger.info(f"新Agent Socket连接: {addr}")

            device_id = None
            authenticated = False

            while True:
                try:
                    type_byte = await reader.readexactly(1)
                    msg_type = type_byte[0]

                    length_bytes = await reader.readexactly(2)
                    json_len = (length_bytes[0] << 8) | length_bytes[1]

                    if json_len > 65535:
                        logger.error(f"消息长度过大: {json_len}")
                        break

                    data = await reader.readexactly(json_len)

                    if msg_type == MessageType.AUTH and not authenticated:
                        try:
                            json_str = data.decode("utf-8")
                            json_data = json.loads(json_str)
                            device_id = json_data.get("device_id", "unknown")

                            await self.msg_handler.handle_auth(
                                self._create_socket_writer_wrapper(writer), json_data
                            )
                            authenticated = True
                        except json.JSONDecodeError as e:
                            logger.error(f"解析注册消息失败: {e}")
                            logger.debug(f"原始JSON数据（前200字节）: {json_str[:200]}")
                            writer.close()
                            await writer.wait_closed()
                            return
                        except Exception as e:
                            logger.error(f"处理注册消息异常: {e}")
                            writer.close()
                            await writer.wait_closed()
                            return

                    elif authenticated and device_id:
                        logger.info(
                            f"收到Agent消息 [0x{msg_type:02X}] 从 {device_id}, 长度={json_len}"
                        )
                        full_message = bytes([msg_type]) + length_bytes + data
                        await self.msg_handler.handle_message(
                            self._create_socket_writer_wrapper(writer),
                            device_id,
                            full_message,
                            is_socket=True,
                        )

                except asyncio.IncompleteReadError:
                    logger.info(f"Agent连接断开: {addr}")
                    break
                except Exception as e:
                    logger.error(f"处理Socket消息错误: {e}")
                    break

        finally:
            if device_id:
                self.conn_mgr.remove_device(device_id)
                await self._notify_device_list_update()
            writer.close()
            await writer.wait_closed()

    def _create_socket_writer_wrapper(self, writer: asyncio.StreamWriter):
        class SocketWriterWrapper:
            def __init__(self, w):
                self.writer = w

            async def send(self, message: bytes):
                self.writer.write(message)
                await self.writer.drain()

            async def close(self):
                self.writer.close()
                await self.writer.wait_closed()

        return SocketWriterWrapper(writer)

    async def _notify_device_list_update(self):
        device_list = self.conn_mgr.get_all_devices()
        await self.msg_handler.broadcast_to_web_consoles(
            MessageType.DEVICE_LIST, {"devices": device_list, "count": len(device_list)}
        )
