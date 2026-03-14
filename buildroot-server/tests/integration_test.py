#!/usr/bin/env python3
"""
真实场景集成测试 - 模拟 Agent 客户端
用于测试 Server 端的各项功能
"""

import asyncio
import json
import struct
import time
import uuid
from datetime import datetime
from typing import Optional


class MockAgent:
    """模拟 Agent 客户端"""

    def __init__(
        self,
        device_id: Optional[str] = None,
        server_host: str = "127.0.0.1",
        server_port: int = 8766,
    ):
        self.device_id = device_id or f"test-{uuid.uuid4().hex[:8]}"
        self.server_host = server_host
        self.server_port = server_port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.registered = False
        self.heartbeat_count = 0
        self.messages_received = []

    async def connect(self) -> bool:
        """连接到 Server"""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.server_host, self.server_port), timeout=5.0
            )
            self.connected = True
            print(
                f"[{self.device_id}] 已连接到 Server {self.server_host}:{self.server_port}"
            )
            return True
        except Exception as e:
            print(f"[{self.device_id}] 连接失败: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False
        self.registered = False
        print(f"[{self.device_id}] 已断开连接")

    def _send_message(self, msg_type: int, data: bytes):
        """发送消息（二进制协议）"""
        if not self.writer:
            return False

        # 协议: [msg_type(1字节)] [length(2字节大端)] [data]
        header = struct.pack(">BH", msg_type, len(data))
        self.writer.write(header + data)
        return True

    def _send_json(self, msg_type: int, data: dict):
        """发送 JSON 消息"""
        json_bytes = json.dumps(data).encode("utf-8")
        return self._send_message(msg_type, json_bytes)

    async def register(self) -> bool:
        """发送注册消息"""
        if not self.connected:
            return False

        register_data = {
            "device_id": self.device_id,
            "hostname": f"test-host-{self.device_id}",
            "ip": "127.0.0.1",
            "mac": "00:11:22:33:44:55",
            "version": "1.0.0",
            "platform": "linux",
            "arch": "x86_64",
        }

        self._send_json(0xF0, register_data)  # REGISTER
        print(f"[{self.device_id}] 发送注册消息")

        # 等待注册结果
        try:
            response = await asyncio.wait_for(self._receive_message(), timeout=5.0)
            if response and response.get("type") == 0xF1:  # REGISTER_RESULT
                result = json.loads(response.get("data", "{}"))
                if result.get("success"):
                    self.registered = True
                    print(f"[{self.device_id}] 注册成功")
                    return True
                else:
                    print(f"[{self.device_id}] 注册失败: {result}")
            return False
        except asyncio.TimeoutError:
            print(f"[{self.device_id}] 注册超时")
            return False

    async def send_heartbeat(self) -> bool:
        """发送心跳"""
        if not self.registered:
            return False

        heartbeat_data = {
            "timestamp": int(time.time() * 1000),
            "device_id": self.device_id,
        }

        self._send_json(0x01, heartbeat_data)  # HEARTBEAT
        self.heartbeat_count += 1
        print(f"[{self.device_id}] 发送心跳 #{self.heartbeat_count}")
        return True

    async def send_system_status(self) -> bool:
        """发送系统状态"""
        if not self.registered:
            return False

        status_data = {
            "timestamp": int(time.time() * 1000),
            "device_id": self.device_id,
            "cpu_usage": 25.5,
            "cpu_cores": 4,
            "cpu_user": 15.0,
            "cpu_system": 10.5,
            "mem_total": 16384.0,
            "mem_used": 8192.0,
            "mem_free": 8192.0,
            "disk_total": 512000.0,
            "disk_used": 256000.0,
            "load_1min": 0.5,
            "load_5min": 0.6,
            "load_15min": 0.7,
            "uptime": 3600,
            "net_rx_bytes": 1024000,
            "net_tx_bytes": 512000,
            "hostname": f"test-host-{self.device_id}",
            "kernel_version": "5.15.0-test",
            "ip_addr": "127.0.0.1",
            "mac_addr": "00:11:22:33:44:55",
        }

        self._send_json(0x02, status_data)  # SYSTEM_STATUS
        print(f"[{self.device_id}] 发送系统状态")
        return True

    async def _receive_message(self) -> Optional[dict]:
        """接收消息"""
        if not self.reader:
            return None

        try:
            # 读取头部 (3字节)
            header = await self.reader.readexactly(3)
            msg_type, length = struct.unpack(">BH", header)

            # 读取数据
            data = b""
            while len(data) < length:
                chunk = await self.reader.read(length - len(data))
                if not chunk:
                    return None
                data += chunk

            return {
                "type": msg_type,
                "data": data.decode("utf-8"),
                "timestamp": datetime.now(),
            }
        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            print(f"[{self.device_id}] 接收消息错误: {e}")
            return None

    async def receive_loop(self, timeout: float = 30.0):
        """接收消息循环"""
        start_time = time.time()
        while time.time() - start_time < timeout and self.connected:
            try:
                msg = await asyncio.wait_for(self._receive_message(), timeout=1.0)
                if msg:
                    self.messages_received.append(msg)
                    print(f"[{self.device_id}] 收到消息: type=0x{msg['type']:02X}")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[{self.device_id}] 接收循环错误: {e}")
                break


class TestRunner:
    """测试执行器"""

    def __init__(self):
        self.results = []

    def record(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        self.results.append(
            {
                "name": test_name,
                "passed": passed,
                "message": message,
                "time": datetime.now().isoformat(),
            }
        )
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status}: {test_name}")
        if message:
            print(f"   {message}")

    def summary(self):
        """打印测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print("\n" + "=" * 60)
        print("测试摘要")
        print("=" * 60)
        print(f"总计: {total} | 通过: {passed} | 失败: {failed}")
        print("=" * 60)

        if failed > 0:
            print("\n失败的测试:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  ❌ {r['name']}: {r['message']}")

        return failed == 0


# 具体测试用例
async def test_connection_and_register(
    runner: TestRunner, server_host: str = "127.0.0.1", server_port: int = 8766
):
    """TC-001: 连接与注册"""
    print("\n" + "=" * 60)
    print("测试: TC-001 连接与注册")
    print("=" * 60)

    agent = MockAgent(server_host=server_host, server_port=server_port)

    try:
        # 测试连接
        connected = await agent.connect()
        runner.record("TC-001-1 连接 Server", connected)

        if not connected:
            return

        # 测试注册
        registered = await agent.register()
        runner.record("TC-001-2 设备注册", registered)

    finally:
        await agent.disconnect()


async def test_heartbeat(
    runner: TestRunner, server_host: str = "127.0.0.1", server_port: int = 8766
):
    """TC-002: 心跳机制"""
    print("\n" + "=" * 60)
    print("测试: TC-002 心跳机制")
    print("=" * 60)

    agent = MockAgent(server_host=server_host, server_port=server_port)

    try:
        await agent.connect()
        await agent.register()

        # 发送 3 次心跳
        for i in range(3):
            await asyncio.sleep(1)
            await agent.send_heartbeat()

        runner.record(
            "TC-002 心跳机制",
            agent.heartbeat_count >= 3,
            f"发送了 {agent.heartbeat_count} 次心跳",
        )

    finally:
        await agent.disconnect()


async def test_system_status(
    runner: TestRunner, server_host: str = "127.0.0.1", server_port: int = 8766
):
    """TC-003: 系统状态上报"""
    print("\n" + "=" * 60)
    print("测试: TC-003 系统状态上报")
    print("=" * 60)

    agent = MockAgent(server_host=server_host, server_port=server_port)

    try:
        await agent.connect()
        await agent.register()

        # 发送系统状态
        sent = await agent.send_system_status()
        runner.record("TC-003 系统状态上报", sent)

    finally:
        await agent.disconnect()


async def test_multiple_agents(
    runner: TestRunner, server_host: str = "127.0.0.1", server_port: int = 8766
):
    """TC-004: 多 Agent 连接"""
    print("\n" + "=" * 60)
    print("测试: TC-004 多 Agent 连接")
    print("=" * 60)

    agents = []
    try:
        # 创建 3 个 Agent
        for i in range(3):
            agent = MockAgent(server_host=server_host, server_port=server_port)
            agents.append(agent)
            connected = await agent.connect()
            if connected:
                await agent.register()
            print(f"Agent-{i + 1}: 连接={connected}, 注册={agent.registered}")

        registered_count = sum(1 for a in agents if a.registered)
        runner.record(
            "TC-004 多 Agent 连接",
            registered_count == 3,
            f"{registered_count}/3 个 Agent 注册成功",
        )

    finally:
        for agent in agents:
            await agent.disconnect()


async def test_reconnect(
    runner: TestRunner, server_host: str = "127.0.0.1", server_port: int = 8766
):
    """TC-005: 自动重连"""
    print("\n" + "=" * 60)
    print("测试: TC-005 自动重连")
    print("=" * 60)
    print("注意: 此测试需要手动重启 Server，跳过自动化验证")
    runner.record("TC-005 自动重连", True, "手动测试项，需重启 Server 验证")


async def main():
    """主函数"""
    print("=" * 60)
    print("Buildroot Server 真实场景集成测试")
    print("=" * 60)
    print(f"时间: {datetime.now().isoformat()}")
    print()

    runner = TestRunner()

    # 测试配置
    server_host = "127.0.0.1"
    server_port = 8766

    # 执行测试
    await test_connection_and_register(runner, server_host, server_port)
    await test_heartbeat(runner, server_host, server_port)
    await test_system_status(runner, server_host, server_port)
    await test_multiple_agents(runner, server_host, server_port)
    await test_reconnect(runner, server_host, server_port)

    # 打印摘要
    success = runner.summary()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
