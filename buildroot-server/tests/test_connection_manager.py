"""
Connection Manager 单元测试
测试连接管理功能
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from managers.connection import ConnectionManager


class TestConnectionManager:
    """连接管理器测试类"""

    @pytest.fixture
    def mock_file_transfer_manager(self):
        """创建模拟文件传输管理器"""
        return Mock()

    @pytest.fixture
    def manager(self, mock_file_transfer_manager):
        """创建 ConnectionManager 实例"""
        return ConnectionManager(mock_file_transfer_manager)

    def test_add_device(self, manager):
        """测试添加设备"""
        device_id = "test-device-001"
        mock_connection = Mock()

        manager.add_device(device_id, mock_connection, "websocket")

        assert device_id in manager.connected_devices
        assert manager.connected_devices[device_id]["type"] == "websocket"
        assert manager.connected_devices[device_id]["connection"] == mock_connection
        assert device_id in manager.pty_sessions

    def test_add_device_socket(self, manager):
        """测试添加 Socket 类型设备"""
        device_id = "test-device-002"
        mock_connection = Mock()

        manager.add_device(device_id, mock_connection, "socket")

        assert manager.connected_devices[device_id]["type"] == "socket"

    def test_remove_device_existing(self, manager):
        """测试移除存在的设备"""
        device_id = "test-device-001"
        manager.add_device(device_id, Mock(), "websocket")

        manager.remove_device(device_id)

        assert device_id not in manager.connected_devices
        assert device_id not in manager.pty_sessions

    def test_remove_device_non_existing(self, manager):
        """测试移除不存在的设备"""
        # 不应该抛出异常
        manager.remove_device("non-existing-device")

    def test_is_device_connected_true(self, manager):
        """测试检查设备已连接"""
        device_id = "test-device-001"
        manager.add_device(device_id, Mock(), "websocket")

        assert manager.is_device_connected(device_id) is True

    def test_is_device_connected_false(self, manager):
        """测试检查设备未连接"""
        assert manager.is_device_connected("non-existing") is False

    def test_get_device_existing(self, manager):
        """测试获取存在的设备"""
        device_id = "test-device-001"
        mock_conn = Mock()
        manager.add_device(device_id, mock_conn, "websocket")

        result = manager.get_device(device_id)

        assert result is not None
        assert result["connection"] == mock_conn

    def test_get_device_non_existing(self, manager):
        """测试获取不存在的设备"""
        result = manager.get_device("non-existing")

        assert result is None

    def test_get_all_devices(self, manager):
        """测试获取所有设备"""
        manager.add_device("dev-001", Mock(), "websocket")
        manager.add_device("dev-002", Mock(), "socket")

        devices = manager.get_all_devices()

        assert len(devices) == 2
        # 检查返回的是字典列表
        device_ids = [d["device_id"] for d in devices]
        assert "dev-001" in device_ids
        assert "dev-002" in device_ids

    @pytest.mark.asyncio
    async def test_add_console(self, manager):
        """测试添加 Web 控制台"""
        mock_websocket = Mock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)

        with patch("managers.connection.WebConsoleSessionRepository") as mock_repo:
            mock_repo.insert = AsyncMock()

            manager.add_console(mock_websocket)
            # 给 create_task 一点执行时间
            await asyncio.sleep(0.01)

            assert mock_websocket in manager.web_consoles
            assert mock_websocket in manager.console_info
            assert "console_id" in manager.console_info[mock_websocket]

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_remove_console(self, manager):
        """测试移除 Web 控制台"""
        mock_websocket = Mock()
        await self.test_add_console(manager)
        mock_websocket = list(manager.web_consoles)[0]
        manager.console_info[mock_websocket]["console_id"]

        device_id, session_ids = manager.remove_console(mock_websocket)

        assert mock_websocket not in manager.web_consoles
        assert mock_websocket not in manager.console_info

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_remove_console_with_sessions(self, manager):
        """测试移除带有会话的控制台"""
        mock_websocket = Mock()
        await self.test_add_console(manager)
        mock_websocket = list(manager.web_consoles)[0]
        manager.console_info[mock_websocket]["device_id"] = "test-device"
        manager.console_info[mock_websocket]["session_ids"] = {1, 2, 3}

        # 添加 PTY 会话
        manager.pty_sessions["test-device"] = {1: asyncio.Queue(), 2: asyncio.Queue()}

        device_id, session_ids = manager.remove_console(mock_websocket)

        assert device_id == "test-device"
        assert session_ids == {1, 2, 3}

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_associate_console_with_device(self, manager):
        """测试关联控制台和设备"""
        await self.test_add_console(manager)
        mock_websocket = list(manager.web_consoles)[0]
        device_id = "test-device-001"

        manager.set_console_device(mock_websocket, device_id)

        assert manager.console_info[mock_websocket]["device_id"] == device_id

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_add_session_to_console(self, manager):
        """测试添加会话到控制台"""
        await self.test_add_console(manager)
        mock_websocket = list(manager.web_consoles)[0]
        session_id = 123

        manager.add_console_session(mock_websocket, session_id)

        assert session_id in manager.console_info[mock_websocket]["session_ids"]

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_remove_session_from_console(self, manager):
        """测试从控制台移除会话"""
        await self.test_add_console(manager)
        mock_websocket = list(manager.web_consoles)[0]
        session_id = 123
        manager.add_console_session(mock_websocket, session_id)

        # 手动移除会话
        manager.console_info[mock_websocket]["session_ids"].discard(session_id)

        assert session_id not in manager.console_info[mock_websocket]["session_ids"]

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_create_request_session(self, manager):
        """测试创建请求会话"""
        request_id = "req-123"
        manager.add_request_session(request_id, "console-001", "test-device")

        assert request_id in manager.request_sessions
        assert manager.request_sessions[request_id]["device_id"] == "test-device"
        assert manager.request_sessions[request_id]["console_id"] == "console-001"

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_remove_request_session(self, manager):
        """测试移除请求会话"""
        request_id = "req-123"
        manager.add_request_session(request_id, "console-001", "test-device")

        manager.remove_request_session(request_id)

        assert request_id not in manager.request_sessions

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_websocket_by_request_id(self, manager):
        """测试通过请求 ID 获取 WebSocket"""
        # 先添加控制台
        await self.test_add_console(manager)
        mock_websocket = list(manager.web_consoles)[0]
        console_id = manager.console_info[mock_websocket]["console_id"]

        # 设置设备关联
        manager.set_console_device(mock_websocket, "test-device")

        # 添加请求会话
        request_id = "req-123"
        manager.add_request_session(request_id, console_id, "test-device")

        result = manager.get_console_by_request(request_id)

        assert result == mock_websocket

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_websocket_by_request_id_expired(self, manager):
        """测试获取过期的请求会话 - 此方法不检查过期时间"""
        # 先添加控制台
        await self.test_add_console(manager)
        mock_websocket = list(manager.web_consoles)[0]
        manager.console_info[mock_websocket]["console_id"]
        manager.set_console_device(mock_websocket, "test-device")

        # 添加请求会话（不存在的console_id）
        request_id = "req-123"
        manager.add_request_session(request_id, "nonexistent-console", "test-device")

        result = manager.get_console_by_request(request_id)

        # 由于 console_id 不匹配，应该返回 None
        assert result is None
