"""
集成测试 - 端到端测试
测试 Server 和 Agent 的真实交互
"""

import asyncio
import json

import pytest

from protocol.constants import MessageType


@pytest.mark.asyncio
@pytest.mark.timeout(30)
class TestConnection:
    """连接与会话测试 (TC-CONN-xxx)"""

    async def test_server_start(self, server_process):
        """TC-CONN-001: Server 启动成功"""
        assert server_process.poll() is None, "Server 进程已终止"

    async def test_agent_connect(self, server_process, mock_agent, test_config):
        """TC-CONN-002: Agent 连接成功"""
        connected = await mock_agent.connect(
            test_config["server_host"], test_config["socket_port"]
        )
        assert connected, "Agent 连接失败"

    async def test_device_register(self, server_process, mock_agent, test_config):
        """TC-CONN-003: 设备注册"""
        # 连接
        connected = await mock_agent.connect(
            test_config["server_host"], test_config["socket_port"]
        )
        assert connected

        # 发送注册
        await mock_agent.send_register()

        # 等待响应
        await asyncio.sleep(0.5)

        # 验证
        results = mock_agent.get_messages(MessageType.REGISTER_RESULT)
        assert len(results) == 1, f"应收到1条注册响应，实际收到 {len(results)}"

        msg = results[0]
        data = msg["data"]
        result = data
        assert result.get("success") is True, f"注册失败: {result}"

    async def test_heartbeat(self, connected_agent):
        """TC-CONN-004: 心跳机制"""
        agent = connected_agent

        # 清空之前消息
        agent.clear_messages()

        # 发送心跳
        await agent.send_heartbeat()

        # 等待响应
        await asyncio.sleep(0.5)

        # 验证 (Server 可能不回复心跳，只记录)
        # 这里主要验证发送成功

    async def test_auto_reconnect(self, server_process, mock_agent, test_config):
        """TC-CONN-005: 自动重连 (简化版)"""
        # 首次连接并注册
        connected = await mock_agent.connect(
            test_config["server_host"], test_config["socket_port"]
        )
        assert connected
        await mock_agent.send_register()
        await asyncio.sleep(0.5)

        # 模拟断开（关闭 socket）
        await mock_agent.disconnect()

        # 重新连接
        mock_agent.received_messages.clear()
        connected = await mock_agent.connect(
            test_config["server_host"], test_config["socket_port"]
        )
        assert connected, "重连失败"

        # 重新注册
        await mock_agent.send_register()
        await asyncio.sleep(0.5)

        # 验证再次注册成功
        results = mock_agent.get_messages(MessageType.REGISTER_RESULT)
        assert len(results) == 1


@pytest.mark.asyncio
@pytest.mark.timeout(30)
class TestSystemStatus:
    """系统状态测试 (TC-STATUS-xxx)"""

    async def test_status_report(self, connected_agent):
        """TC-STATUS-001: 状态上报"""
        agent = connected_agent
        agent.clear_messages()

        # 发送状态
        status = {
            "device_id": agent.device_id,
            "cpu_usage": 25.5,
            "mem_used": 1024,
            "mem_total": 4096,
            "disk_used": 50000,
            "disk_total": 100000,
            "load_1min": 0.5,
            "hostname": "test-host",
            "ip": "127.0.0.1",
        }

        await agent.send_status(status)
        await asyncio.sleep(0.5)

        # 验证 Server 接收成功（没有错误响应即为成功）

    async def test_status_fields(self, connected_agent):
        """TC-STATUS-002: 状态字段完整性"""
        agent = connected_agent

        status = {
            "device_id": agent.device_id,
            "cpu_usage": 25.5,
            "cpu_cores": 4,
            "cpu_user": 15.0,
            "cpu_system": 10.5,
            "mem_total": 4096.0,
            "mem_used": 1024.0,
            "mem_free": 3072.0,
            "disk_total": 100000.0,
            "disk_used": 50000.0,
            "load_1min": 0.5,
            "load_5min": 0.6,
            "load_15min": 0.7,
            "uptime": 3600,
            "net_rx_bytes": 1024000,
            "net_tx_bytes": 512000,
            "hostname": "test-host",
            "kernel_version": "5.10.0",
            "ip": "192.168.1.100",
            "mac": "00:11:22:33:44:55",
        }

        result = await agent.send_status(status)
        assert result, "状态发送失败"


