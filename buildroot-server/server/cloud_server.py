import asyncio
import logging
import os
import websockets

from config.settings import settings
from managers.connection import ConnectionManager
from managers.file_transfer import FileTransferManager
from handlers.register_handler import RegisterHandler
from handlers.system_handler import SystemHandler
from handlers.pty_handler import PtyHandler
from handlers.file_handler import FileHandler
from handlers.update_handler import UpdateHandler
from handlers.ping_handler import PingHandler
from handlers.command_handler import CommandHandler
from server.websocket_handler import WebSocketHandler
from handlers.socket_handler import SocketHandler
from protocol.constants import MessageType
from protocol.codec import MessageCodec
from typing import Optional

logger = logging.getLogger(__name__)


class MessageRouter:
    """消息路由器 - 路由消息到各个Handler"""

    def __init__(self, conn_mgr: ConnectionManager):
        self.conn_mgr = conn_mgr

        self.register_handler = RegisterHandler(conn_mgr)
        self.system_handler = SystemHandler(conn_mgr)
        self.pty_handler = PtyHandler(conn_mgr)
        self.file_handler = FileHandler(conn_mgr)
        self.update_handler = UpdateHandler(conn_mgr)
        self.ping_handler = PingHandler(conn_mgr)
        self.command_handler = CommandHandler(conn_mgr)

        self.download_chunks = {}
        self._max_download_chunks = 100

    def _cleanup_download_chunks(self):
        if len(self.download_chunks) > self._max_download_chunks:
            oldest_keys = list(self.download_chunks.keys())[
                : len(self.download_chunks) - self._max_download_chunks
            ]
            for key in oldest_keys:
                del self.download_chunks[key]
            logger.debug(f"清理 download_chunks: {len(oldest_keys)} 个")

    async def send_to_device(self, device_id: str, msg_type: int, data: dict) -> bool:
        """发送消息到指定设备"""
        if not await self.conn_mgr.is_device_connected(device_id):
            logger.warning(f"设备未连接: {device_id}")
            return False

        try:
            dev_info = await self.conn_mgr.get_device(device_id)
            if not dev_info:
                logger.error(f"设备连接为空: {device_id}")
                return False

            conn_type = dev_info["type"]
            connection = dev_info["connection"]

            message = MessageCodec.encode(msg_type, data)
            logger.debug(
                f"[SEND_TO_DEVICE] device={device_id}, type=0x{msg_type:02X}, msg_hex={message.hex()[:50]}...{message.hex()[-30:] if len(message.hex()) > 80 else ''}, total_len={len(message)}"
            )

            if conn_type == "websocket":
                if hasattr(connection, "state") and connection.state.name != "OPEN":
                    logger.warning(f"设备WebSocket连接未开启: {device_id}")
                    await self.conn_mgr.remove_device(device_id)
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
            await self.conn_mgr.remove_device(device_id)
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
        """广播消息到Web控制台 - 复用 BaseHandler 实现"""
        return await self.register_handler.broadcast_to_web_consoles(
            msg_type, data, target_console_id, target_device_id
        )

    async def handle_auth(self, websocket, data: dict) -> bool:
        return await self.register_handler.handle_auth(websocket, data)

    async def handle_heartbeat(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_heartbeat(device_id, data)

    async def handle_system_status(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_system_status(device_id, data)

    async def handle_log_upload(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_log_upload(device_id, data)

    async def handle_script_result(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_script_result(device_id, data)

    async def handle_auth_result(self, device_id: str, data: dict) -> None:
        await self.register_handler.handle_auth_result(device_id, data)

    async def handle_device_connect(
        self, connection, device_id: str, version: str, conn_type: str = "websocket"
    ) -> bool:
        """处理设备连接（注册模式）"""
        return await self.register_handler.handle_device_connect(
            connection, device_id, version, conn_type
        )

    async def handle_update_check(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_check(device_id, data)

    async def handle_update_download(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_download(device_id, data)

    async def handle_update_progress(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_progress(device_id, data)

    async def handle_update_complete(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_complete(device_id, data)

    async def handle_update_error(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_error(device_id, data)

    async def handle_update_rollback(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_rollback(device_id, data)

    async def handle_update_request_approval(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_request_approval(device_id, data)

    async def handle_update_download_ready(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_download_ready(device_id, data)

    async def handle_update_approve_install(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_approve_install(device_id, data)

    async def handle_update_deny(self, device_id: str, data: dict) -> None:
        await self.update_handler.handle_update_deny(device_id, data)

    async def handle_update_approve_download(self, device_id: str, data: dict) -> None:
        try:
            logger.info(f"[{device_id}] 收到Web下载批准，转发到Agent")
            await self.send_to_device(
                device_id, MessageType.UPDATE_APPROVE_DOWNLOAD, data
            )
        except Exception as e:
            logger.error(f"[{device_id}] 转发下载批准失败: {e}")

    async def unicast_by_request_id(
        self, msg_type: int, data: dict, request_id: str
    ) -> None:
        return await self.register_handler.unicast_by_request_id(
            msg_type, data, request_id
        )

    async def notify_device_list_update(self) -> None:
        return await self.register_handler.notify_device_list_update()

    async def notify_device_disconnect(
        self, device_id: str, reason: str = "disconnect"
    ) -> None:
        return await self.register_handler.notify_device_disconnect(device_id, reason)

    async def handle_file_download_request(self, device_id: str, data: dict) -> None:
        return await self.file_handler.handle_file_download_request(device_id, data)

    async def handle_pty_data(self, device_id: str, data: dict) -> None:
        return await self.pty_handler.handle_pty_data(device_id, data)

    async def handle_pty_create(self, device_id: str, data: dict) -> None:
        return await self.pty_handler.handle_pty_create(device_id, data)

    async def handle_pty_resize(self, device_id: str, data: dict) -> None:
        return await self.pty_handler.handle_pty_resize(device_id, data)

    async def handle_pty_close(self, device_id: str, data: dict) -> None:
        return await self.pty_handler.handle_pty_close(device_id, data)

    async def handle_message(
        self, websocket, device_id: str, data: bytes, is_socket: bool = False
    ) -> None:
        msg_type = None
        json_data = {}

        import json

        if len(data) >= 3:
            msg_type = data[0]
            length_bytes = data[1:3]
            json_len = (length_bytes[0] << 8) | length_bytes[1]
            if len(data) >= 3 + json_len:
                json_data_bytes = data[3 : 3 + json_len]
                try:
                    json_str = json_data_bytes.decode("utf-8")
                    if json_str.strip():
                        json_data = json.loads(json_str)
                except Exception:
                    json_data = {}

        json_data = json_data or {}

        handlers = {
            MessageType.HEARTBEAT: self.handle_heartbeat,
            MessageType.SYSTEM_STATUS: self.handle_system_status,
            MessageType.LOG_UPLOAD: self.handle_log_upload,
            MessageType.SCRIPT_RESULT: self.handle_script_result,
            MessageType.UPDATE_CHECK: self.handle_update_check,
            MessageType.UPDATE_DOWNLOAD: self.handle_update_download,
            MessageType.UPDATE_PROGRESS: self.handle_update_progress,
            MessageType.UPDATE_COMPLETE: self.handle_update_complete,
            MessageType.UPDATE_ERROR: self.handle_update_error,
            MessageType.UPDATE_ROLLBACK: self.handle_update_rollback,
            MessageType.UPDATE_REQUEST_APPROVAL: self.handle_update_request_approval,
            MessageType.UPDATE_DOWNLOAD_READY: self.handle_update_download_ready,
            MessageType.UPDATE_APPROVE_INSTALL: self.handle_update_approve_install,
            MessageType.PING_STATUS: self.ping_handler.handle_ping_status,
            MessageType.UPDATE_DENY: self.handle_update_deny,
            MessageType.UPDATE_APPROVE_DOWNLOAD: self.handle_update_approve_download,
        }

        if msg_type in handlers:
            await handlers[msg_type](device_id, json_data)
            return

        if msg_type == MessageType.FILE_LIST_REQUEST:
            if device_id and await self.conn_mgr.is_device_connected(device_id):
                await self.send_to_device(device_id, msg_type, json_data)
            return
        elif msg_type == MessageType.FILE_REQUEST:
            if device_id and await self.conn_mgr.is_device_connected(device_id):
                await self.send_to_device(device_id, msg_type, json_data)
            return
        elif msg_type == MessageType.FILE_DOWNLOAD_REQUEST:
            await self.handle_file_download_request(device_id, json_data)
            return
        elif msg_type in (
            MessageType.PTY_CREATE,
            MessageType.PTY_DATA,
            MessageType.PTY_RESIZE,
            MessageType.PTY_CLOSE,
        ):
            is_from_device = is_socket
            if is_from_device:
                if msg_type == MessageType.PTY_DATA:
                    await self.handle_pty_data(device_id, json_data)
                elif msg_type == MessageType.PTY_CREATE:
                    await self.handle_pty_create(device_id, json_data)
                elif msg_type == MessageType.PTY_RESIZE:
                    await self.handle_pty_resize(device_id, json_data)
                elif msg_type == MessageType.PTY_CLOSE:
                    await self.handle_pty_close(device_id, json_data)
                return
            else:
                if device_id and await self.conn_mgr.is_device_connected(device_id):
                    await self.send_to_device(device_id, msg_type, json_data)
                return

        if msg_type == MessageType.FILE_DATA:
            request_id = json_data.get("request_id")
            if request_id:
                await self.unicast_by_request_id(
                    MessageType.FILE_DATA,
                    {"device_id": device_id, **json_data},
                    request_id,
                )
        elif msg_type == MessageType.FILE_LIST_RESPONSE:
            request_id = json_data.get("request_id")
            if request_id:
                await self.unicast_by_request_id(
                    MessageType.FILE_LIST_RESPONSE,
                    {"device_id": device_id, **json_data},
                    request_id,
                )
        elif msg_type == MessageType.DOWNLOAD_PACKAGE:
            await self._handle_download_package(device_id, json_data)
        elif msg_type == MessageType.CMD_RESPONSE:
            request_id = json_data.get("request_id")
            if request_id:
                await self.unicast_by_request_id(
                    MessageType.CMD_RESPONSE,
                    {"device_id": device_id, **json_data},
                    request_id,
                )
        elif msg_type == MessageType.DEVICE_LIST:
            page = json_data.get("page", 0)
            page_size = json_data.get("page_size", 20)
            search_keyword = json_data.get("search_keyword", "").lower()
            sort_by = json_data.get("sort_by", "device_id")
            sort_order = json_data.get("sort_order", "asc")

            logger.debug(
                f"[DEVICE_LIST] 收到Socket请求 - "
                f"page={page}, page_size={page_size}, "
                f"search_keyword='{search_keyword}', sort_by={sort_by}, sort_order={sort_order}"
            )

            all_devices = await self.conn_mgr.get_all_devices()

            logger.info(
                f"[DEVICE_LIST] 当前连接设备数={len(all_devices)}, "
                f"设备列表={[d['device_id'] for d in all_devices]}"
            )

            filtered_devices = all_devices
            if search_keyword:
                filtered_devices = [
                    d
                    for d in all_devices
                    if search_keyword in d.get("device_id", "").lower()
                ]
                logger.debug(
                    f"[DEVICE_LIST] 搜索关键词='{search_keyword}' - "
                    f"过滤前={len(all_devices)}, 过滤后={len(filtered_devices)}"
                )

            if sort_by:
                reverse = sort_order.lower() == "desc"
                filtered_devices.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
                logger.debug(
                    f"[DEVICE_LIST] 排序 - sort_by={sort_by}, reverse={reverse}, "
                    f"前3个设备={[d.get('device_id') for d in filtered_devices[:3]]}"
                )

            total_count = len(filtered_devices)
            start_index = page * page_size
            end_index = start_index + page_size
            paged_devices = filtered_devices[start_index:end_index]

            logger.debug(
                f"[DEVICE_LIST] 分页计算 - "
                f"total_count={total_count}, page={page}, page_size={page_size}, "
                f"start_index={start_index}, end_index={end_index}, "
                f"返回设备数={len(paged_devices)}"
            )

            if total_count == 0:
                logger.warning(
                    f"[DEVICE_LIST] 返回空设备列表 - "
                    f"search_keyword='{search_keyword}', 可能原因: 无设备连接或搜索无匹配"
                )

            response = MessageCodec.encode(
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
                logger.info(
                    f"[DEVICE_LIST] 已发送到Web控制台 - "
                    f"当前页={page + 1}/{((total_count - 1) // page_size) + 1 if total_count > 0 else 0}, "
                    f"本页设备={len(paged_devices)}, 总设备={total_count}, "
                    f"设备IDs={[d['device_id'] for d in paged_devices]}"
                )
        else:
            logger.debug(f"未知消息类型: 0x{msg_type:02X}")

    async def _handle_download_package(self, device_id: str, json_data: dict) -> None:
        request_id = json_data.get("request_id", f"{device_id}-download")
        chunk_index = json_data.get("chunk_index", 0)
        total_chunks = json_data.get("total_chunks", 1)
        content = json_data.get("content", "")

        logger.info(
            f"收到打包分块 [{device_id}]: request_id={request_id}, chunk={chunk_index + 1}/{total_chunks}"
        )

        if request_id not in self.download_chunks:
            self._cleanup_download_chunks()
            self.download_chunks[request_id] = {
                "chunks": [None] * total_chunks,
                "total": total_chunks,
                "filename": json_data.get("filename", "unknown"),
                "size": json_data.get("size", 0),
                "device_id": device_id,
            }

        chunk_data = self.download_chunks[request_id]
        chunk_data["chunks"][chunk_index] = content

        chunk_info = {
            "device_id": device_id,
            "filename": chunk_data["filename"],
            "size": chunk_data["size"],
            "content": content,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "request_id": request_id,
        }

        if chunk_index == 0:
            chunk_info["is_first"] = True
            logger.info(f"转发首块到Web: {chunk_index + 1}/{total_chunks}")
        elif chunk_index == total_chunks - 1:
            chunk_info["is_last"] = True
            logger.info(f"转发末块到Web: {chunk_index + 1}/{total_chunks}, 删除会话")
            del self.download_chunks[request_id]
        else:
            logger.debug(f"转发中间块到Web: {chunk_index + 1}/{total_chunks}")

        await self.broadcast_to_web_consoles(MessageType.DOWNLOAD_PACKAGE, chunk_info)


class CloudServer:
    """云端服务器主类"""

    # 类变量，用于共享连接管理器
    conn_mgr: ConnectionManager = None

    def __init__(self):
        self.file_transfer = FileTransferManager()
        self.conn_mgr = ConnectionManager(self.file_transfer)
        # 设置类变量，使其可以被其他模块访问
        CloudServer.conn_mgr = self.conn_mgr
        self.msg_handler = MessageRouter(self.conn_mgr)
        self.socket_handler = SocketHandler(self.conn_mgr, self.msg_handler)
        self.ws_handler = WebSocketHandler(self.conn_mgr, self.msg_handler)

    async def run(self) -> None:
        host = settings.host
        ws_port = settings.ws_port
        socket_port = settings.socket_port

        logger.info(f"启动WebSocket服务器（前端）: ws://{host}:{ws_port}")
        logger.info(f"启动Socket服务器（Agent）: {host}:{socket_port}")
        logger.info(f"文件上传目录: {os.path.abspath(settings.upload_dir)}")

        ws_server = await websockets.serve(
            self.ws_handler.agent_handler,
            host,
            ws_port,
            ping_interval=settings.ping_interval,
            ping_timeout=settings.ping_timeout,
        )

        socket_server = await asyncio.start_server(
            self.socket_handler.handle_connection, host, socket_port
        )

        logger.info("服务器运行中，按 Ctrl+C 停止")

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            ws_server.close()
            await ws_server.wait_closed()
            socket_server.close()
            await socket_server.wait_closed()
