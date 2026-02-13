#!/usr/bin/env python3
"""
Buildroot Agent 云端服务器示例 - 增强版
支持文件上传、流式传输、断点续传，优化弱网环境
支持双端口模式：WebSocket（前端）和 Socket（Agent）

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
import ssl
import uuid
from datetime import datetime
from typing import Dict, Set, Any, Optional, Tuple, List, Union
from pathlib import Path
from dataclasses import dataclass, field

# 导入更新管理模块
from update_manager import UpdateManager

# 配置日志
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s"
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
    FILE_DOWNLOAD_REQUEST = 0x25
    FILE_DOWNLOAD_DATA = 0x26
    FILE_DOWNLOAD_CONTROL = 0x27
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
    # 更新管理消息类型
    UPDATE_CHECK = 0x60  # 检查更新请求
    UPDATE_INFO = 0x61  # 更新信息响应
    UPDATE_DOWNLOAD = 0x62  # 请求下载更新包
    UPDATE_PROGRESS = 0x63  # 上报下载进度
    UPDATE_APPROVE = 0x64  # 服务器批准下载（提供URL）
    UPDATE_COMPLETE = 0x65  # 更新完成通知
    UPDATE_ERROR = 0x66  # 更新错误通知
    UPDATE_ROLLBACK = 0x67  # 回滚通知


# 有效的认证Token（已废弃，保留用于向后兼容）
# VALID_TOKENS = {
#     "test-token-123": "测试设备1",
#     "your-auth-token": "默认设备",
# }


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


class AgentSocketHandler:
    """Agent Socket 连接处理器"""

    def __init__(self, connection_manager, message_handler):
        self.conn_mgr = connection_manager
        self.msg_handler = message_handler

    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """处理 Agent Socket 连接"""
        try:
            addr = writer.get_extra_info("peername")
            logger.info(f"新Agent Socket连接: {addr}")

            device_id = None
            authenticated = False

            while True:
                # 读取消息：[1字节类型] + [2字节长度(大端)] + [JSON数据]
                try:
                    type_byte = await reader.readexactly(1)
                    msg_type = type_byte[0]

                    # 读取长度字段（2字节大端序）
                    length_bytes = await reader.readexactly(2)
                    json_len = (length_bytes[0] << 8) | length_bytes[1]

                    # 读取精确长度的JSON数据
                    if json_len > 65535:
                        logger.error(f"消息长度过大: {json_len}")
                        break

                    data = await reader.readexactly(json_len)

                    # 检查是否为注册消息（已去除认证机制）
                    if msg_type == MessageType.AUTH and not authenticated:
                        try:
                            json_str = data.decode("utf-8")
                            json_data = json.loads(json_str)
                            device_id = json_data.get("device_id", "unknown")

                            # 处理注册（自动接受所有设备）
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

                    # 已认证的消息处理
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
        """创建 Socket writer 包装器，使其具有类似 WebSocket 的 send 方法"""

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
        """通知设备列表更新"""
        device_list = self.conn_mgr.get_all_devices()
        await self.msg_handler.broadcast_to_web_consoles(
            MessageType.DEVICE_LIST, {"devices": device_list, "count": len(device_list)}
        )


class ConnectionManager:
    """连接管理器 - 管理设备连接（WebSocket + Socket）和Web控制台"""

    def __init__(self, file_transfer_manager: FileTransferManager):
        self.connected_devices: Dict[
            str, Dict[str, Any]
        ] = {}  # device_id -> {"type": "websocket"|"socket", "connection": obj}
        self.web_consoles: Set[WebSocketServerProtocol] = set()
        self.console_info: Dict[WebSocketServerProtocol, Dict[str, Any]] = {}
        self.pty_sessions: Dict[str, Dict[int, asyncio.Queue]] = {}
        self.request_sessions: Dict[
            str, Dict[str, str]
        ] = {}  # request_id -> {console_id, device_id}
        self.file_transfer = file_transfer_manager

    def add_device(
        self, device_id: str, connection: Any, conn_type: str = "websocket"
    ) -> None:
        """添加设备连接"""
        self.connected_devices[device_id] = {
            "type": conn_type,
            "connection": connection,
        }
        self.pty_sessions[device_id] = {}

    def remove_device(self, device_id: str) -> None:
        """移除设备连接"""
        self.connected_devices.pop(device_id, None)
        self.pty_sessions.pop(device_id, None)

    def add_console(self, websocket: WebSocketServerProtocol) -> None:
        """添加Web控制台"""
        console_id = str(uuid.uuid4())[:8]
        self.web_consoles.add(websocket)
        self.console_info[websocket] = {
            "console_id": console_id,
            "device_id": None,
            "session_ids": set(),
            "connected_time": time.time(),
        }
        logger.info(f"Web控制台连接: console_id={console_id}")

    def remove_console(
        self, websocket: WebSocketServerProtocol
    ) -> Tuple[Optional[str], Set[int]]:
        """移除Web控制台，返回设备ID和会话IDs以便清理PTY"""
        console_id = self.console_info.get(websocket, {}).get("console_id", "unknown")
        device_id = None
        session_ids = set()

        if websocket in self.console_info:
            device_id = self.console_info[websocket].get("device_id")
            session_ids = self.console_info[websocket].get("session_ids", set()).copy()
            self.web_consoles.discard(websocket)
            self.console_info.pop(websocket, None)

        logger.info(
            f"Web控制台断开: console_id={console_id}, device_id={device_id}, sessions={session_ids}"
        )
        return device_id, session_ids

    def set_console_device(
        self, websocket: WebSocketServerProtocol, device_id: str
    ) -> None:
        """设置控制台当前选中的设备"""
        if websocket in self.console_info:
            old_device = self.console_info[websocket].get("device_id")
            self.console_info[websocket]["device_id"] = device_id
            logger.info(
                f"控制台 {self.console_info[websocket]['console_id']} 切换设备: {old_device} -> {device_id}"
            )

    def add_console_session(
        self, websocket: WebSocketServerProtocol, session_id: int
    ) -> None:
        """记录控制台创建的session"""
        if websocket in self.console_info:
            self.console_info[websocket]["session_ids"].add(session_id)

    def get_console_by_session(
        self, device_id: str, session_id: int
    ) -> Optional[WebSocketServerProtocol]:
        """根据device_id和session_id查找对应的控制台"""
        for websocket, info in self.console_info.items():
            if info.get("device_id") == device_id and session_id in info.get(
                "session_ids", set()
            ):
                return websocket
        logger.warning(
            f"get_console_by_session未找到: device_id={device_id}, session_id={session_id}, "
            f"已注册sessions: {[(info.get('device_id'), info.get('session_ids')) for info in self.console_info.values()]}"
        )
        return None

    def add_request_session(
        self, request_id: str, console_id: str, device_id: str
    ) -> None:
        """记录request_id对应的控制台session"""
        if not request_id:
            return
        self.request_sessions[request_id] = {
            "console_id": console_id,
            "device_id": device_id,
        }
        logger.debug(
            f"注册request_session: request_id={request_id}, console_id={console_id}, device_id={device_id}"
        )

    def get_console_by_request(
        self, request_id: str
    ) -> Optional[WebSocketServerProtocol]:
        """根据request_id查找对应的控制台"""
        if not request_id or request_id not in self.request_sessions:
            return None
        req_info = self.request_sessions[request_id]
        target_console_id = req_info.get("console_id")
        target_device_id = req_info.get("device_id")

        for websocket, info in self.console_info.items():
            if (
                info.get("console_id") == target_console_id
                and info.get("device_id") == target_device_id
            ):
                return websocket
        return None

    def get_console_info(
        self, websocket: WebSocketServerProtocol
    ) -> Optional[Dict[str, Any]]:
        """获取控制台信息"""
        return self.console_info.get(websocket)

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取设备连接信息"""
        return self.connected_devices.get(device_id)

    def is_device_connected(self, device_id: str) -> bool:
        """检查设备是否已连接"""
        return device_id in self.connected_devices

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """获取所有连接的设备信息"""
        devices = []
        for device_id, dev_info in self.connected_devices.items():
            conn = dev_info["connection"]
            conn_type = dev_info["type"]
            remote_addr = self._get_remote_address(conn, conn_type)
            devices.append(
                {
                    "device_id": device_id,
                    "connected_time": datetime.now().isoformat(),
                    "status": "online",
                    "connection_type": conn_type,
                    "remote_addr": remote_addr,
                }
            )
        return devices

    def _get_remote_address(self, connection: Any, conn_type: str) -> str:
        """获取远程地址信息"""
        try:
            if conn_type == "websocket":
                remote = getattr(connection, "remote_address", "unknown")
                return remote[0] if isinstance(remote, tuple) else str(remote)
            elif conn_type == "socket":
                writer = connection
                addr = writer.get_extra_info("peername")
                return f"{addr[0]}:{addr[1]}" if addr else "unknown"
            else:
                return "unknown"
        except:
            return "unknown"