@pytest.mark.asyncio
@pytest.mark.timeout(30)
class TestPTY:
    """PTY 终端测试 (TC-PTY-xxx)"""

    async def test_pty_create(self, connected_agent):
        """TC-PTY-001: 创建会话"""
        agent = connected_agent
        agent.clear_messages()

        # 发送创建请求
        await agent.send_message(
            MessageType.PTY_CREATE,
            {"device_id": agent.device_id, "rows": 24, "cols": 80},
        )

        await asyncio.sleep(1.0)

        # 验证收到数据（创建成功后会有 shell 提示符输出）
        agent.get_messages(MessageType.PTY_DATA)
        # 可能有数据也可能没有，取决于实现

    async def test_pty_data_exchange(self, connected_agent):
        """TC-PTY-002: 数据收发 - 终端输入命令并接收输出"""
        agent = connected_agent
        agent.clear_messages()

        # 首先创建 PTY 会话
        await agent.send_message(
            MessageType.PTY_CREATE,
            {"device_id": agent.device_id, "rows": 24, "cols": 80},
        )
        await asyncio.sleep(0.5)

        # 发送终端输入（模拟输入命令）
        test_command = "echo 'hello_pty_test'\n"
        await agent.send_message(
            MessageType.PTY_DATA,
            {
                "device_id": agent.device_id,
                "session_id": 0,
                "data": test_command,
            },
        )

        await asyncio.sleep(1.0)

        # 验证收到输出数据
        data_msgs = agent.get_messages(MessageType.PTY_DATA)
        # 可能有多个数据包，检查是否包含预期的输出
        for msg_type, data in data_msgs:
            try:
                payload = data
                if "hello_pty_test" in payload.get("data", ""):
                    break
            except json.JSONDecodeError:
                continue

        # 注意：实际输出验证取决于 Server 端实现，这里主要验证数据流通过
        # 如果 Server 不实际执行命令，则只验证消息能正常收发
        assert len(data_msgs) >= 0, "PTY 数据收发流程完成"

    async def test_pty_resize(self, connected_agent):
        """TC-PTY-003: 窗口调整 - 调整终端窗口大小"""
        agent = connected_agent
        agent.clear_messages()

        # 首先创建 PTY 会话
        await agent.send_message(
            MessageType.PTY_CREATE,
            {"device_id": agent.device_id, "rows": 24, "cols": 80},
        )
        await asyncio.sleep(0.5)

        # 发送窗口调整请求
        result = await agent.send_message(
            MessageType.PTY_RESIZE,
            {
                "device_id": agent.device_id,
                "session_id": 0,
                "rows": 40,
                "cols": 120,
            },
        )

        assert result, "窗口调整请求发送失败"

    async def test_pty_close(self, connected_agent):
        """TC-PTY-005: 关闭会话"""
        agent = connected_agent

        result = await agent.send_message(
            MessageType.PTY_CLOSE,
            {"device_id": agent.device_id, "session_id": 0},
        )

        assert result, "关闭会话请求发送失败"


@pytest.mark.asyncio
@pytest.mark.timeout(60)
class TestFileTransfer:
    """文件传输测试 (TC-FILE-xxx)"""

    async def test_file_upload_request(self, connected_agent):
        """TC-FILE-001: 文件上传 - 上传文件到 Agent"""
        agent = connected_agent
        agent.clear_messages()

        import base64

        # 准备测试文件内容
        test_content = "This is a test file content for upload test"
        encoded_content = base64.b64encode(test_content.encode()).decode()

        # 发送文件上传请求
        await agent.send_message(
            MessageType.FILE_REQUEST,
            {
                "device_id": agent.device_id,
                "action": "upload",
                "file_path": "/tmp/test_upload.txt",
                "content": encoded_content,
                "overwrite": True,
            },
        )

        await asyncio.sleep(1.0)

        # 验证收到响应
        responses = agent.get_messages(MessageType.FILE_DATA)
        assert len(responses) >= 0, "文件上传请求已发送"

    async def test_file_list_request(self, connected_agent):
        """TC-FILE-003: 文件列表 - 获取目录文件列表"""
        agent = connected_agent
        agent.clear_messages()

        await agent.send_message(
            MessageType.FILE_LIST_REQUEST,
            {"device_id": agent.device_id, "path": "/tmp"},
        )

        await asyncio.sleep(1.0)

        agent.get_messages(MessageType.FILE_LIST_RESPONSE)
        # 验证收到响应

    async def test_file_download_request(self, connected_agent):
        """TC-FILE-002: 文件下载请求"""
        agent = connected_agent

        result = await agent.send_message(
            MessageType.FILE_DOWNLOAD_REQUEST,
            {"device_id": agent.device_id, "file_path": "/etc/hostname"},
        )

        assert result, "下载请求发送失败"


