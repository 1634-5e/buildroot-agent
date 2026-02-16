import base64
import logging
import os
from websockets.server import WebSocketServerProtocol

from handlers.base import BaseHandler
from protocol.constants import MessageType
from config.settings import settings

logger = logging.getLogger(__name__)


class FileHandler(BaseHandler):
    async def handle_file_upload_start(
        self, device_id: str, data: dict, websocket: WebSocketServerProtocol
    ) -> None:
        filename = data.get("filename", "")
        file_size = data.get("file_size", 0)
        checksum = data.get("checksum", "")

        try:
            resume_id = data.get("resume_transfer_id", "")
            if resume_id:
                resume_info = await self.conn_mgr.file_transfer.get_resume_info(
                    resume_id
                )
                if resume_info:
                    logger.info(
                        f"[{device_id}] 恢复上传会话: {resume_id}, 进度: {resume_info['progress'] * 100:.1f}%"
                    )
                    response = self.create_message(
                        MessageType.FILE_UPLOAD_ACK,
                        {
                            "transfer_id": resume_id,
                            "chunk_size": resume_info["chunk_size"],
                            "received_chunks": resume_info["received_chunks"],
                            "missing_chunks": resume_info["missing_chunks"],
                            "resume": True,
                            "message": "继续上传",
                        },
                    )
                    await self._safe_send(websocket, response)
                    return

            session = await self.conn_mgr.file_transfer.create_upload_session(
                device_id, filename, file_size, checksum
            )

            response = self.create_message(
                MessageType.FILE_UPLOAD_ACK,
                {
                    "transfer_id": session.transfer_id,
                    "chunk_size": session.chunk_size,
                    "total_chunks": session.total_chunks,
                    "received_chunks": [],
                    "resume": False,
                    "message": "开始上传",
                },
            )
            await self._safe_send(websocket, response)

        except Exception as e:
            logger.error(f"[{device_id}] 创建上传会话失败: {e}")
            response = self.create_message(
                MessageType.FILE_UPLOAD_ACK, {"success": False, "error": str(e)}
            )
            await self._safe_send(websocket, response)

    async def handle_file_upload_data(
        self,
        device_id: str,
        data: dict,
        raw_data: bytes,
        websocket: WebSocketServerProtocol,
    ) -> None:
        transfer_id = data.get("transfer_id", "")
        chunk_index = data.get("chunk_index", -1)

        chunk_data = data.get("chunk_data", "")

        if chunk_data:
            try:
                chunk_bytes = base64.b64decode(chunk_data)
            except:
                chunk_bytes = b""
        else:
            chunk_bytes = b""

        success, message = await self.conn_mgr.file_transfer.process_upload_chunk(
            transfer_id, chunk_index, chunk_bytes
        )

        response = self.create_message(
            MessageType.FILE_UPLOAD_ACK,
            {
                "transfer_id": transfer_id,
                "chunk_index": chunk_index,
                "success": success,
                "message": message,
            },
        )
        await self._safe_send(websocket, response)

        session = self.conn_mgr.file_transfer.sessions.get(transfer_id)
        if session:
            await self.broadcast_to_web_consoles(
                MessageType.FILE_TRANSFER_STATUS,
                {
                    "device_id": device_id,
                    "transfer_id": transfer_id,
                    "filename": session.filename,
                    "progress": session.get_progress(),
                    "received_chunks": len(session.received_chunks),
                    "total_chunks": session.total_chunks,
                    "direction": "upload",
                },
            )

    async def handle_file_upload_complete(
        self, device_id: str, data: dict, websocket: WebSocketServerProtocol
    ) -> None:
        transfer_id = data.get("transfer_id", "")

        success, result = await self.conn_mgr.file_transfer.complete_upload(transfer_id)

        response = self.create_message(
            MessageType.FILE_UPLOAD_COMPLETE,
            {
                "transfer_id": transfer_id,
                "success": success,
                "filepath": result if success else "",
                "error": result if not success else "",
            },
        )
        await self._safe_send(websocket, response)

        if success:
            logger.info(f"[{device_id}] 文件上传完成: {result}")
        else:
            logger.error(f"[{device_id}] 文件上传失败: {result}")

    async def handle_file_download_request(self, device_id: str, data: dict) -> None:
        action = data.get("action")
        file_path = data.get("file_path")
        offset = data.get("offset", 0)
        chunk_size = data.get("chunk_size", 16384)
        request_id = data.get("request_id", "")

        if action == "download_update" and file_path:
            await self._handle_file_download(
                device_id, file_path, offset, chunk_size, request_id
            )
        else:
            logger.error(f"[{device_id}] 无效的下载请求: {data}")

    async def _handle_file_download(
        self,
        device_id: str,
        file_path: str,
        offset: int,
        chunk_size: int,
        request_id: str,
    ) -> None:
        try:
            full_path = os.path.join(settings.updates_dir, os.path.basename(file_path))

            if not os.path.exists(full_path):
                await self.send_to_device(
                    device_id,
                    MessageType.FILE_DOWNLOAD_DATA,
                    {
                        "action": "download_error",
                        "file_path": file_path,
                        "request_id": request_id,
                        "error": f"文件不存在: {full_path}",
                    },
                )
                return

            file_size = os.path.getsize(full_path)

            if offset >= file_size:
                complete_response = self.create_message(
                    MessageType.FILE_DOWNLOAD_DATA,
                    {
                        "action": "file_data",
                        "file_path": file_path,
                        "offset": offset,
                        "data": "",
                        "size": 0,
                        "is_final": True,
                        "total_size": file_size,
                        "request_id": request_id,
                    },
                )
                await self.send_to_device(
                    device_id,
                    MessageType.FILE_DOWNLOAD_DATA,
                    {
                        "action": "file_data",
                        "file_path": file_path,
                        "offset": offset,
                        "data": "",
                        "size": 0,
                        "is_final": True,
                        "total_size": file_size,
                        "request_id": request_id,
                    },
                )
                logger.info(f"[{device_id}] 文件下载完成: {file_path}")
                return

            with open(full_path, "rb") as f:
                f.seek(offset)
                data_chunk = f.read(chunk_size)

            data_b64 = base64.b64encode(data_chunk).decode("utf-8")

            is_final = (offset + len(data_chunk)) >= file_size

            response = self.create_message(
                MessageType.FILE_DOWNLOAD_DATA,
                {
                    "action": "file_data",
                    "file_path": file_path,
                    "offset": offset,
                    "data": data_b64,
                    "size": len(data_chunk),
                    "is_final": is_final,
                    "total_size": file_size,
                    "request_id": request_id,
                },
            )

            await self.send_to_device(device_id, MessageType.FILE_DOWNLOAD_DATA, response.model_dump())
            logger.debug(
                f"[{device_id}] 发送数据块: offset={offset}, size={len(data_chunk)}, final={is_final}"
            )

        except Exception as e:
            logger.error(f"[{device_id}] 文件下载处理失败: {e}")
            error_response = self.create_message(
                MessageType.FILE_DOWNLOAD_DATA,
                {
                    "action": "download_error",
                    "file_path": file_path,
                    "request_id": request_id,
                    "error": str(e),
                },
            )
            await self.send_to_device(device_id, MessageType.FILE_DOWNLOAD_DATA, error_response.model_dump())
