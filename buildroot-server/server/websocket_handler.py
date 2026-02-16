import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol

from protocol.constants import MessageType

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """WebSocket 连接处理器"""

    def __init__(self, conn_mgr, msg_handler):
        self.conn_mgr = conn_mgr
        self.msg_handler = msg_handler

    async def agent_handler(self, websocket: WebSocketServerProtocol) -> None:
        try:
            remote = getattr(websocket, "remote_address", "unknown")
        except:
            remote = "unknown"
        logger.info(f"新连接: {remote}")

        self.conn_mgr.add_console(websocket)

        device_id: str | None = None
        authenticated = False
        is_device = False

        try:
            if not hasattr(websocket, "__aiter__"):
                logger.error("WebSocket不支持异步迭代")
                return

            async for message in websocket:
                if len(message) < 1:
                    continue

                msg_type = message[0]

                if msg_type == MessageType.AUTH and not is_device:
                    is_device = True
                    self.conn_mgr.remove_console(websocket)

                    try:
                        auth_len = (message[1] << 8) | message[2]
                        json_data = json.loads(
                            message[3 : 3 + auth_len].decode("utf-8")
                        )
                        device_id = json_data.get("device_id", "unknown")
                        authenticated = await self.msg_handler.handle_auth(
                            websocket, json_data
                        )
                        if authenticated:
                            pass
                        else:
                            if hasattr(websocket, "close") and callable(
                                getattr(websocket, "close", None)
                            ):
                                await websocket.close()
                            return
                    except Exception as e:
                        logger.error(f"解析认证消息失败: {e}")
                        if hasattr(websocket, "close") and callable(
                            getattr(websocket, "close", None)
                        ):
                            await websocket.close()
                        return

                if is_device and authenticated and device_id:
                    if len(message) >= 1:
                        msg_type = message[0]
                        logger.info(f"收到设备消息 [0x{msg_type:02X}] 从 {device_id}")
                    await self.msg_handler.handle_message(websocket, device_id, message)

                elif not is_device:
                    try:
                        logger.debug(
                            f"[RECV_WEB] raw_hex={message.hex()[:50]}...{message.hex()[-30:] if len(message.hex()) > 80 else ''}, len={len(message)}"
                        )
                        json_len = (message[1] << 8) | message[2]
                        logger.debug(
                            f"[RECV_WEB] msg_type=0x{message[0]:02X}, json_len={json_len}, len_high={message[1]:02X}, len_low={message[2]:02X}"
                        )
                        json_str = message[3 : 3 + json_len].decode("utf-8")
                        json_data = json.loads(json_str)

                        console_id = json_data.pop("console_id", None)
                        device_id = json_data.get("device_id")

                        console_info = self.conn_mgr.get_console_info(websocket)
                        if console_info:
                            if device_id:
                                self.conn_mgr.set_console_device(websocket, device_id)
                            session_id = json_data.get("session_id")
                            if session_id:
                                try:
                                    self.conn_mgr.add_console_session(
                                        websocket, int(session_id)
                                    )
                                except (ValueError, TypeError):
                                    logger.warning(f"无效的session_id: {session_id}")
                            request_id = json_data.get("request_id")
                            if request_id and device_id:
                                self.conn_mgr.add_request_session(
                                    request_id,
                                    console_info.get("console_id", ""),
                                    device_id,
                                )

                        device_info = device_id if device_id else "所有设备"
                        actual_console_id = (
                            console_info.get("console_id", console_id)
                            if console_info
                            else console_id
                        )
                        logger.info(
                            f"Web控制台 [{actual_console_id}] 收到消息 [0x{msg_type:02X}] for device: {device_info}, data: {json_str[:200]}"
                        )

                        if device_id:
                            logger.info(
                                f"Web控制台消息 [0x{msg_type:02X}] 转发到设备: {device_id}"
                            )

                            success = await self.msg_handler.send_to_device(
                                device_id, msg_type, json_data
                            )
                            if success:
                                logger.info(f"消息已转发到设备 {device_id}")
                            else:
                                logger.warning(f"转发消息到设备失败: {device_id}")
                        else:
                            if msg_type == MessageType.DEVICE_LIST:
                                page = json_data.get("page", 0)
                                page_size = json_data.get("page_size", 20)
                                search_keyword = json_data.get(
                                    "search_keyword", ""
                                ).lower()
                                sort_by = json_data.get("sort_by", "device_id")
                                sort_order = json_data.get("sort_order", "asc")

                                all_devices = self.conn_mgr.get_all_devices()

                                filtered_devices = all_devices
                                if search_keyword:
                                    filtered_devices = [
                                        d
                                        for d in all_devices
                                        if search_keyword
                                        in d.get("device_id", "").lower()
                                    ]

                                if sort_by:
                                    reverse = sort_order.lower() == "desc"
                                    filtered_devices.sort(
                                        key=lambda x: x.get(sort_by, ""),
                                        reverse=reverse,
                                    )

                                total_count = len(filtered_devices)
                                start_index = page * page_size
                                end_index = start_index + page_size
                                paged_devices = filtered_devices[start_index:end_index]

                                response = self.msg_handler.create_message(
                                    MessageType.DEVICE_LIST,
                                    {
                                        "devices": paged_devices,
                                        "total_count": total_count,
                                        "page": page,
                                        "page_size": page_size,
                                    },
                                )
                                if hasattr(websocket, "send") and callable(
                                    getattr(websocket, "send", None)
                                ):
                                    await websocket.send(response)
                                    logger.info("设备列表已发送到web控制台")
                    except Exception as e:
                        logger.error(f"Web控制台消息处理失败: {e}")

        except websockets.exceptions.ConnectionClosed as e:
            if is_device:
                logger.info(
                    f"设备连接关闭: {device_id or remote}, code: {e.code}, reason: {e.reason}"
                )
                if device_id:
                    self.conn_mgr.remove_device(device_id)
                    logger.info(f"设备断开: {device_id}")
                    await self.msg_handler.notify_device_disconnect(device_id)
            else:
                logger.info(
                    f"Web控制台断开: {remote}, code: {e.code}, reason: {e.reason}"
                )
                device_id, session_ids = self.conn_mgr.remove_console(websocket)
                if (
                    device_id
                    and session_ids
                    and self.conn_mgr.is_device_connected(device_id)
                ):
                    for session_id in session_ids:
                        await self.msg_handler.send_to_device(
                            device_id,
                            MessageType.PTY_CLOSE,
                            {
                                "session_id": session_id,
                                "reason": "console disconnected",
                            },
                        )
        except Exception as e:
            logger.error(f"连接处理错误: {e}")
        finally:
            if not is_device:
                device_id, session_ids = self.conn_mgr.remove_console(websocket)
                if (
                    device_id
                    and session_ids
                    and self.conn_mgr.is_device_connected(device_id)
                ):
                    for session_id in session_ids:
                        await self.msg_handler.send_to_device(
                            device_id,
                            MessageType.PTY_CLOSE,
                            {
                                "session_id": session_id,
                                "reason": "console disconnected",
                            },
                        )
