"""
模拟 Agent 客户端 - 用于测试 Server
"""

import asyncio
import json
import struct
import time
import uuid
from typing import Optional, Callable


class MockAgent:
    """模拟 Buildroot Agent 客户端"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.device_id = f"test-{uuid.uuid4().hex[:8]}"
        self.connected = False
        self.registered = False
        self.message_handlers: dict[int, Callable] = {}
        self.received_messages: list[dict] = []

    async def connect(self) -> bool:
        """连接到 Server"""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=5.0
            )
            self.connected = True
            # 启动消息接收循环
            asyncio.create_task(self._receive_loop())
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        self.connected = False
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self.reader = None
        self.writer = None

    async def _receive_loop(self):
        """消息接收循环"""
        while self.connected and self.reader:
            try:
                # 读取消息头 (3 bytes: type + length)
                header = await self.reader.read(3)
                if len(header) < 3:
                    break

                msg_type = header[0]
                msg_len = struct.unpack(">H", header[1:3])[0]

                # 读取消息体
                data = b""
                while len(data) < msg_len:
                    chunk = await self.reader.read(msg_len - len(data))
                    if not chunk:
                        break
                    data += chunk

                # 解析 JSON
                try:
                    payload = json.loads(data.decode("utf-8"))
                    message = {
                        "type": msg_type,
                        "payload": payload,
                        "timestamp": time.time(),
                    }
                    self.received_messages.append(message)

                    # 调用消息处理器
                    if msg_type in self.message_handlers:
                        await self.message_handlers[msg_type](payload)
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    async def send_message(self, msg_type: int, payload: dict) -> bool:
        """发送消息到 Server"""
        if not self.writer:
            return False

        try:
            data = json.dumps(payload).encode("utf-8")
            header = struct.pack("B", msg_type) + struct.pack(">H", len(data))
            self.writer.write(header + data)
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"发送消息失败: {e}")
            return False

    async def register(self, device_info: Optional[dict] = None) -> bool:
        """发送注册消息"""
        if not device_info:
            device_info = {
                "device_id": self.device_id,
                "hostname": "test-device",
                "ip": "127.0.0.1",
                "mac": "00:11:22:33:44:55",
                "version": "1.0.0",
            }

        # 0xF0 = REGISTER
        success = await self.send_message(0xF0, device_info)
        if success:
            # 等待注册结果
            await asyncio.sleep(0.5)
            for msg in self.received_messages:
                if msg["type"] == 0xF1:  # REGISTER_RESULT
                    self.registered = msg["payload"].get("success", False)
                    return self.registered
        return False

    async def send_heartbeat(self) -> bool:
        """发送心跳"""
        # 0x01 = HEARTBEAT
        return await self.send_message(
            0x01, {"device_id": self.device_id, "timestamp": int(time.time())}
        )

    async def send_status(self, status: dict) -> bool:
        """发送系统状态"""
        # 0x02 = SYSTEM_STATUS
        status["device_id"] = self.device_id
        return await self.send_message(0x02, status)

    async def wait_for_message(
        self, msg_type: int, timeout: float = 5.0
    ) -> Optional[dict]:
        """等待特定类型的消息"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            for msg in self.received_messages:
                if msg["type"] == msg_type:
                    return msg
            await asyncio.sleep(0.1)
        return None

    def get_messages_by_type(self, msg_type: int) -> list[dict]:
        """获取特定类型的所有消息"""
        return [m for m in self.received_messages if m["type"] == msg_type]

    def clear_messages(self):
        """清空消息列表"""
        self.received_messages.clear()
