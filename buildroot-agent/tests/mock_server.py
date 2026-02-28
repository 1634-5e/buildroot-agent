#!/usr/bin/env python3
"""
Mock Server for Agent Testing
模拟服务器用于测试 Agent 端功能
"""

import asyncio
import json
import struct
import logging
import argparse
from datetime import datetime
from typing import Optional, Callable, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# 消息类型定义（与 agent.h 保持一致）
MSG_TYPE_HEARTBEAT = 0x01
MSG_TYPE_SYSTEM_STATUS = 0x02
MSG_TYPE_LOG_UPLOAD = 0x03
MSG_TYPE_SCRIPT_RECV = 0x04
MSG_TYPE_SCRIPT_RESULT = 0x05
MSG_TYPE_PTY_CREATE = 0x10
MSG_TYPE_PTY_DATA = 0x11
MSG_TYPE_PTY_RESIZE = 0x12
MSG_TYPE_PTY_CLOSE = 0x13
MSG_TYPE_FILE_REQUEST = 0x20
MSG_TYPE_FILE_DATA = 0x21
MSG_TYPE_FILE_LIST_REQUEST = 0x22
MSG_TYPE_FILE_LIST_RESPONSE = 0x23
MSG_TYPE_DOWNLOAD_PACKAGE = 0x24
MSG_TYPE_FILE_DOWNLOAD_REQUEST = 0x25
MSG_TYPE_FILE_DOWNLOAD_DATA = 0x26
MSG_TYPE_CMD_REQUEST = 0x30
MSG_TYPE_CMD_RESPONSE = 0x31
MSG_TYPE_DEVICE_LIST = 0x50
MSG_TYPE_DEVICE_DISCONNECT = 0x51
MSG_TYPE_DEVICE_UPDATE = 0x52
MSG_TYPE_REGISTER = 0xF0
MSG_TYPE_REGISTER_RESULT = 0xF1
MSG_TYPE_UPDATE_CHECK = 0x60
MSG_TYPE_UPDATE_INFO = 0x61
MSG_TYPE_PING_STATUS = 0x70


