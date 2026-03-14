"""
模拟 Agent 客户端 - 支持 PTY 终端
"""

import asyncio
import json
import os
import pty
import signal
import struct
import termios
import time
import uuid
from typing import Optional


class MockAgentPTY:
    """模拟 Buildroot Agent 客户端 - 支持 PTY"""

    # 消息类型
    HEARTBEAT = 0x01
    SYSTEM_STATUS = 0x02
    PTY_CREATE = 0x10
    PTY_DATA = 0x11
    PTY_RESIZE = 0x12
    PTY_CLOSE = 0x13
    REGISTER = 0xF0
    REGISTER_RESULT = 0xF1

    def __init__(self, host: str = "127.0.0.1", port: int = 8766, device_id: str = None):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.device_id = device_id or f"test-{uuid.uuid4().hex[:8]}"
        self.connected = False
        self.registered = False

        # PTY 会话
        self.pty_sessions: dict[int, dict] = {}  # session_id -> {master_fd, process}

    async def connect(self) -> bool:
        """连接到 Server"""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=5.0
            )
            self.connected = True
            asyncio.create_task(self._receive_loop())
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        self.connected = False

        # 关闭所有 PTY 会话
        for session_id in list(self.pty_sessions.keys()):
            await self._close_pty(session_id)

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
                header = await self.reader.read(3)
                if len(header) < 3:
                    break

                msg_type = header[0]
                msg_len = struct.unpack(">H", header[1:3])[0]

                data = b""
                while len(data) < msg_len:
                    chunk = await self.reader.read(msg_len - len(data))
                    if not chunk:
                        break
                    data += chunk

                try:
                    payload = json.loads(data.decode("utf-8"))
                    await self._handle_message(msg_type, payload)
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"接收错误: {e}")
                break

    async def _handle_message(self, msg_type: int, payload: dict):
        """处理收到的消息"""
        if msg_type == self.REGISTER_RESULT:
            self.registered = payload.get("success", False)
            print(f"注册结果: {payload}")

        elif msg_type == self.PTY_CREATE:
            await self._handle_pty_create(payload)

        elif msg_type == self.PTY_DATA:
            await self._handle_pty_data(payload)

        elif msg_type == self.PTY_RESIZE:
            await self._handle_pty_resize(payload)

        elif msg_type == self.PTY_CLOSE:
            await self._handle_pty_close(payload)

    async def _handle_pty_create(self, payload: dict):
        """处理 PTY_CREATE 请求"""
        session_id = payload.get("session_id")
        rows = payload.get("rows", 24)
        cols = payload.get("cols", 80)

        print(f"[PTY] 创建会话: session_id={session_id}, size={cols}x{rows}")

        try:
            # 创建伪终端
            master_fd, slave_fd = pty.openpty()

            # 设置终端大小
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl = __import__("fcntl")
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

            # 启动 shell
            process = await asyncio.create_subprocess_exec(
                "/bin/bash",
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
            )

            os.close(slave_fd)

            # 保存会话
            self.pty_sessions[session_id] = {
                "master_fd": master_fd,
                "process": process,
                "rows": rows,
                "cols": cols,
            }

            # 启动读取任务
            asyncio.create_task(self._pty_read_loop(session_id))

            # 发送创建成功响应
            await self._send_message(self.PTY_CREATE, {
                "session_id": session_id,
                "status": "created",
                "rows": rows,
                "cols": cols,
            })

            print(f"[PTY] 会话创建成功: {session_id}")

        except Exception as e:
            print(f"[PTY] 创建失败: {e}")
            await self._send_message(self.PTY_CREATE, {
                "session_id": session_id,
                "status": "error",
                "error": str(e),
            })

    async def _handle_pty_data(self, payload: dict):
        """处理 PTY_DATA (用户输入)"""
        session_id = payload.get("session_id")
        data = payload.get("data", "")

        session = self.pty_sessions.get(session_id)
        if not session:
            return

        try:
            os.write(session["master_fd"], data.encode("utf-8"))
        except Exception as e:
            print(f"[PTY] 写入失败: {e}")

    async def _handle_pty_resize(self, payload: dict):
        """处理 PTY_RESIZE"""
        session_id = payload.get("session_id")
        rows = payload.get("rows", 24)
        cols = payload.get("cols", 80)

        session = self.pty_sessions.get(session_id)
        if not session:
            return

        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl = __import__("fcntl")
            fcntl.ioctl(session["master_fd"], termios.TIOCSWINSZ, winsize)
            session["rows"] = rows
            session["cols"] = cols
            print(f"[PTY] 调整大小: {session_id} -> {cols}x{rows}")
        except Exception as e:
            print(f"[PTY] 调整大小失败: {e}")

    async def _handle_pty_close(self, payload: dict):
        """处理 PTY_CLOSE"""
        session_id = payload.get("session_id")
        await self._close_pty(session_id)

    async def _close_pty(self, session_id: int):
        """关闭 PTY 会话"""
        session = self.pty_sessions.pop(session_id, None)
        if not session:
            return

        try:
            os.close(session["master_fd"])
        except Exception:
            pass

        try:
            session["process"].terminate()
            await asyncio.wait_for(session["process"].wait(), timeout=2.0)
        except Exception:
            try:
                session["process"].kill()
            except Exception:
                pass

        print(f"[PTY] 会话已关闭: {session_id}")

    async def _pty_read_loop(self, session_id: int):
        """PTY 输出读取循环"""
        session = self.pty_sessions.get(session_id)
        if not session:
            return

        master_fd = session["master_fd"]
        loop = asyncio.get_event_loop()

        try:
            while session_id in self.pty_sessions:
                # 使用 asyncio 读取文件描述符
                try:
                    data = await loop.run_in_executor(None, os.read, master_fd, 4096)
                    if not data:
                        break

                    # 发送到 server
                    await self._send_message(self.PTY_DATA, {
                        "session_id": session_id,
                        "data": data.decode("utf-8", errors="replace"),
                    })
                except OSError:
                    break
        except Exception as e:
            print(f"[PTY] 读取错误: {e}")
        finally:
            # 会话结束，通知 server
            if session_id in self.pty_sessions:
                await self._send_message(self.PTY_CLOSE, {
                    "session_id": session_id,
                    "reason": "shell exited",
                })
                await self._close_pty(session_id)

    async def _send_message(self, msg_type: int, payload: dict) -> bool:
        """发送消息"""
        if not self.writer:
            return False

        try:
            data = json.dumps(payload).encode("utf-8")
            header = struct.pack("B", msg_type) + struct.pack(">H", len(data))
            self.writer.write(header + data)
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"发送失败: {e}")
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

        success = await self._send_message(self.REGISTER, device_info)
        if success:
            await asyncio.sleep(0.5)
        return self.registered

    async def send_heartbeat(self) -> bool:
        """发送心跳"""
        return await self._send_message(
            self.HEARTBEAT,
            {"device_id": self.device_id, "timestamp": int(time.time())}
        )

    async def send_status(self, status: dict) -> bool:
        """发送系统状态"""
        status["device_id"] = self.device_id
        return await self._send_message(self.SYSTEM_STATUS, status)


async def main():
    print("=" * 60)
    print("Mock Agent (PTY 支持)")
    print("=" * 60)

    agent = MockAgentPTY(host="127.0.0.1", port=8766)
    print(f"Device ID: {agent.device_id}")

    print("\n连接到 Server...")
    if not await agent.connect():
        print("连接失败")
        return

    print("连接成功")

    print("\n注册设备...")
    if not await agent.register():
        print("注册失败")
        await agent.disconnect()
        return

    print("注册成功")

    print("\n发送系统状态...")
    await agent.send_status({
        "cpu_usage": 25.5,
        "memory_usage": 40.0,
        "disk_usage": 30.0,
        "uptime": 12345,
    })

    print("\n" + "=" * 60)
    print("Agent 运行中 (支持 PTY)")
    print("=" * 60)

    try:
        while agent.connected:
            await asyncio.sleep(10)
            await agent.send_heartbeat()
            print("[心跳已发送]")
    except KeyboardInterrupt:
        print("\n断开连接...")
        await agent.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n退出")