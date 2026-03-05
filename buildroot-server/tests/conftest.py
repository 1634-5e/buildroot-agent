"""
Pytest configuration and fixtures for buildroot-server tests.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import pytest_asyncio

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from protocol.constants import MessageType


class MockAgent:
    """模拟 Agent 客户端，用于测试 Server。"""

    def __init__(self, device_id: str = None):
        self.device_id = device_id or f"test_device_{int(time.time())}"
        self.socket = None
        self.connected = False
        self.received_messages = []
        self._read_task = None

    async def connect(self, host: str = "127.0.0.1", port: int = 18766):
        """连接到 Server。"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(False)
        await asyncio.get_event_loop().sock_connect(self.socket, (host, port))
        self.connected = True
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        """后台读取消息。"""
        buffer = b""
        while self.connected:
            try:
                chunk = await asyncio.wait_for(
                    asyncio.get_event_loop().sock_recv(self.socket, 4096), timeout=1.0
                )
                if not chunk:
                    break
                buffer += chunk

                # 解析消息
                while len(buffer) >= 3:
                    msg_type = buffer[0]
                    msg_len = int.from_bytes(buffer[1:3], "big")
                    if len(buffer) < 3 + msg_len:
                        break
                    data = buffer[3 : 3 + msg_len].decode("utf-8")
                    self.received_messages.append(
                        {"type": msg_type, "data": json.loads(data) if data else {}}
                    )
                    buffer = buffer[3 + msg_len :]
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    async def send(self, msg_type: int, data: dict):
        """发送消息。"""
        if not self.connected:
            raise ConnectionError("Not connected")
        payload = json.dumps(data).encode("utf-8")
        header = bytes([msg_type]) + len(payload).to_bytes(2, "big")
        await asyncio.get_event_loop().sock_sendall(self.socket, header + payload)

    async def register(self):
        """发送注册消息。"""
        await self.send(
            MessageType.REGISTER,
            {
                "device_id": self.device_id,
                "hostname": "test-host",
                "version": "1.0.0",
                "ip": "127.0.0.1",
            },
        )
        await asyncio.sleep(0.1)

    async def heartbeat(self):
        """发送心跳。"""
        await self.send(MessageType.HEARTBEAT, {"timestamp": int(time.time() * 1000)})

    def clear_messages(self):
        """清空接收到的消息。"""
        self.received_messages.clear()

    async def send_message(self, msg_type: int, data: dict = None):
        """发送消息。"""
        await self.send(msg_type, data or {})

    async def send_status(self):
        """发送状态请求。"""
        await self.send(3, {"timestamp": int(time.time() * 1000)})  # MessageType.STATUS_REQUEST = 3

    async def send_register(self):
        """发送注册消息。"""
        await self.register()

    async def disconnect(self):
        """断开连接。"""
        self.connected = False
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        if self.socket:
            self.socket.close()

    def get_message(self, msg_type: int = None, timeout: float = 2.0) -> dict:
        """获取接收到的消息。"""
        start = time.time()
        while time.time() - start < timeout:
            for msg in self.received_messages:
                if msg_type is None or msg["type"] == msg_type:
                    self.received_messages.remove(msg)
                    return msg
            time.sleep(0.05)
        return None

    def get_messages(self, msg_type: int = None, timeout: float = 2.0) -> list:
        """获取多个接收到的消息。"""
        start = time.time()
        messages = []
        while time.time() - start < timeout:
            messages = [
                msg for msg in self.received_messages
                if msg_type is None or msg["type"] == msg_type
            ]
            if messages:
                for msg in messages:
                    self.received_messages.remove(msg)
                return messages
            time.sleep(0.05)
        return messages


@pytest_asyncio.fixture
async def mock_agent():
    """创建 MockAgent 实例。"""
    agent = MockAgent()
    yield agent
    await agent.disconnect()


@pytest.fixture(scope="session")
def server_port():
    """获取可用端口。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="session")
def temp_db():
    """创建临时数据库文件。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(scope="session")
def server_process():
    """启动测试服务器进程。

    用于集成测试，启动真实的 Server 进程。
    """
    import sys
    import time

    # 设置测试环境变量
    env = os.environ.copy()
    env["BR_SERVER_DATABASE_URL"] = "sqlite+aiosqlite:///test_integration.db"
    env["BR_SERVER_SOCKET_PORT"] = "18766"
    env["BR_SERVER_WS_PORT"] = "18765"
    env["BR_SERVER_LOG_LEVEL"] = "ERROR"  # 减少日志输出

    # 启动服务器进程
    proc = subprocess.Popen(
        [sys.executable, "-m", "main"],
        cwd=str(Path(__file__).parent.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 等待服务器启动
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", 18766))
            sock.close()
            if result == 0:
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        proc.wait()
        raise RuntimeError("Server failed to start within 10 seconds")

    yield proc

    # 清理
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    # 清理测试数据库
    if os.path.exists("test_integration.db"):
        os.unlink("test_integration.db")


@pytest.fixture
def test_config():
    """集成测试配置"""
    return {
        "server_host": "127.0.0.1",
        "socket_port": 18766,
        "ws_port": 18765,
    }


@pytest_asyncio.fixture
async def connected_agent(mock_agent):
    """创建已连接的 MockAgent 实例。"""
    await mock_agent.connect()
    yield mock_agent
