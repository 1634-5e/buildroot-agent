#!/usr/bin/env python3
"""
Buildroot Agent 云端服务器示例 - 增强版
支持文件上传、流式传输、断点续传，优化弱网环境

安装依赖: pip install websockets

运行: python3 server_example.py
"""

import asyncio
import json
import struct
import logging
import os
import hashlib
import time
from datetime import datetime
from typing import Dict, Set, Any, Optional, Tuple, List
from pathlib import Path
from dataclasses import dataclass, field

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# 尝试导入WebSocketServerProtocol
try:
    from websockets.server import WebSocketServerProtocol
    import websockets
except ImportError:
    print("请先安装 websockets: pip install websockets")
    exit(1)


# 消息类型定义 (与Agent保持一致)
class MessageType:
    """消息类型常量定义"""

    HEARTBEAT = 0x01
    SYSTEM_STATUS = 0x02
    LOG_UPLOAD = 0x03
    SCRIPT_RECV = 0x04
    SCRIPT_RESULT = 0x05
    PTY_CREATE = 0x10
    PTY_DATA = 0x11
    PTY_RESIZE = 0x12
    PTY_CLOSE = 0x13
    FILE_REQUEST = 0x20
    FILE_DATA = 0x21
    FILE_LIST_REQUEST = 0x22
    FILE_LIST_RESPONSE = 0x23
    DOWNLOAD_PACKAGE = 0x24
    CMD_REQUEST = 0x30
    CMD_RESPONSE = 0x31
    DEVICE_LIST = 0x50
    AUTH = 0xF0
    AUTH_RESULT = 0xF1
    # 新增文件传输消息类型
    FILE_UPLOAD_START = 0x40  # 开始上传请求
    FILE_UPLOAD_DATA = 0x41  # 上传数据分片
    FILE_UPLOAD_ACK = 0x42  # 分片确认
    FILE_UPLOAD_COMPLETE = 0x43  # 上传完成
    FILE_DOWNLOAD_START = 0x44  # 开始下载请求
    FILE_DOWNLOAD_DATA = 0x45  # 下载数据分片
    FILE_DOWNLOAD_ACK = 0x46  # 下载确认
    FILE_TRANSFER_STATUS = 0x47  # 传输状态/进度


# 有效的认证Token
VALID_TOKENS = {
    "test-token-123": "测试设备1",
    "your-auth-token": "默认设备",
}


@dataclass
class FileTransferSession:
    """文件传输会话"""

    transfer_id: str
    device_id: str
    filename: str
    filepath: str
    file_size: int
    direction: str  # 'upload' 或 'download'
    chunk_size: int
    total_chunks: int
    received_chunks: Set[int] = field(default_factory=set)
    retry_count: Dict[int, int] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    checksum: str = ""

    def get_progress(self) -> float:
        """获取传输进度"""
        if self.total_chunks == 0:
            return 0.0
        return len(self.received_chunks) / self.total_chunks

    def get_missing_chunks(self) -> List[int]:
        """获取未接收的分片列表"""
        return [i for i in range(self.total_chunks) if i not in self.received_chunks]