class MockAgentServer:
    """模拟 Agent 服务器"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        self.host = host
        self.port = port
        self.server = None
        self.clients: Dict[str, Any] = {}
        self.message_handlers: Dict[int, Callable] = {
            MSG_TYPE_REGISTER: self._handle_register,
            MSG_TYPE_HEARTBEAT: self._handle_heartbeat,
            MSG_TYPE_SYSTEM_STATUS: self._handle_system_status,
            MSG_TYPE_LOG_UPLOAD: self._handle_log_upload,
            MSG_TYPE_SCRIPT_RESULT: self._handle_script_result,
            MSG_TYPE_PTY_CREATE: self._handle_pty_create,
            MSG_TYPE_PTY_DATA: self._handle_pty_data,
            MSG_TYPE_PTY_RESIZE: self._handle_pty_resize,
            MSG_TYPE_PTY_CLOSE: self._handle_pty_close,
            MSG_TYPE_FILE_LIST_REQUEST: self._handle_file_list_request,
            MSG_TYPE_FILE_DOWNLOAD_REQUEST: self._handle_file_download_request,
            MSG_TYPE_CMD_REQUEST: self._handle_cmd_request,
            MSG_TYPE_UPDATE_CHECK: self._handle_update_check,
            MSG_TYPE_PING_STATUS: self._handle_ping_status,
        }
        self.registered_devices: set = set()
        self.message_log: list = []

    async def start(self):
        """启动服务器"""
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        logger.info(f"Mock Server started on {self.host}:{self.port}")

    async def stop(self):
        """停止服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Mock Server stopped")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """处理客户端连接"""
        addr = writer.get_extra_info("peername")
        logger.info(f"New client connected: {addr}")

        client_id = f"{addr[0]}:{addr[1]}"
        self.clients[client_id] = {
            "reader": reader,
            "writer": writer,
            "addr": addr,
            "device_id": None,
            "registered": False,
        }

        try:
            while True:
                # 读取消息头 (3 bytes: type + length)
                header = await reader.readexactly(3)
                if len(header) < 3:
                    break

                msg_type = header[0]
                msg_len = struct.unpack(">H", header[1:3])[0]

                # 读取消息体
                data = await reader.readexactly(msg_len)

                # 记录消息
                self.message_log.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "client_id": client_id,
                        "msg_type": hex(msg_type),
                        "data_len": msg_len,
                    }
                )

                # 处理消息
                await self._process_message(client_id, msg_type, data)

        except asyncio.IncompleteReadError:
            logger.info(f"Client disconnected: {addr}")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            await self._cleanup_client(client_id)

    async def _process_message(self, client_id: str, msg_type: int, data: bytes):
        """处理消息"""
        handler = self.message_handlers.get(msg_type)
        if handler:
            try:
                await handler(client_id, data)
            except Exception as e:
                logger.error(f"Error handling message 0x{msg_type:02X}: {e}")
        else:
            logger.warning(f"Unknown message type: 0x{msg_type:02X}")

    async def _send_message(self, client_id: str, msg_type: int, payload: dict):
        """发送消息给客户端"""
        if client_id not in self.clients:
            logger.error(f"Client {client_id} not found")
            return

        writer = self.clients[client_id]["writer"]
        try:
            data = json.dumps(payload).encode("utf-8")
            header = struct.pack("B", msg_type) + struct.pack(">H", len(data))
            writer.write(header + data)
            await writer.drain()
            logger.debug(f"Sent message 0x{msg_type:02X} to {client_id}")
        except Exception as e:
            logger.error(f"Error sending message to {client_id}: {e}")

    async def _cleanup_client(self, client_id: str):
        """清理客户端连接"""
        if client_id in self.clients:
            client = self.clients[client_id]
            if client.get("device_id"):
                self.registered_devices.discard(client["device_id"])
                logger.info(f"Device {client['device_id']} unregistered")

            try:
                client["writer"].close()
                await client["writer"].wait_closed()
            except:
                pass

            del self.clients[client_id]
            logger.info(f"Client {client_id} cleaned up")

    # ============= 消息处理器 =============

    async def _handle_register(self, client_id: str, data: bytes):
        """处理注册消息"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = payload.get("device_id", "unknown")
            version = payload.get("version", "unknown")

            self.clients[client_id]["device_id"] = device_id
            self.clients[client_id]["registered"] = True
            self.registered_devices.add(device_id)

            logger.info(f"Device registered: {device_id} (v{version})")

            # 发送注册结果
            await self._send_message(
                client_id,
                MSG_TYPE_REGISTER_RESULT,
                {
                    "success": True,
                    "message": "Registration successful",
                    "device_id": device_id,
                },
            )
        except Exception as e:
            logger.error(f"Error handling register: {e}")
            await self._send_message(
                client_id,
                MSG_TYPE_REGISTER_RESULT,
                {"success": False, "message": str(e)},
            )

    async def _handle_heartbeat(self, client_id: str, data: bytes):
        """处理心跳消息"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            logger.debug(f"Heartbeat from {device_id}")
            # 心跳不需要响应
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")

    async def _handle_system_status(self, client_id: str, data: bytes):
        """处理系统状态消息"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            cpu = payload.get("cpu_usage", 0)
            mem = payload.get("mem_used", 0)
            logger.info(f"Status from {device_id}: CPU={cpu:.1f}%, MEM={mem:.0f}MB")
        except Exception as e:
            logger.error(f"Error handling system status: {e}")

    async def _handle_log_upload(self, client_id: str, data: bytes):
        """处理日志上传"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            filepath = payload.get("filepath", "unknown")
            logger.info(f"Log upload from {device_id}: {filepath}")
        except Exception as e:
            logger.error(f"Error handling log upload: {e}")

    async def _handle_script_result(self, client_id: str, data: bytes):
        """处理脚本执行结果"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            script_id = payload.get("script_id", "unknown")
            success = payload.get("success", False)
            logger.info(
                f"Script result from {device_id}: {script_id} success={success}"
            )
        except Exception as e:
            logger.error(f"Error handling script result: {e}")

    async def _handle_pty_create(self, client_id: str, data: bytes):
        """处理 PTY 创建"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            session_id = payload.get("session_id", 0)
            logger.info(f"PTY create from {device_id}: session={session_id}")
            # 发送 shell 提示符
            await self._send_message(
                client_id, MSG_TYPE_PTY_DATA, {"session_id": session_id, "data": "$ "}
            )
        except Exception as e:
            logger.error(f"Error handling PTY create: {e}")

    async def _handle_pty_data(self, client_id: str, data: bytes):
        """处理 PTY 数据"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            session_id = payload.get("session_id", 0)
            data_str = payload.get("data", "")
            logger.debug(
                f"PTY data from {device_id}: session={session_id}, data={repr(data_str)}"
            )
            # 简单回显
            if data_str.strip():
                response = f"Echo: {data_str}\r\n$ "
                await self._send_message(
                    client_id,
                    MSG_TYPE_PTY_DATA,
                    {"session_id": session_id, "data": response},
                )
        except Exception as e:
            logger.error(f"Error handling PTY data: {e}")

    async def _handle_pty_resize(self, client_id: str, data: bytes):
        """处理 PTY 调整大小"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            session_id = payload.get("session_id", 0)
            rows = payload.get("rows", 24)
            cols = payload.get("cols", 80)
            logger.info(
                f"PTY resize from {device_id}: session={session_id}, {rows}x{cols}"
            )
        except Exception as e:
            logger.error(f"Error handling PTY resize: {e}")

    async def _handle_pty_close(self, client_id: str, data: bytes):
        """处理 PTY 关闭"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            session_id = payload.get("session_id", 0)
            logger.info(f"PTY close from {device_id}: session={session_id}")
        except Exception as e:
            logger.error(f"Error handling PTY close: {e}")

    async def _handle_file_list_request(self, client_id: str, data: bytes):
        """处理文件列表请求"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            path = payload.get("path", "/")
            logger.info(f"File list request from {device_id}: {path}")

            # 返回模拟文件列表
            await self._send_message(
                client_id,
                MSG_TYPE_FILE_LIST_RESPONSE,
                {
                    "path": path,
                    "files": [
                        {"name": "test.txt", "size": 1024, "is_dir": False},
                        {"name": "test_dir", "size": 0, "is_dir": True},
                    ],
                },
            )
        except Exception as e:
            logger.error(f"Error handling file list request: {e}")

    async def _handle_file_download_request(self, client_id: str, data: bytes):
        """处理文件下载请求"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            file_path = payload.get("file_path", "unknown")
            logger.info(f"File download request from {device_id}: {file_path}")
        except Exception as e:
            logger.error(f"Error handling file download request: {e}")

    async def _handle_cmd_request(self, client_id: str, data: bytes):
        """处理命令请求"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            command = payload.get("command", "")
            logger.info(f"Command request from {device_id}: {command}")

            # 返回模拟命令结果
            await self._send_message(
                client_id,
                MSG_TYPE_CMD_RESPONSE,
                {"exit_code": 0, "output": f"Executed: {command}", "error": ""},
            )
        except Exception as e:
            logger.error(f"Error handling command request: {e}")

    async def _handle_update_check(self, client_id: str, data: bytes):
        """处理更新检查"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            current_version = payload.get("current_version", "unknown")
            logger.info(f"Update check from {device_id}: current={current_version}")

            # 返回无更新
            await self._send_message(
                client_id,
                MSG_TYPE_UPDATE_INFO,
                {
                    "has_update": False,
                    "current_version": current_version,
                    "latest_version": current_version,
                    "message": "No update available",
                },
            )
        except Exception as e:
            logger.error(f"Error handling update check: {e}")

    async def _handle_ping_status(self, client_id: str, data: bytes):
        """处理 Ping 状态"""
        try:
            payload = json.loads(data.decode("utf-8"))
            device_id = self.clients[client_id].get("device_id", "unknown")
            results = payload.get("results", [])
            logger.info(f"Ping status from {device_id}: {len(results)} targets")
        except Exception as e:
            logger.error(f"Error handling ping status: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Mock Server for Agent Testing")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8766, help="Port to bind (default: 8766)"
    )
    args = parser.parse_args()

    server = MockAgentServer(args.host, args.port)
    await server.start()

    try:
        # 保持运行
        while True:
            await asyncio.sleep(1)
            if server.registered_devices:
                logger.info(f"Registered devices: {len(server.registered_devices)}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
