import asyncio
import logging
import os
from websockets.server import WebSocketServerProtocol
import websockets

from config.settings import settings
from managers.connection import ConnectionManager
from managers.file_transfer import FileTransferManager
from managers.update import UpdateManager
from handlers.auth_handler import AuthHandler
from handlers.system_handler import SystemHandler
from handlers.pty_handler import PtyHandler
from handlers.file_handler import FileHandler
from handlers.update_handler import UpdateHandler
from handlers.command_handler import CommandHandler
from server.websocket_handler import WebSocketHandler
from handlers.socket_handler import SocketHandler
from console.interactive import InteractiveConsole

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息处理器整合类"""

    def __init__(self, conn_mgr: ConnectionManager):
        self.conn_mgr = conn_mgr

        self.auth_handler = AuthHandler(conn_mgr)
        self.system_handler = SystemHandler(conn_mgr)
        self.pty_handler = PtyHandler(conn_mgr)
        self.file_handler = FileHandler(conn_mgr)
        self.update_handler = UpdateHandler(conn_mgr)
        self.command_handler = CommandHandler(conn_mgr)

        self.download_chunks = {}

    async def handle_auth(self, websocket: WebSocketServerProtocol, data: dict) -> bool:
        return await self.auth_handler.handle_auth(websocket, data)

    async def handle_heartbeat(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_heartbeat(device_id, data)

    async def handle_system_status(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_system_status(device_id, data)

    async def handle_log_upload(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_log_upload(device_id, data)

    async def handle_script_result(self, device_id: str, data: dict) -> None:
        await self.system_handler.handle_script_result(device_id, data)

    async def handle_auth_result(self, device_id: str, data: dict) -> None:
        await self.auth_handler.handle_auth_result(device_id, data)

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

    async def handle_file_upload_start(self, device_id: str, data: dict, websocket: WebSocketServerProtocol) -> None:
        await self.file_handler.handle_file_upload_start(device_id, data, websocket)

    async def handle_file_upload_data(self, device_id: str, data: dict, raw_data: bytes, websocket: WebSocketServerProtocol) -> None:
        await self.file_handler.handle_file_upload_data(device_id, data, raw_data, websocket)

    async def handle_file_upload_complete(self, device_id: str, data: dict, websocket: WebSocketServerProtocol) -> None:
        await self.file_handler.handle_file_upload_complete(device_id, data, websocket)

    async def handle_file_download_request(self, device_id: str, data: dict) -> None:
        await self.file_handler.handle_file_download_request(device_id, data)

    async def handle_pty_data(self, device_id: str, data: dict) -> None:
        await self.pty_handler.handle_pty_data(device_id, data)

    async def handle_pty_create(self, device_id: str, data: dict) -> None:
        await self.pty_handler.handle_pty_create(device_id, data)

    async def handle_pty_resize(self, device_id: str, data: dict) -> None:
        await self.pty_handler.handle_pty_resize(device_id, data)

    async def handle_pty_close(self, device_id: str, data: dict) -> None:
        await self.pty_handler.handle_pty_close(device_id, data)

    async def handle_cmd_request(self, device_id: str, data: dict, websocket) -> None:
        await self.command_handler.handle_cmd_request(device_id, data, websocket)

    async def handle_cmd_response(self, device_id: str, data: dict) -> None:
        await self.command_handler.handle_cmd_response(device_id, data)

    async def create_message(self, msg_type: int, data: dict) -> bytes:
        return self.auth_handler.create_message(msg_type, data)

    async def send_to_device(self, device_id: str, msg_type: int, data: dict) -> bool:
        return await self.auth_handler.send_to_device(device_id, msg_type, data)

    async def broadcast_to_web_consoles(self, msg_type: int, data: dict, target_console_id: str = None, target_device_id: str = None) -> None:
        return await self.auth_handler.broadcast_to_web_consoles(msg_type, data, target_console_id, target_device_id)

    async def unicast_by_request_id(self, msg_type: int, data: dict, request_id: str) -> None:
        return await self.auth_handler.unicast_by_request_id(msg_type, data, request_id)

    async def notify_device_list_update(self) -> None:
        return await self.auth_handler.notify_device_list_update()

    async def handle_message(self, websocket, device_id: str, data: bytes, is_socket: bool = False) -> None:
        from protocol.constants import MessageType

        msg_type, json_data = self.auth_handler.__class__.create_message.__self__ if False else (None, {})
        
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
                except:
                    json_data = {}

        json_data = json_data or {}

        if msg_type == MessageType.FILE_UPLOAD_START:
            await self.handle_file_upload_start(device_id, json_data, websocket)
            return
        elif msg_type == MessageType.FILE_UPLOAD_DATA:
            await self.handle_file_upload_data(device_id, json_data, data, websocket)
            return
        elif msg_type == MessageType.FILE_UPLOAD_COMPLETE:
            await self.handle_file_upload_complete(device_id, json_data, websocket)
            return
        elif msg_type == MessageType.FILE_LIST_REQUEST:
            if device_id and self.conn_mgr.is_device_connected(device_id):
                await self.send_to_device(device_id, msg_type, json_data)
            return
        elif msg_type == MessageType.FILE_REQUEST:
            if device_id and self.conn_mgr.is_device_connected(device_id):
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
            else:
                if device_id and self.conn_mgr.is_device_connected(device_id):
                    await self.send_to_device(device_id, msg_type, json_data)
            return

        handlers = {
            MessageType.HEARTBEAT: self.handle_heartbeat,
            MessageType.SYSTEM_STATUS: self.handle_system_status,
            MessageType.LOG_UPLOAD: self.handle_log_upload,
            MessageType.SCRIPT_RESULT: self.handle_script_result,
            MessageType.AUTH_RESULT: self.handle_auth_result,
            MessageType.UPDATE_CHECK: self.handle_update_check,
            MessageType.UPDATE_DOWNLOAD: self.handle_update_download,
            MessageType.UPDATE_PROGRESS: self.handle_update_progress,
            MessageType.UPDATE_COMPLETE: self.handle_update_complete,
            MessageType.UPDATE_ERROR: self.handle_update_error,
            MessageType.UPDATE_ROLLBACK: self.handle_update_rollback,
        }

        if msg_type in handlers:
            await handlers[msg_type](device_id, json_data)
        elif msg_type == MessageType.FILE_DATA:
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
            device_list = self.conn_mgr.get_all_devices()
            response = self.create_message(
                MessageType.DEVICE_LIST,
                {"devices": device_list, "count": len(device_list)},
            )
            if hasattr(websocket, "send") and callable(
                getattr(websocket, "send", None)
            ):
                await websocket.send(response)
        else:
            logger.warning(f"未知消息类型: 0x{msg_type:02X}")

    async def _handle_download_package(self, device_id: str, json_data: dict) -> None:
        request_id = json_data.get("request_id", f"{device_id}-download")
        chunk_index = json_data.get("chunk_index", 0)
        total_chunks = json_data.get("total_chunks", 1)
        content = json_data.get("content", "")

        logger.info(
            f"收到打包分块 [{device_id}]: request_id={request_id}, chunk={chunk_index + 1}/{total_chunks}"
        )

        if request_id not in self.download_chunks:
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

    def __init__(self):
        self.file_transfer = FileTransferManager()
        self.conn_mgr = ConnectionManager(self.file_transfer)
        self.msg_handler = MessageHandler(self.conn_mgr)
        self.socket_handler = SocketHandler(self.conn_mgr, self.msg_handler)
        self.ws_handler = WebSocketHandler(self.conn_mgr, self.msg_handler)
        self.console = InteractiveConsole(self)
        self._last_device_count = 0
        self._device_list_broadcast_task = None

    async def run(self) -> None:
        host = settings.host
        ws_port = settings.ws_port
        socket_port = settings.socket_port

        logger.info(f"启动WebSocket服务器（前端）: ws://{host}:{ws_port}")
        logger.info(f"启动Socket服务器（Agent）: {host}:{socket_port}")
        logger.info(f"文件上传目录: {os.path.abspath(settings.upload_dir)}")

        ws_server = await websockets.serve(
            self.ws_handler.agent_handler, host, ws_port, ping_interval=settings.ping_interval, ping_timeout=settings.ping_timeout
        )

        socket_server = await asyncio.start_server(
            self.socket_handler.handle_connection, host, socket_port
        )

        self._start_device_list_monitor()

        asyncio.create_task(self.console.interactive_console())

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

    def _start_device_list_monitor(self) -> None:
        self._device_list_broadcast_task = asyncio.create_task(
            self._check_device_list_changes()
        )

    async def _check_device_list_changes(self) -> None:
        while True:
            await asyncio.sleep(15)
            current_count = len(self.conn_mgr.connected_devices)
            if current_count > self._last_device_count:
                await self.msg_handler.notify_device_list_update()
            self._last_device_count = current_count
