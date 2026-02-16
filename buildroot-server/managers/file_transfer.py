import asyncio
import hashlib
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

from models.file_transfer import FileTransferSession
from config.settings import settings

logger = logging.getLogger(__name__)


class FileTransferManager:
    """文件传输管理器 - 支持流式传输和断点续传"""

    def __init__(self):
        self.sessions: Dict[str, FileTransferSession] = {}
        self.device_chunk_sizes: Dict[str, int] = {}
        self.device_success_rates: Dict[str, List[bool]] = {}
        self.lock = asyncio.Lock()

        os.makedirs(settings.upload_dir, exist_ok=True)

        asyncio.create_task(self._cleanup_expired_sessions())

    def get_chunk_size(self, device_id: str) -> int:
        if device_id not in self.device_chunk_sizes:
            return settings.chunk_sizes["medium"]
        return self.device_chunk_sizes[device_id]

    def update_network_quality(self, device_id: str, success: bool) -> None:
        if device_id not in self.device_success_rates:
            self.device_success_rates[device_id] = []

        rates = self.device_success_rates[device_id]
        rates.append(success)
        if len(rates) > 20:
            rates.pop(0)

        if len(rates) >= 5:
            success_rate = sum(rates[-5:]) / 5
            current_size = self.device_chunk_sizes.get(
                device_id, settings.chunk_sizes["medium"]
            )

            if success_rate < 0.6:
                if current_size > settings.chunk_sizes["small"]:
                    new_size = max(current_size // 2, settings.chunk_sizes["small"])
                    self.device_chunk_sizes[device_id] = new_size
                    logger.info(
                        f"[{device_id}] 网络质量差，减小分片到 {new_size} bytes"
                    )
            elif success_rate > 0.95 and current_size < settings.chunk_sizes["xlarge"]:
                new_size = min(current_size * 2, settings.chunk_sizes["xlarge"])
                self.device_chunk_sizes[device_id] = new_size
                logger.info(f"[{device_id}] 网络质量良好，增大分片到 {new_size} bytes")

    async def create_upload_session(
        self, device_id: str, filename: str, file_size: int, checksum: str = ""
    ) -> FileTransferSession:
        transfer_id = hashlib.md5(
            f"{device_id}:{filename}:{time.time()}".encode()
        ).hexdigest()[:16]

        chunk_size = self.get_chunk_size(device_id)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        safe_filename = os.path.basename(filename)
        if not safe_filename or safe_filename.startswith(".") or ".." in safe_filename:
            raise ValueError(f"非法文件名: {filename}")

        filepath = os.path.join(settings.upload_dir, f"{transfer_id}_{safe_filename}")

        session = FileTransferSession(
            transfer_id=transfer_id,
            device_id=device_id,
            filename=safe_filename,
            filepath=filepath,
            file_size=file_size,
            direction="upload",
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            checksum=checksum,
        )

        async with self.lock:
            self.sessions[transfer_id] = session

        logger.info(
            f"[{device_id}] 创建上传会话: {transfer_id}, 文件: {safe_filename}, "
            f"大小: {file_size} bytes, 分片: {total_chunks}, 分片大小: {chunk_size}"
        )

        return session

    async def process_upload_chunk(
        self, transfer_id: str, chunk_index: int, chunk_data: bytes
    ) -> Tuple[bool, str]:
        async with self.lock:
            if transfer_id not in self.sessions:
                return False, "会话不存在或已过期"

            session = self.sessions[transfer_id]

        session.last_activity = time.time()

        if chunk_index < 0 or chunk_index >= session.total_chunks:
            return False, f"分片索引越界: {chunk_index}/{session.total_chunks}"

        if chunk_index in session.received_chunks:
            return True, "分片已存在"

        try:
            temp_path = session.filepath + ".tmp"

            with open(temp_path, "r+b" if os.path.exists(temp_path) else "wb") as f:
                offset = chunk_index * session.chunk_size
                f.seek(offset)
                f.write(chunk_data)

            session.received_chunks.add(chunk_index)

            self.update_network_quality(session.device_id, True)

            progress = session.get_progress() * 100
            logger.debug(
                f"[{session.device_id}] 接收分片 {chunk_index + 1}/{session.total_chunks} "
                f"({progress:.1f}%) - {transfer_id}"
            )

            return True, "OK"

        except Exception as e:
            logger.error(f"[{session.device_id}] 写入分片失败: {e}")
            return False, str(e)

    async def complete_upload(self, transfer_id: str) -> Tuple[bool, str]:
        async with self.lock:
            if transfer_id not in self.sessions:
                return False, "会话不存在"

            session = self.sessions[transfer_id]

        missing = session.get_missing_chunks()
        if missing:
            return False, f"缺少分片: {len(missing)} 个"

        try:
            temp_path = session.filepath + ".tmp"
            final_path = session.filepath

            if os.path.exists(temp_path):
                os.rename(temp_path, final_path)

            actual_size = os.path.getsize(final_path)
            if actual_size != session.file_size:
                os.remove(final_path)
                return False, f"文件大小不匹配: {actual_size} != {session.file_size}"

            if session.checksum:
                md5_hash = hashlib.md5()
                with open(final_path, "rb") as f:
                    while chunk := f.read(8192):
                        md5_hash.update(chunk)

                if md5_hash.hexdigest() != session.checksum:
                    os.remove(final_path)
                    return False, "文件MD5校验失败"

            logger.info(
                f"[{session.device_id}] 上传完成: {session.filename} "
                f"({session.file_size} bytes) -> {final_path}"
            )

            async with self.lock:
                del self.sessions[transfer_id]

            return True, final_path

        except Exception as e:
            logger.error(f"[{session.device_id}] 完成上传失败: {e}")
            return False, str(e)

    async def get_resume_info(self, transfer_id: str) -> Optional[dict]:
        async with self.lock:
            if transfer_id not in self.sessions:
                return None

            session = self.sessions[transfer_id]

        return {
            "transfer_id": transfer_id,
            "received_chunks": list(session.received_chunks),
            "missing_chunks": session.get_missing_chunks(),
            "progress": session.get_progress(),
            "chunk_size": session.chunk_size,
        }

    async def _cleanup_expired_sessions(self):
        while True:
            await asyncio.sleep(60)

            current_time = time.time()
            expired = []

            async with self.lock:
                for transfer_id, session in self.sessions.items():
                    if current_time - session.last_activity > settings.session_timeout:
                        expired.append(transfer_id)

                for transfer_id in expired:
                    session = self.sessions.pop(transfer_id)
                    temp_path = session.filepath + ".tmp"
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                            logger.info(f"清理过期会话临时文件: {temp_path}")
                        except:
                            pass
                    logger.info(f"清理过期传输会话: {transfer_id}")
