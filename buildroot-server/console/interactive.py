import asyncio
import logging
import os
from datetime import datetime

from protocol.constants import MessageType

logger = logging.getLogger(__name__)


class InteractiveConsole:
    """交互式控制台"""

    def __init__(self, server):
        self.server = server

    async def interactive_console(self) -> None:
        await asyncio.sleep(2)

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
        devices = self.server.conn_mgr.connected_devices
        if devices:
            print("已连接设备:")
            for dev_id in devices:
                print(f"  - {dev_id}")
        else:
            print("没有已连接的设备")

    async def _cmd_status(self, device_id: str) -> None:
        await self.server.msg_handler.send_to_device(
            device_id,
            MessageType.CMD_REQUEST,
            {"cmd": "status", "request_id": "status-1"},
        )
        print(f"已请求设备状态: {device_id}")

    async def _cmd_exec(self, device_id: str, command: str) -> None:
        await self.server.msg_handler.send_to_device(
            device_id,
            MessageType.CMD_REQUEST,
            {
                "cmd": command,
                "request_id": f"exec-{datetime.now().timestamp()}",
            },
        )
        print(f"已发送命令: {command}")

    async def _cmd_script(self, device_id: str) -> None:
        await self.server.msg_handler.send_to_device(
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
        session_id = 1
        await self.server.msg_handler.send_to_device(
            device_id,
            MessageType.PTY_CREATE,
            {"session_id": session_id, "rows": 24, "cols": 80},
        )
        print(f"已请求创建PTY会话: {device_id}")
        print("(PTY交互功能需要在Web界面或专用客户端中使用)")

    async def _cmd_tail(self, device_id: str, filepath: str) -> None:
        await self.server.msg_handler.send_to_device(
            device_id,
            MessageType.FILE_REQUEST,
            {"action": "tail", "filepath": filepath, "lines": 50},
        )
        print(f"已请求日志: {filepath}")

    async def _cmd_uploads(self) -> None:
        upload_dir = "./uploads"
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
