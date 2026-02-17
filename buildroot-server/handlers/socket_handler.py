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
            registered = False

            while True:
                try:
                    type_byte = await reader.readexactly(1)
                    msg_type = type_byte[0]

                    length_bytes = await reader.readexactly(2)
                    json_len = (length_bytes[0] << 8) | length_bytes[1]

                    logger.debug(
                        f"[SOCKET] 收到消息 - msg_type=0x{msg_type:02X}, "
                        f"json_len={json_len}, registered={registered}"
                    )

                    if json_len > 65535:
                        logger.error(f"消息长度过大: {json_len}")
                        break

                    data = await reader.readexactly(json_len)

                    # 注册模式：处理 REGISTER 消息（首次连接或重新注册）
                    if msg_type == MessageType.REGISTER:
                        logger.info(f"[SOCKET] 收到REGISTER注册消息 - 尝试注册设备")
                        try:
                            json_str = data.decode("utf-8")
                            json_data = json.loads(json_str)
                            new_device_id = json_data.get("device_id", "unknown")
                            version = json_data.get("version", "unknown")

                            # 如果device_id发生变化，先移除旧设备
                            if device_id and device_id != new_device_id:
                                self.conn_mgr.remove_device(device_id)
                                logger.info(
                                    f"设备ID变更: {device_id} -> {new_device_id}"
                                )

                            device_id = new_device_id

                            # 注册或更新连接
                            await self.msg_handler.handle_device_connect(
                                self._create_socket_writer_wrapper(writer),
                                device_id,
                                version,
                                "socket",
                            )
                            registered = True
                            continue
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

                    elif registered and device_id:
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
                await self._notify_device_disconnect(device_id)
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

    async def _notify_device_disconnect(self, device_id: str) -> None:
        """通知设备断开"""
        await self.msg_handler.notify_device_disconnect(device_id)