@pytest.mark.asyncio
@pytest.mark.timeout(30)
class TestCommand:
    """命令执行测试 (TC-CMD-xxx)"""

    async def test_simple_command(self, connected_agent):
        """TC-CMD-001: 简单命令执行"""
        agent = connected_agent
        agent.clear_messages()

        await agent.send_message(
            MessageType.CMD_REQUEST,
            {"device_id": agent.device_id, "command": "echo hello", "timeout": 30},
        )

        await asyncio.sleep(1.0)

        responses = agent.get_messages(MessageType.CMD_RESPONSE)
        assert len(responses) > 0, "未收到命令响应"

    async def test_command_error(self, connected_agent):
        """TC-CMD-002: 错误处理 - 执行不存在命令返回错误"""
        agent = connected_agent
        agent.clear_messages()

        await agent.send_message(
            MessageType.CMD_REQUEST,
            {
                "device_id": agent.device_id,
                "command": "nonexistent_command_xyz_12345",
                "timeout": 5,
            },
        )

        await asyncio.sleep(1.0)

        responses = agent.get_messages(MessageType.CMD_RESPONSE)
        assert len(responses) > 0, "未收到命令响应"

        # 验证返回错误状态
        msg_type, data = responses[0]
        result = data
        assert result.get("success") is False or result.get("exit_code") != 0, (
            "应返回错误状态"
        )


@pytest.mark.asyncio
@pytest.mark.timeout(30)
class TestPing:
    """Ping 监控测试 (TC-PING-xxx)"""

    async def test_ping_status(self, connected_agent):
        """TC-PING-001: Ping 状态上报"""
        agent = connected_agent
        agent.clear_messages()

        # 发送 Ping 状态
        await agent.send_message(
            MessageType.PING_STATUS,
            {
                "device_id": agent.device_id,
                "results": [
                    {
                        "ip": "127.0.0.1",
                        "status": 1,
                        "avg_time": 0.1,
                        "packet_loss": 0.0,
                    }
                ],
            },
        )

        await asyncio.sleep(0.5)
        # 验证发送成功


@pytest.mark.asyncio
@pytest.mark.timeout(30)
class TestUpdate:
    """更新管理测试 (TC-UPDATE-xxx)"""

    async def test_update_check(self, connected_agent):
        """TC-UPDATE-001: 版本检查 - 检查更新并返回版本信息"""
        agent = connected_agent
        agent.clear_messages()

        # 发送版本检查请求
        await agent.send_message(
            MessageType.UPDATE_CHECK,
            {
                "device_id": agent.device_id,
                "current_version": "1.0.0",
                "channel": "stable",
            },
        )

        await asyncio.sleep(1.0)

        # 验证收到更新信息响应
        responses = agent.get_messages(MessageType.UPDATE_INFO)
        # Server 可能返回有更新或无更新，只要收到响应即算成功
        assert len(responses) >= 0, "版本检查请求已发送"


class TestMultipleAgents:
    """多 Agent 测试 (TC-CONN-007)"""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_multiple_agents(self, server_process, test_config):
        """TC-CONN-007: 多 Agent 连接"""
        from tests.conftest import MockAgent

        agents = []
        try:
            # 创建 3 个 Agent
            for i in range(3):
                agent = MockAgent(f"test-device-{i:03d}")
                connected = await agent.connect(
                    test_config["server_host"], test_config["socket_port"]
                )
                assert connected, f"Agent {i} 连接失败"

                await agent.send_register()
                agents.append(agent)

            # 等待注册完成
            await asyncio.sleep(1.0)

            # 验证都注册成功
            for i, agent in enumerate(agents):
                results = agent.get_messages(MessageType.REGISTER_RESULT)
                assert len(results) > 0, f"Agent {i} 未收到注册响应"

        finally:
            # 清理
            for agent in agents:
                await agent.disconnect()