class MessageHandler:
    """消息处理器"""

    def __init__(self, connection_manager: ConnectionManager):
        self.conn_mgr = connection_manager
        # 初始化更新管理器
        self.update_manager = UpdateManager()

        # 设置广播方法的回调
        self.update_manager._broadcast_update_progress = self._broadcast_update_progress
        self.update_manager._broadcast_update_status = self._broadcast_update_status

        # 分块下载跟踪: {request_id: {"chunks": [], "total": 0, "filename": "", "size": 0}}
        self.download_chunks = {}

    @staticmethod
    def create_message(msg_type: int, data: dict) -> bytes:
        """创建消息: [type(1)] + [length(2, 大端)] + [JSON数据]"""
        json_data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        json_len = len(json_data)
        msg = bytes([msg_type]) + json_len.to_bytes(2, "big") + json_data
        logger.debug(
            f"[CREATE_MSG] type=0x{msg_type:02X}, len={json_len}, hex={msg.hex()[:50]}...{msg.hex()[-30:] if len(msg.hex()) > 80 else ''}"
        )
        return msg

    @staticmethod
    def parse_message(data: bytes) -> Tuple[Optional[int], Optional[dict]]:
        """解析消息: [type(1)] + [length(2, 大端)] + [JSON数据]"""
        if len(data) < 3:
            return None, None
        msg_type = data[0]

        # 读取长度字段（2字节大端序）
        length_bytes = data[1:3]
        json_len = (length_bytes[0] << 8) | length_bytes[1]

        # 验证数据长度
        if len(data) < 3 + json_len:
            logger.warning(f"消息不完整: 期望{3 + json_len}字节, 实际{len(data)}字节")
            return msg_type, {}

        # 提取JSON数据
        json_data_bytes = data[3 : 3 + json_len]

        try:
            json_str = json_data_bytes.decode("utf-8")
            if json_str.strip():
                json_data = json.loads(json_str)
            else:
                json_data = {}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"消息JSON解析失败: {e}")
            logger.debug(
                f"原始JSON数据（前200字节）: {json_data_bytes[:200] if len(json_data_bytes) > 0 else 'empty'}"
            )
            json_data = {}

        return msg_type, json_data

    async def handle_auth(self, websocket: WebSocketServerProtocol, data: dict) -> bool:
        """处理设备注册（已去除认证机制）"""
        device_id = data.get("device_id", "unknown")
        version = data.get("version", "unknown")

        logger.info(f"设备注册成功: {device_id} (版本: {version})")
        self.conn_mgr.add_device(device_id, websocket)

        response = self.create_message(
            MessageType.AUTH_RESULT,
            {"success": True, "message": f"欢迎, {device_id}"},
        )
        logger.info(
            f"准备发送注册响应给 {device_id}, 消息长度={len(response)}, 类型=0x{MessageType.AUTH_RESULT:02X}"
        )
        send_result = await self._safe_send(websocket, response)
        logger.info(f"_safe_send返回结果: {send_result}")
        logger.info(f"注册响应{'已成功' if send_result else '发送失败'}给 {device_id}")
        return True

    async def _safe_send(self, websocket, message: bytes) -> bool:
        """安全发送消息（支持WebSocket和Socket）"""
        try:
            # 检查是否是WebSocket连接
            if hasattr(websocket, "state"):
                if websocket.state.name != "OPEN":
                    logger.debug("WebSocket连接未开启，跳过发送")
                    return False

            # 检查是否有send方法
            if hasattr(websocket, "send") and callable(
                getattr(websocket, "send", None)
            ):
                await websocket.send(message)
                logger.debug(f"消息已发送，长度={len(message)}")
                return True
            else:
                logger.error("WebSocket对象没有send方法")
                return False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            import traceback

            traceback.print_exc()
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

        request_id = data.get("request_id")
        if request_id:
            status_data = {"device_id": device_id, **data}
            await self.unicast_by_request_id(
                MessageType.SYSTEM_STATUS,
                status_data,
                request_id,
            )

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
        session_id = int(data.get("session_id", -1))
        pty_data = data.get("data", "")

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            try:
                await self.broadcast_to_web_consoles(
                    MessageType.PTY_DATA,
                    {
                        "device_id": device_id,
                        "session_id": session_id,
                        "data": pty_data,
                    },
                    target_console_id=target_console_id,
                )
            except Exception:
                pass
        else:
            logger.warning(
                f"未找到PTY session对应的console: device={device_id}, session={session_id}"
            )

    async def handle_pty_create(self, device_id: str, data: dict) -> None:
        """处理PTY创建"""
        session_id = int(data.get("session_id", -1))
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

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            await self.broadcast_to_web_consoles(
                MessageType.PTY_CREATE,
                {"device_id": device_id, **data},
                target_console_id=target_console_id,
            )
        else:
            logger.warning(
                f"未找到PTY会话对应的web控制台 [{device_id}]: session={session_id}"
            )

    async def handle_pty_resize(self, device_id: str, data: dict) -> None:
        """处理PTY调整大小"""
        session_id = int(data.get("session_id", -1))
        rows = data.get("rows", 24)
        cols = data.get("cols", 80)

        logger.info(
            f"PTY调整大小 [{device_id}]: session={session_id}, size={cols}x{rows}"
        )

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            await self.broadcast_to_web_consoles(
                MessageType.PTY_RESIZE,
                {"device_id": device_id, **data},
                target_console_id=target_console_id,
            )
        else:
            logger.warning(
                f"未找到PTY resize对应的web控制台 [{device_id}]: session={session_id}"
            )

    async def handle_pty_close(self, device_id: str, data: dict) -> None:
        """处理PTY关闭"""
        session_id = int(data.get("session_id", -1))
        reason = data.get("reason", "unknown")
        logger.info(f"PTY会话关闭 [{device_id}]: session={session_id}, reason={reason}")

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            await self.broadcast_to_web_consoles(
                MessageType.PTY_CLOSE,
                {"device_id": device_id, **data},
                target_console_id=target_console_id,
            )
        else:
            logger.warning(
                f"未找到PTY close对应的web控制台 [{device_id}]: session={session_id}"
            )

        if (
            device_id in self.conn_mgr.pty_sessions
            and session_id in self.conn_mgr.pty_sessions[device_id]
        ):
            del self.conn_mgr.pty_sessions[device_id][session_id]

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

    # 更新处理器方法
    async def handle_update_check(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新检查请求"""
        try:
            result = await self.update_manager.handle_update_check(device_id, json_data)
            await self.send_to_device(device_id, MessageType.UPDATE_INFO, result)
            logger.info(f"[{device_id}] 已发送更新信息响应")
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新检查失败: {e}")
            error_response = {
                "has_update": "false",
                "error": f"更新检查失败: {str(e)}",
                "current_version": json_data.get("current_version", "1.0.0"),
                "latest_version": json_data.get("current_version", "1.0.0"),
            }
            await self.send_to_device(
                device_id, MessageType.UPDATE_INFO, error_response
            )

    async def handle_update_download(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新下载请求"""
        try:
            result = await self.update_manager.handle_update_download(
                device_id, json_data
            )
            if result.get("status") == "approved":
                await self.send_to_device(device_id, MessageType.UPDATE_APPROVE, result)
                logger.info(f"[{device_id}] 已批准下载: {result.get('download_url')}")
            else:
                await self.send_to_device(device_id, MessageType.UPDATE_ERROR, result)
                logger.error(f"[{device_id}] 下载请求被拒绝: {result.get('error')}")
        except Exception as e:
            logger.error(f"[{device_id}] 处理下载请求失败: {e}")
            error_response = {
                "status": "error",
                "error": f"下载请求处理失败: {str(e)}",
                "request_id": json_data.get("request_id", ""),
            }
            await self.send_to_device(
                device_id, MessageType.UPDATE_ERROR, error_response
            )

    async def handle_update_progress(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新进度报告"""
        try:
            await self.update_manager.handle_update_progress(device_id, json_data)
            # 广播进度到Web控制台
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_PROGRESS, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新进度失败: {e}")

    async def handle_update_complete(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新完成通知"""
        try:
            await self.update_manager.handle_update_complete(device_id, json_data)
            # 广播完成状态到Web控制台
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_COMPLETE, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新完成通知失败: {e}")

    async def handle_update_error(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新错误通知"""
        try:
            await self.update_manager.handle_update_error(device_id, json_data)
            # 广播错误到Web控制台
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ERROR, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新错误通知失败: {e}")

    async def handle_update_rollback(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新回滚通知"""
        try:
            await self.update_manager.handle_update_rollback(device_id, json_data)
            # 广播回滚状态到Web控制台
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ROLLBACK, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新回滚通知失败: {e}")

    # 重写更新管理器的广播方法
    async def _broadcast_update_progress(
        self, device_id: str, progress_data: Dict[str, Any]
    ) -> None:
        """广播更新进度到Web控制台"""
        await self.broadcast_to_web_consoles(MessageType.UPDATE_PROGRESS, progress_data)

    async def _broadcast_update_status(
        self, device_id: str, status_data: Dict[str, Any]
    ) -> None:
        """广播更新状态到Web控制台"""
        event_type = status_data.get("event", "update_status")
        if event_type == "update_complete":
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_COMPLETE, status_data
            )
        elif event_type == "update_error":
            await self.broadcast_to_web_consoles(MessageType.UPDATE_ERROR, status_data)
        elif event_type == "update_rollback":
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ROLLBACK, status_data
            )
        else:
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_PROGRESS, status_data
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

    async def handle_file_download_request(self, device_id: str, data: dict) -> None:
        """处理TCP文件下载请求"""
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
        """处理文件下载的内部实现"""
        try:
            # 构建完整的文件路径（假设更新包存储在updates目录）
            full_path = os.path.join("updates", os.path.basename(file_path))

            if not os.path.exists(full_path):
                # 发送错误响应
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
                # 文件已经下载完成
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

            # 读取数据块
            with open(full_path, "rb") as f:
                f.seek(offset)
                data_chunk = f.read(chunk_size)

            # Base64编码数据
            import base64

            data_b64 = base64.b64encode(data_chunk).decode("utf-8")

            # 检查是否为最后一块
            is_final = (offset + len(data_chunk)) >= file_size

            # 发送数据块响应
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
            error_response = self.create_message(
                MessageType.FILE_DOWNLOAD_DATA,
                {
                    "action": "download_error",
                    "file_path": file_path,
                    "request_id": request_id,
                    "error": str(e),
                },
            )
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

    async def handle_message(
        self, websocket, device_id: str, data: bytes, is_socket: bool = False
    ) -> None:
        """处理消息"""
        msg_type, json_data = self.parse_message(data)

        # 确保json_data不为None
        json_data = json_data or {}

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
        elif msg_type == MessageType.FILE_LIST_REQUEST:
            # Forward file list request to device
            if device_id and self.conn_mgr.is_device_connected(device_id):
                await self.send_to_device(device_id, msg_type, json_data)
            return
        elif msg_type == MessageType.FILE_REQUEST:
            # Forward file request to device
            if device_id and self.conn_mgr.is_device_connected(device_id):
                await self.send_to_device(device_id, msg_type, json_data)
            return
        elif msg_type == MessageType.FILE_DOWNLOAD_REQUEST:
            # Handle TCP file download request from agent
            await self.handle_file_download_request(device_id, json_data)
            return
        elif msg_type == MessageType.FILE_DOWNLOAD_REQUEST:
            # Handle TCP file download request from agent
            await self.handle_file_download_request(device_id, json_data)
            return
        elif msg_type in (
            MessageType.PTY_CREATE,
            MessageType.PTY_DATA,
            MessageType.PTY_RESIZE,
            MessageType.PTY_CLOSE,
        ):
            # PTY消息需要区分来源
            is_from_device = is_socket  # 来自Socket的都是Agent
            if is_from_device:
                # 从设备来的消息，广播到web consoles
                if msg_type == MessageType.PTY_DATA:
                    await self.handle_pty_data(device_id, json_data)
                elif msg_type == MessageType.PTY_CREATE:
                    await self.handle_pty_create(device_id, json_data)
                elif msg_type == MessageType.PTY_RESIZE:
                    await self.handle_pty_resize(device_id, json_data)
                elif msg_type == MessageType.PTY_CLOSE:
                    await self.handle_pty_close(device_id, json_data)
            else:
                # 从web console来的消息，转发给设备
                if device_id and self.conn_mgr.is_device_connected(device_id):
                    await self.send_to_device(device_id, msg_type, json_data)
                else:
                    logger.warning(
                        f"Cannot forward PTY message: device {device_id} not connected"
                    )
            return

        # 其他消息处理
        handlers = {
            MessageType.HEARTBEAT: self.handle_heartbeat,
            MessageType.SYSTEM_STATUS: self.handle_system_status,
            MessageType.LOG_UPLOAD: self.handle_log_upload,
            MessageType.SCRIPT_RESULT: self.handle_script_result,
            MessageType.AUTH_RESULT: self.handle_auth_result,
            # 添加更新处理器
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
            logger.info(f"收到文件数据 [{device_id}]: {json_data}")
            request_id = json_data.get("request_id")
            if request_id:
                await self.unicast_by_request_id(
                    MessageType.FILE_DATA,
                    {"device_id": device_id, **json_data},
                    request_id,
                )
            else:
                logger.warning(f"FILE_DATA缺少request_id，不发送")
        elif msg_type == MessageType.FILE_LIST_RESPONSE:
            request_id = json_data.get("request_id")
            if request_id:
                await self.unicast_by_request_id(
                    MessageType.FILE_LIST_RESPONSE,
                    {"device_id": device_id, **json_data},
                    request_id,
                )
            else:
                logger.warning(f"FILE_LIST_RESPONSE缺少request_id，不发送")
        elif msg_type == MessageType.DOWNLOAD_PACKAGE:
            await self._handle_download_package(device_id, json_data)
        elif msg_type == MessageType.CMD_RESPONSE:
            logger.info(f"收到命令响应 [{device_id}]: {json_data}")
            request_id = json_data.get("request_id")
            if request_id:
                await self.unicast_by_request_id(
                    MessageType.CMD_RESPONSE,
                    {"device_id": device_id, **json_data},
                    request_id,
                )
            else:
                logger.warning(f"CMD_RESPONSE缺少request_id，不发送")
        elif msg_type == MessageType.AUTH:
            logger.debug(f"收到认证消息 [{device_id}]（已认证）")
        elif msg_type == MessageType.DEVICE_LIST:
            logger.info(f"设备列表查询 [{device_id}]: {json_data}")
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

    async def unicast_by_request_id(
        self,
        msg_type: int,
        data: dict,
        request_id: str,
    ) -> None:
        """根据request_id单播消息到对应的web控制台"""
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

    async def broadcast_to_web_consoles(
        self,
        msg_type: int,
        data: dict,
        target_console_id: Optional[str] = None,
        target_device_id: Optional[str] = None,
    ) -> None:
        """向web控制台发送消息（支持过滤）

        Args:
            msg_type: 消息类型
            data: 消息数据
            target_console_id: 如果指定，只发送给该console_id
            target_device_id: 如果指定，只发送给关注该设备的console
        """
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
                        logger.warning(
                            f"broadcast skip by console_id: target={target_console_id}, console={console_info.get('console_id')}"
                        )
                        continue

                    if (
                        target_device_id
                        and console_info.get("device_id") is not None
                        and console_info.get("device_id") != target_device_id
                    ):
                        logger.warning(
                            f"broadcast skip by device_id: target={target_device_id}, console_device={console_info.get('device_id')}"
                        )
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
            logger.error(f"发送消息失败: {e}")

    async def _handle_download_package(self, device_id: str, json_data: dict) -> None:
        """处理打包下载响应，支持分块传输"""
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

    async def send_to_device(self, device_id: str, msg_type: int, data: dict) -> bool:
        """发送消息到设备（支持 WebSocket 和 Socket）"""
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
                # WebSocket 连接
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
                # Socket 连接
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


class CloudServer:
    """云端服务器主类"""

    def __init__(self):
        self.file_transfer = FileTransferManager()
        self.conn_mgr = ConnectionManager(self.file_transfer)
        self.msg_handler = MessageHandler(self.conn_mgr)
        self.socket_handler = AgentSocketHandler(self.conn_mgr, self.msg_handler)
        self._last_device_count = 0
        self._device_list_broadcast_task = None

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
                        # 解析认证消息: [type(1)] + [length(2, 大端)] + [JSON数据]
                        auth_len = (message[1] << 8) | message[2]
                        json_data = json.loads(
                            message[3 : 3 + auth_len].decode("utf-8")
                        )
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
                    if len(message) >= 1:
                        msg_type = message[0]
                        logger.info(f"收到设备消息 [0x{msg_type:02X}] 从 {device_id}")
                    await self.msg_handler.handle_message(websocket, device_id, message)

                # Web控制台的消息处理
                elif not is_device:
                    try:
                        # 解析消息: [type(1)] + [length(2, 大端)] + [JSON数据]
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
                                device_list = self.conn_mgr.get_all_devices()
                                response = self.msg_handler.create_message(
                                    MessageType.DEVICE_LIST,
                                    {"devices": device_list, "count": len(device_list)},
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
                    await self.notify_device_list_update()
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

    async def notify_device_list_update(self) -> None:
        """通知web控制台设备列表更新"""
        device_list = self.conn_mgr.get_all_devices()
        await self.msg_handler.broadcast_to_web_consoles(
            MessageType.DEVICE_LIST, {"devices": device_list, "count": len(device_list)}
        )

    def _start_device_list_monitor(self) -> None:
        """启动设备列表监控定时任务"""
        self._device_list_broadcast_task = asyncio.create_task(
            self._check_device_list_changes()
        )

    async def _check_device_list_changes(self) -> None:
        """定时检查设备列表变化，有新设备时广播"""
        while True:
            await asyncio.sleep(15)
            current_count = len(self.conn_mgr.connected_devices)
            if current_count > self._last_device_count:
                await self.notify_device_list_update()
            self._last_device_count = current_count

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
        """运行服务器（双端口模式：WebSocket + Socket）"""
        host = "0.0.0.0"
        ws_port = 8765  # 前端 WebSocket 端口
        socket_port = 8766  # Agent Socket 端口

        logger.info(f"启动WebSocket服务器（前端）: ws://{host}:{ws_port}")
        logger.info(f"启动Socket服务器（Agent）: {host}:{socket_port}")
        logger.info(f"文件上传目录: {os.path.abspath(self.file_transfer.UPLOAD_DIR)}")

        # 启动 WebSocket 服务器
        ws_server = await websockets.serve(
            self.agent_handler, host, ws_port, ping_interval=30, ping_timeout=10
        )

        # 启动 Socket 服务器
        socket_server = await asyncio.start_server(
            self.socket_handler.handle_connection, host, socket_port
        )

        # 启动设备列表监控任务
        self._start_device_list_monitor()

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


async def main() -> None:
    """主函数"""
    server = CloudServer()
    try:
        await server.run()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    asyncio.run(main())