class FileTransferManager:
    """文件传输管理器 - 支持流式传输和断点续传"""

    # 分片大小配置 (根据网络状况自适应)
    CHUNK_SIZES = {
        "small": 8 * 1024,  # 8KB - 极弱网环境
        "medium": 32 * 1024,  # 32KB - 一般弱网
        "large": 64 * 1024,  # 64KB - 正常网络
        "xlarge": 128 * 1024,  # 128KB - 良好网络
    }

    MAX_RETRIES = 5  # 最大重试次数
    RETRY_DELAY_BASE = 1.0  # 基础重试延迟(秒)
    SESSION_TIMEOUT = 300  # 会话超时时间(秒)
    UPLOAD_DIR = "./uploads"  # 上传文件存储目录

    def __init__(self):
        self.sessions: Dict[str, FileTransferSession] = {}
        self.device_chunk_sizes: Dict[str, int] = {}  # 设备自适应分片大小
        self.device_success_rates: Dict[str, List[bool]] = {}  # 成功率统计
        self.lock = asyncio.Lock()

        # 确保上传目录存在
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

        # 启动清理任务
        asyncio.create_task(self._cleanup_expired_sessions())

    def get_chunk_size(self, device_id: str) -> int:
        """根据设备网络状况获取合适的分片大小"""
        if device_id not in self.device_chunk_sizes:
            # 初始使用中等分片
            return self.CHUNK_SIZES["medium"]
        return self.device_chunk_sizes[device_id]

    def update_network_quality(self, device_id: str, success: bool) -> None:
        """更新网络质量评估"""
        if device_id not in self.device_success_rates:
            self.device_success_rates[device_id] = []

        # 保留最近20次的传输记录
        rates = self.device_success_rates[device_id]
        rates.append(success)
        if len(rates) > 20:
            rates.pop(0)

        # 根据成功率调整分片大小
        if len(rates) >= 5:
            success_rate = sum(rates[-5:]) / 5
            current_size = self.device_chunk_sizes.get(
                device_id, self.CHUNK_SIZES["medium"]
            )

            if success_rate < 0.6:
                # 成功率低，减小分片
                if current_size > self.CHUNK_SIZES["small"]:
                    new_size = max(current_size // 2, self.CHUNK_SIZES["small"])
                    self.device_chunk_sizes[device_id] = new_size
                    logger.info(
                        f"[{device_id}] 网络质量差，减小分片到 {new_size} bytes"
                    )
            elif success_rate > 0.95 and current_size < self.CHUNK_SIZES["xlarge"]:
                # 成功率高，增大分片
                new_size = min(current_size * 2, self.CHUNK_SIZES["xlarge"])
                self.device_chunk_sizes[device_id] = new_size
                logger.info(f"[{device_id}] 网络质量良好，增大分片到 {new_size} bytes")

    async def create_upload_session(
        self, device_id: str, filename: str, file_size: int, checksum: str = ""
    ) -> FileTransferSession:
        """创建上传会话"""
        transfer_id = hashlib.md5(
            f"{device_id}:{filename}:{time.time()}".encode()
        ).hexdigest()[:16]

        # 根据设备网络状况选择分片大小
        chunk_size = self.get_chunk_size(device_id)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        # 安全性检查：限制文件名
        safe_filename = os.path.basename(filename)
        if not safe_filename or safe_filename.startswith(".") or ".." in safe_filename:
            raise ValueError(f"非法文件名: {filename}")

        filepath = os.path.join(self.UPLOAD_DIR, f"{transfer_id}_{safe_filename}")

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
        """处理上传分片"""
        async with self.lock:
            if transfer_id not in self.sessions:
                return False, "会话不存在或已过期"

            session = self.sessions[transfer_id]

        # 更新活动时间
        session.last_activity = time.time()

        # 检查分片索引
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            return False, f"分片索引越界: {chunk_index}/{session.total_chunks}"

        # 检查是否已接收
        if chunk_index in session.received_chunks:
            return True, "分片已存在"

        try:
            # 写入文件 (使用临时文件模式支持断点续传)
            temp_path = session.filepath + ".tmp"

            # 以读写模式打开，如果不存在则创建
            with open(temp_path, "r+b" if os.path.exists(temp_path) else "wb") as f:
                # 定位到分片位置
                offset = chunk_index * session.chunk_size
                f.seek(offset)
                f.write(chunk_data)

            # 标记为已接收
            session.received_chunks.add(chunk_index)

            # 更新成功率统计
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
        """完成上传，验证文件完整性"""
        async with self.lock:
            if transfer_id not in self.sessions:
                return False, "会话不存在"

            session = self.sessions[transfer_id]

        # 检查是否所有分片都已接收
        missing = session.get_missing_chunks()
        if missing:
            return False, f"缺少分片: {len(missing)} 个"

        try:
            # 重命名临时文件
            temp_path = session.filepath + ".tmp"
            final_path = session.filepath

            if os.path.exists(temp_path):
                os.rename(temp_path, final_path)

            # 验证文件大小
            actual_size = os.path.getsize(final_path)
            if actual_size != session.file_size:
                os.remove(final_path)
                return False, f"文件大小不匹配: {actual_size} != {session.file_size}"

            # 如果提供了校验和，验证MD5
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

            # 清理会话
            async with self.lock:
                del self.sessions[transfer_id]

            return True, final_path

        except Exception as e:
            logger.error(f"[{session.device_id}] 完成上传失败: {e}")
            return False, str(e)

    async def get_resume_info(self, transfer_id: str) -> Optional[Dict]:
        """获取断点续传信息"""
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
        """定期清理过期的传输会话"""
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次

            current_time = time.time()
            expired = []

            async with self.lock:
                for transfer_id, session in self.sessions.items():
                    if current_time - session.last_activity > self.SESSION_TIMEOUT:
                        expired.append(transfer_id)

                for transfer_id in expired:
                    session = self.sessions.pop(transfer_id)
                    # 清理临时文件
                    temp_path = session.filepath + ".tmp"
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                            logger.info(f"清理过期会话临时文件: {temp_path}")
                        except:
                            pass
                    logger.info(f"清理过期传输会话: {transfer_id}")


class ConnectionManager:
    """连接管理器 - 管理设备连接和Web控制台"""

    def __init__(self, file_transfer_manager: FileTransferManager):
        self.connected_devices: Dict[str, WebSocketServerProtocol] = {}
        self.web_consoles: Set[WebSocketServerProtocol] = set()
        self.pty_sessions: Dict[str, Dict[int, asyncio.Queue]] = {}
        self.file_transfer = file_transfer_manager

    def add_device(self, device_id: str, websocket: WebSocketServerProtocol) -> None:
        """添加设备连接"""
        self.connected_devices[device_id] = websocket
        self.pty_sessions[device_id] = {}

    def remove_device(self, device_id: str) -> None:
        """移除设备连接"""
        self.connected_devices.pop(device_id, None)
        self.pty_sessions.pop(device_id, None)

    def add_console(self, websocket: WebSocketServerProtocol) -> None:
        """添加Web控制台"""
        self.web_consoles.add(websocket)

    def remove_console(self, websocket: WebSocketServerProtocol) -> None:
        """移除Web控制台"""
        self.web_consoles.discard(websocket)

    def get_device(self, device_id: str) -> Optional[WebSocketServerProtocol]:
        """获取设备WebSocket连接"""
        return self.connected_devices.get(device_id)

    def is_device_connected(self, device_id: str) -> bool:
        """检查设备是否已连接"""
        return device_id in self.connected_devices

    def get_all_devices(self) -> Dict[str, Any]:
        """获取所有连接的设备信息"""
        devices = []
        for device_id, ws in self.connected_devices.items():
            remote_addr = self._get_remote_address(ws)
            devices.append(
                {
                    "device_id": device_id,
                    "connected_time": datetime.now().isoformat(),
                    "status": "online",
                    "remote_addr": remote_addr,
                }
            )
        return devices

    def _get_remote_address(self, websocket: WebSocketServerProtocol) -> str:
        """获取远程地址信息"""
        try:
            remote = getattr(websocket, "remote_address", "unknown")
            return remote[0] if isinstance(remote, tuple) else str(remote)
        except:
            return "unknown"


class MessageHandler:
    """消息处理器"""

    def __init__(self, connection_manager: ConnectionManager):
        self.conn_mgr = connection_manager

    @staticmethod
    def create_message(msg_type: int, data: dict) -> bytes:
        """创建消息"""
        json_data = json.dumps(data).encode("utf-8")
        return bytes([msg_type]) + json_data

    @staticmethod
    def parse_message(data: bytes) -> Tuple[Optional[int], Optional[dict]]:
        """解析消息"""
        if len(data) < 1:
            return None, None
        msg_type = data[0]
        try:
            json_data = json.loads(data[1:].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            json_data = {}
        return msg_type, json_data

    async def handle_auth(self, websocket: WebSocketServerProtocol, data: dict) -> bool:
        """处理认证"""
        device_id = data.get("device_id", "unknown")
        token = data.get("token", "")
        version = data.get("version", "unknown")

        if token in VALID_TOKENS:
            logger.info(f"设备认证成功: {device_id} (版本: {version})")
            self.conn_mgr.add_device(device_id, websocket)

            response = self.create_message(
                MessageType.AUTH_RESULT,
                {"success": True, "message": f"欢迎, {VALID_TOKENS[token]}"},
            )
            await self._safe_send(websocket, response)
            return True
        else:
            logger.warning(f"设备认证失败: {device_id}:{token}, 无效Token")
            response = self.create_message(
                MessageType.AUTH_RESULT,
                {"success": False, "message": "认证失败: Token无效"},
            )
            await self._safe_send(websocket, response)
            return False

    async def _safe_send(
        self, websocket: WebSocketServerProtocol, message: bytes
    ) -> bool:
        """安全发送消息"""
        try:
            # 检查连接状态
            if not hasattr(websocket, "state") or websocket.state.name != "OPEN":
                logger.debug("WebSocket连接未开启，跳过发送")
                return False

            if hasattr(websocket, "send") and callable(
                getattr(websocket, "send", None)
            ):
                await websocket.send(message)
                return True
            else:
                logger.warning("WebSocket对象没有send方法")
                return False
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket连接已关闭: code={e.code}, reason={e.reason}")
            return False
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"WebSocket连接错误关闭: code={e.code}, reason={e.reason}")
            return False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def handle_heartbeat(self, device_id: str, data: dict) -> None:
        """处理心跳"""
        logger.debug(f"收到心跳: {device_id}")

    async def handle_system_status(self, device_id: str, data: dict) -> None:
        """处理系统状态"""
        logger.info(
            f"设备状态 [{device_id}]: "
            f"CPU={data.get('cpu_usage', 0):.1f}%, "
            f"MEM={data.get('mem_used', 0):.0f}/{data.get('mem_total', 0):.0f}MB, "
            f"Load={data.get('load_1min', 0):.2f}"
        )

        status_data = {"device_id": device_id, **data}
        await self.broadcast_to_web_consoles(MessageType.SYSTEM_STATUS, status_data)

    async def handle_log_upload(self, device_id: str, data: dict) -> None:
        """处理日志上传"""
        filepath = data.get("filepath", "unknown")
        if "chunk" in data:
            chunk = data.get("chunk", 0)
            total = data.get("total_chunks", 1)
            logger.info(f"收到日志分片 [{device_id}]: {filepath} ({chunk + 1}/{total})")
        elif "line" in data:
            line = data.get("line", "")
            logger.info(f"实时日志 [{device_id}] {filepath}: {line}")
        elif "lines" in data:
            lines = data.get("lines", 0)
            logger.info(f"收到日志 [{device_id}]: {filepath} ({lines} 行)")

    async def handle_script_result(self, device_id: str, data: dict) -> None:
        """处理脚本执行结果"""
        script_id = data.get("script_id", "unknown")
        exit_code = data.get("exit_code", -1)
        success = data.get("success", False)
        output = data.get("output", "")

        status = "成功" if success else "失败"
        logger.info(f"脚本执行{status} [{device_id}]: {script_id}, 退出码={exit_code}")
        if output:
            logger.info(f"输出:\n{output[:500]}")

    async def handle_pty_data(self, device_id: str, data: dict) -> None:
        """处理PTY数据 (从设备到服务器)"""
        session_id = data.get("session_id", -1)
        pty_data = data.get("data", "")

        if (
            device_id in self.conn_mgr.pty_sessions
            and session_id in self.conn_mgr.pty_sessions[device_id]
        ):
            try:
                await self.broadcast_to_web_consoles(
                    MessageType.PTY_DATA,
                    {
                        "device_id": device_id,
                        "session_id": session_id,
                        "data": pty_data,
                    },
                )
            except Exception:
                pass

    async def handle_pty_close(self, device_id: str, data: dict) -> None:
        """处理PTY关闭"""
        session_id = data.get("session_id", -1)
        reason = data.get("reason", "unknown")
        logger.info(f"PTY会话关闭 [{device_id}]: session={session_id}, reason={reason}")

        if (
            device_id in self.conn_mgr.pty_sessions
            and session_id in self.conn_mgr.pty_sessions[device_id]
        ):
            del self.conn_mgr.pty_sessions[device_id][session_id]

    async def handle_pty_create(self, device_id: str, data: dict) -> None:
        """处理PTY创建"""
        session_id = data.get("session_id", -1)
        status = data.get("status", "unknown")
        rows = data.get("rows", 24)
        cols = data.get("cols", 80)

        logger.info(
            f"PTY会话创建 [{device_id}]: session={session_id}, status={status}, size={cols}x{rows}"
        )

        if device_id not in self.conn_mgr.pty_sessions:
            self.conn_mgr.pty_sessions[device_id] = {}

        if session_id not in self.conn_mgr.pty_sessions[device_id]:
            self.conn_mgr.pty_sessions[device_id][session_id] = asyncio.Queue()

        await self.broadcast_to_web_consoles(
            MessageType.PTY_CREATE, {"device_id": device_id, **data}
        )

    async def handle_auth_result(self, device_id: str, data: dict) -> None:
        """处理认证结果（从设备到服务器）"""
        success = data.get("success", False)
        message = data.get("message", "")

        logger.info(
            f"设备认证结果 [{device_id}]: {'成功' if success else '失败'}, {message}"
        )

        await self.broadcast_to_web_consoles(
            MessageType.AUTH_RESULT, {"device_id": device_id, **data}
        )

    async def handle_file_upload_start(
        self, device_id: str, data: dict, websocket: WebSocketServerProtocol
    ) -> None:
        """处理文件上传开始请求"""
        filename = data.get("filename", "")
        file_size = data.get("file_size", 0)
        checksum = data.get("checksum", "")

        try:
            # 检查是否支持断点续传
            resume_id = data.get("resume_transfer_id", "")
            if resume_id:
                # 尝试恢复之前的会话
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

            # 创建新会话
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
        """处理文件上传数据分片"""
        transfer_id = data.get("transfer_id", "")
        chunk_index = data.get("chunk_index", -1)

        # 分片数据在 raw_data 中（避免base64编码开销）
        # 格式: [1字节消息类型][JSON头部][二进制数据]
        # 这里我们假设 chunk_data 已经在 data 中作为 base64 或者直接在 raw_data 中
        chunk_data = data.get("chunk_data", "")

        if chunk_data:
            import base64

            try:
                chunk_bytes = base64.b64decode(chunk_data)
            except:
                chunk_bytes = b""
        else:
            # 如果没有在JSON中，可能需要在 raw_data 中解析
            chunk_bytes = b""

        success, message = await self.conn_mgr.file_transfer.process_upload_chunk(
            transfer_id, chunk_index, chunk_bytes
        )

        # 发送确认
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

        # 广播进度到Web控制台
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
        """处理文件上传完成"""
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

    async def handle_message(
        self, websocket: WebSocketServerProtocol, device_id: str, data: bytes
    ) -> None:
        """处理消息"""
        msg_type, json_data = self.parse_message(data)

        # 文件传输相关消息
        if msg_type == MessageType.FILE_UPLOAD_START:
            await self.handle_file_upload_start(device_id, json_data, websocket)
            return
        elif msg_type == MessageType.FILE_UPLOAD_DATA:
            await self.handle_file_upload_data(device_id, json_data, data, websocket)
            return
        elif msg_type == MessageType.FILE_UPLOAD_COMPLETE:
            await self.handle_file_upload_complete(device_id, json_data, websocket)
            return

        # 其他消息处理
        handlers = {
            MessageType.HEARTBEAT: self.handle_heartbeat,
            MessageType.SYSTEM_STATUS: self.handle_system_status,
            MessageType.LOG_UPLOAD: self.handle_log_upload,
            MessageType.SCRIPT_RESULT: self.handle_script_result,
            MessageType.PTY_CREATE: self.handle_pty_create,
            MessageType.PTY_DATA: self.handle_pty_data,
            MessageType.PTY_CLOSE: self.handle_pty_close,
            MessageType.AUTH_RESULT: self.handle_auth_result,
        }

        if msg_type in handlers:
            await handlers[msg_type](device_id, json_data)
        elif msg_type == MessageType.FILE_DATA:
            logger.info(f"收到文件数据 [{device_id}]: {json_data}")
        elif msg_type == MessageType.FILE_LIST_RESPONSE:
            await self.broadcast_to_web_consoles(
                MessageType.FILE_LIST_RESPONSE, {"device_id": device_id, **json_data}
            )
        elif msg_type == MessageType.DOWNLOAD_PACKAGE:
            logger.info(
                f"收到打包响应 [{device_id}]: filename={json_data.get('filename', 'unknown')}, size={json_data.get('size', '0')}"
            )
            await self.broadcast_to_web_consoles(
                MessageType.DOWNLOAD_PACKAGE, {"device_id": device_id, **json_data}
            )
        elif msg_type == MessageType.CMD_RESPONSE:
            logger.info(f"收到命令响应 [{device_id}]: {json_data}")
            await self.broadcast_to_web_consoles(
                MessageType.CMD_RESPONSE, {"device_id": device_id, **json_data}
            )
        elif msg_type == MessageType.AUTH:
            logger.debug(f"收到认证消息 [{device_id}]（已认证）")
        elif msg_type == MessageType.DEVICE_LIST:
            logger.info(f"设备列表查询 [{device_id}]: {json_data}")
            # Send current device list to the requesting client
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

    async def broadcast_to_web_consoles(self, msg_type: int, data: dict) -> None:
        """向所有web控制台广播消息"""
        if not self.conn_mgr.web_consoles:
            return

        try:
            message = self.create_message(msg_type, data)
            to_remove = []

            for console in list(self.conn_mgr.web_consoles):
                try:
                    # 检查WebSocket连接状态
                    if hasattr(console, "state") and console.state.name != "OPEN":
                        logger.debug("Web控制台连接未开启，移除连接")
                        to_remove.append(console)
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
                except websockets.exceptions.ConnectionClosedError as e:
                    logger.warning(
                        f"Web控制台连接错误: code={e.code}, reason={e.reason}"
                    )
                    to_remove.append(console)
                except Exception as e:
                    logger.warning(f"向web控制台发送失败: {e}")
                    to_remove.append(console)

            for console in to_remove:
                self.conn_mgr.remove_console(console)
        except Exception as e:
            logger.error(f"广播消息失败: {e}")

    async def send_to_device(self, device_id: str, msg_type: int, data: dict) -> bool:
        """发送消息到设备"""
        if not self.conn_mgr.is_device_connected(device_id):
            logger.warning(f"设备未连接: {device_id}")
            return False

        try:
            websocket = self.conn_mgr.get_device(device_id)
            if not websocket:
                logger.error(f"设备WebSocket为空: {device_id}")
                return False

            # 检查连接状态
            if hasattr(websocket, "state") and websocket.state.name != "OPEN":
                logger.warning(f"设备WebSocket连接未开启: {device_id}")
                self.conn_mgr.remove_device(device_id)
                return False

            if not hasattr(websocket, "send") or not callable(
                getattr(websocket, "send", None)
            ):
                logger.error(f"设备WebSocket无效: {device_id}")
                return False

            message = self.create_message(msg_type, data)
            await websocket.send(message)
            return True
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(
                f"设备WebSocket连接已关闭: {device_id}, code={e.code}, reason={e.reason}"
            )
            self.conn_mgr.remove_device(device_id)
            return False
        except Exception as e:
            logger.error(f"发送失败: {e}")
            return False


class CloudServer:
    """云端服务器主类"""

    def __init__(self):
        self.file_transfer = FileTransferManager()
        self.conn_mgr = ConnectionManager(self.file_transfer)
        self.msg_handler = MessageHandler(self.conn_mgr)

    async def agent_handler(self, websocket: WebSocketServerProtocol) -> None:
        """WebSocket连接处理"""
        try:
            remote = getattr(websocket, "remote_address", "unknown")
        except:
            remote = "unknown"
        logger.info(f"新连接: {remote}")

        # 先尝试作为web控制台处理
        self.conn_mgr.add_console(websocket)
        await self.notify_device_list_update()

        device_id: Optional[str] = None
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

                # 如果收到认证消息，说明是设备连接
                if msg_type == MessageType.AUTH and not is_device:
                    is_device = True
                    self.conn_mgr.remove_console(websocket)

                    try:
                        json_data = json.loads(message[1:].decode("utf-8"))
                        device_id = json_data.get("device_id", "unknown")
                        authenticated = await self.msg_handler.handle_auth(
                            websocket, json_data
                        )
                        if authenticated:
                            await self.notify_device_list_update()
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

                # 设备连接后的消息处理
                if is_device and authenticated and device_id:
                    await self.msg_handler.handle_message(websocket, device_id, message)

                # Web控制台的消息处理
                elif not is_device:
                    try:
                        json_data = json.loads(message[1:].decode("utf-8"))
                        if "device_id" in json_data:
                            device_id = json_data["device_id"]
                            logger.info(
                                f"Web控制台消息 [0x{msg_type:02X}] 转发到设备: {device_id}"
                            )

                            if self.conn_mgr.is_device_connected(device_id):
                                target_ws = self.conn_mgr.get_device(device_id)
                                if hasattr(target_ws, "send") and callable(
                                    getattr(target_ws, "send", None)
                                ):
                                    new_message = bytes([msg_type]) + json.dumps(
                                        json_data
                                    ).encode("utf-8")
                                    await target_ws.send(new_message)
                                    logger.debug("消息已发送到设备")
                            else:
                                logger.warning(f"设备不在线: {device_id}")
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
                    await self.notify_device_list_update()
            else:
                logger.info(
                    f"Web控制台断开: {remote}, code: {e.code}, reason: {e.reason}"
                )
                self.conn_mgr.remove_console(websocket)
        except Exception as e:
            logger.error(f"连接处理错误: {e}")
        finally:
            if not is_device:
                self.conn_mgr.remove_console(websocket)

    async def notify_device_list_update(self) -> None:
        """通知web控制台设备列表更新"""
        device_list = self.conn_mgr.get_all_devices()
        await self.msg_handler.broadcast_to_web_consoles(
            MessageType.DEVICE_LIST, {"devices": device_list, "count": len(device_list)}
        )

    async def interactive_console(self) -> None:
        """交互式控制台"""
        await asyncio.sleep(2)  # 等待服务器启动

        print("\n" + "=" * 60)
        print("Buildroot Agent 云端控制台")
        print("=" * 60)
        print("命令:")
        print("  list              - 列出已连接设备")
        print("  status <device>   - 获取设备状态")
        print("  exec <device> <cmd> - 执行命令")
        print("  script <device>   - 发送测试脚本")
        print("  pty <device>      - 创建PTY会话")
        print("  tail <device> <file> - 查看日志")
        print("  uploads           - 查看已上传文件")
        print("  quit              - 退出")
        print("=" * 60 + "\n")

        loop = asyncio.get_event_loop()

        while True:
            try:
                line = await loop.run_in_executor(None, input, "> ")
                line = line.strip()

                if not line:
                    continue

                parts = line.split(maxsplit=2)
                cmd = parts[0].lower()

                if cmd in ("quit", "exit"):
                    print("退出...")
                    break
                elif cmd == "list":
                    await self._cmd_list()
                elif cmd == "status" and len(parts) >= 2:
                    await self._cmd_status(parts[1])
                elif cmd == "exec" and len(parts) >= 3:
                    await self._cmd_exec(parts[1], parts[2])
                elif cmd == "script" and len(parts) >= 2:
                    await self._cmd_script(parts[1])
                elif cmd == "pty" and len(parts) >= 2:
                    await self._cmd_pty(parts[1])
                elif cmd == "tail" and len(parts) >= 3:
                    await self._cmd_tail(parts[1], parts[2])
                elif cmd == "uploads":
                    await self._cmd_uploads()
                else:
                    print("未知命令，输入 'list' 查看已连接设备")

            except EOFError:
                break
            except Exception as e:
                print(f"错误: {e}")

    async def _cmd_list(self) -> None:
        """列出已连接设备"""
        devices = self.conn_mgr.connected_devices
        if devices:
            print("已连接设备:")
            for dev_id in devices:
                print(f"  - {dev_id}")
        else:
            print("没有已连接的设备")

    async def _cmd_status(self, device_id: str) -> None:
        """获取设备状态"""
        await self.msg_handler.send_to_device(
            device_id,
            MessageType.CMD_REQUEST,
            {"cmd": "status", "request_id": "status-1"},
        )
        print(f"已请求设备状态: {device_id}")

    async def _cmd_exec(self, device_id: str, command: str) -> None:
        """执行命令"""
        await self.msg_handler.send_to_device(
            device_id,
            MessageType.CMD_REQUEST,
            {
                "cmd": command,
                "request_id": f"exec-{datetime.now().timestamp()}",
            },
        )
        print(f"已发送命令: {command}")

    async def _cmd_script(self, device_id: str) -> None:
        """发送测试脚本"""
        await self.msg_handler.send_to_device(
            device_id,
            MessageType.SCRIPT_RECV,
            {
                "script_id": "test-script",
                "content": '#!/bin/bash\necho "Hello from cloud!"\ndate\nuname -a\nfree -m\n',
                "execute": True,
            },
        )
        print(f"已发送测试脚本到: {device_id}")

    async def _cmd_pty(self, device_id: str) -> None:
        """创建PTY会话"""
        session_id = 1
        await self.msg_handler.send_to_device(
            device_id,
            MessageType.PTY_CREATE,
            {"session_id": session_id, "rows": 24, "cols": 80},
        )
        print(f"已请求创建PTY会话: {device_id}")
        print("(PTY交互功能需要在Web界面或专用客户端中使用)")

    async def _cmd_tail(self, device_id: str, filepath: str) -> None:
        """查看日志"""
        await self.msg_handler.send_to_device(
            device_id,
            MessageType.FILE_REQUEST,
            {"action": "tail", "filepath": filepath, "lines": 50},
        )
        print(f"已请求日志: {filepath}")

    async def _cmd_uploads(self) -> None:
        """查看已上传文件"""
        upload_dir = self.file_transfer.UPLOAD_DIR
        if not os.path.exists(upload_dir):
            print("上传目录为空")
            return

        files = os.listdir(upload_dir)
        if not files:
            print("暂无上传文件")
            return

        print(f"\n已上传文件 (目录: {upload_dir}):")
        print("-" * 80)
        print(f"{'文件名':<50} {'大小':<15} {'修改时间'}")
        print("-" * 80)

        for filename in sorted(files):
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                # 去掉transfer_id前缀
                display_name = (
                    "_".join(filename.split("_")[1:]) if "_" in filename else filename
                )
                size_str = (
                    f"{size:,} bytes"
                    if size < 1024 * 1024
                    else f"{size / 1024 / 1024:.2f} MB"
                )
                print(f"{display_name:<50} {size_str:<15} {mtime}")
        print()

    async def run(self) -> None:
        """运行服务器"""
        host = "0.0.0.0"
        port = 8765

        logger.info(f"启动WebSocket服务器: ws://{host}:{port}")
        logger.info(f"文件上传目录: {os.path.abspath(self.file_transfer.UPLOAD_DIR)}")

        server = await websockets.serve(
            self.agent_handler, host, port, ping_interval=30, ping_timeout=10
        )

        logger.info("服务器运行中，按 Ctrl+C 停止")

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            server.close()
            await server.wait_closed()


async def main() -> None:
    """主函数"""
    server = CloudServer()
    try:
        await server.run()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    asyncio.run(main())
