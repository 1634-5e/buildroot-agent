import base64
import logging
import os

from handlers.base import BaseHandler
from protocol.constants import MessageType
from config.settings import settings

logger = logging.getLogger(__name__)


class FileHandler(BaseHandler):
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

            await self.send_to_device(
                device_id,
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
            logger.debug(
                f"[{device_id}] 发送数据块: offset={offset}, size={len(data_chunk)}, final={is_final}"
            )

        except Exception as e:
            logger.error(f"[{device_id}] 文件下载处理失败: {e}")
            await self.send_to_device(
                device_id,
                MessageType.FILE_DOWNLOAD_DATA,
                {
                    "action": "download_error",
                    "file_path": file_path,
                    "request_id": request_id,
                    "error": str(e),
                },
            )
