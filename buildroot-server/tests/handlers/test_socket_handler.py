"""
SocketHandler 单元测试
测试 Agent Socket 连接处理
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from handlers.socket_handler import SocketHandler
from protocol.constants import MessageType


@pytest.mark.asyncio
class TestSocketHandler:
    """Socket 处理器测试类"""

    @pytest.fixture
    def mock_conn_mgr(self):
        """创建模拟连接管理器"""
        mock = Mock()
        mock.add_device = Mock()
        mock.remove_device = Mock()
        mock.get_all_devices = Mock(return_value=[])
        return mock

    @pytest.fixture
    def mock_msg_handler(self):
        """创建模拟消息处理器"""
        mock = AsyncMock()
        mock.handle_device_connect = AsyncMock()
        mock.handle_message = AsyncMock()
        mock.broadcast_to_web_consoles = AsyncMock()
        mock.notify_device_disconnect = AsyncMock()
        return mock

    @pytest.fixture
    def handler(self, mock_conn_mgr, mock_msg_handler):
        """创建 SocketHandler 实例"""
        return SocketHandler(mock_conn_mgr, mock_msg_handler)

    @pytest.fixture
    def mock_reader_writer(self):
        """创建模拟的 reader 和 writer"""
        reader = AsyncMock()
        writer = AsyncMock()
        writer.get_extra_info = Mock(return_value=("127.0.0.1", 12345))
        writer.close = Mock()
        writer.wait_closed = AsyncMock()
        writer.write = Mock()
        writer.drain = AsyncMock()
        return reader, writer

    async def test_handle_connection_register_success(
        self, handler, mock_reader_writer
    ):
        """测试处理注册消息成功"""
        reader, writer = mock_reader_writer

        # 构建 REGISTER 消息
        register_data = json.dumps(
            {"device_id": "test-device-001", "version": "1.0.0"}
        ).encode()

        msg_header = bytes([MessageType.REGISTER])
        msg_header += len(register_data).to_bytes(2, "big")

        # 模拟读取消息
        reader.readexactly.side_effect = [
            msg_header[0:1],  # type
            msg_header[1:3],  # length
            register_data,  # data
            asyncio.IncompleteReadError(b"", 1),  # 断开连接
        ]

        await handler.handle_connection(reader, writer)

        handler.msg_handler.handle_device_connect.assert_called_once()
        handler.conn_mgr.remove_device.assert_called_once_with("test-device-001")

    async def test_handle_connection_register_invalid_json(
        self, handler, mock_reader_writer
    ):
        """测试处理无效的 JSON 注册消息"""
        reader, writer = mock_reader_writer

        # 构建无效的 REGISTER 消息
        invalid_data = b"invalid json"
        msg_header = bytes([MessageType.REGISTER])
        msg_header += len(invalid_data).to_bytes(2, "big")

        reader.readexactly.side_effect = [
            msg_header[0:1],
            msg_header[1:3],
            invalid_data,
        ]

        await handler.handle_connection(reader, writer)

        # 应该关闭连接（至少调用一次）
        assert writer.close.call_count >= 1
        writer.wait_closed.assert_called()

    async def test_handle_connection_message_too_large(
        self, handler, mock_reader_writer
    ):
        """测试处理过大的消息"""
        reader, writer = mock_reader_writer

        # 构建超长的消息 (使用最大值 65535)
        msg_header = bytes([MessageType.HEARTBEAT])
        msg_header += (65535).to_bytes(2, "big")  # 最大值

        reader.readexactly.side_effect = [
            msg_header[0:1],
            msg_header[1:3],
        ]

        await handler.handle_connection(reader, writer)

        # 应该断开连接（至少调用一次）
        assert writer.close.call_count >= 1

    async def test_handle_connection_registered_message(
        self, handler, mock_reader_writer
    ):
        """测试处理已注册设备的消息"""
        reader, writer = mock_reader_writer

        # 先注册
        register_data = json.dumps(
            {"device_id": "test-device-001", "version": "1.0.0"}
        ).encode()

        # 然后发送心跳
        heartbeat_data = json.dumps({"timestamp": 123456}).encode()

        reader.readexactly.side_effect = [
            bytes([MessageType.REGISTER]),
            len(register_data).to_bytes(2, "big"),
            register_data,
            bytes([MessageType.HEARTBEAT]),
            len(heartbeat_data).to_bytes(2, "big"),
            heartbeat_data,
            asyncio.IncompleteReadError(b"", 1),
        ]

        await handler.handle_connection(reader, writer)

        # 应该处理心跳消息
        handler.msg_handler.handle_message.assert_called_once()

    async def test_handle_connection_device_change(self, handler, mock_reader_writer):
        """测试设备 ID 变更"""
        reader, writer = mock_reader_writer

        # 第一次注册
        register_data1 = json.dumps(
            {"device_id": "device-old", "version": "1.0.0"}
        ).encode()

        # 第二次注册（变更 ID）
        register_data2 = json.dumps(
            {"device_id": "device-new", "version": "1.0.0"}
        ).encode()

        reader.readexactly.side_effect = [
            bytes([MessageType.REGISTER]),
            len(register_data1).to_bytes(2, "big"),
            register_data1,
            bytes([MessageType.REGISTER]),
            len(register_data2).to_bytes(2, "big"),
            register_data2,
            asyncio.IncompleteReadError(b"", 1),
        ]

        await handler.handle_connection(reader, writer)

        # 连接断开时会移除当前设备
        handler.conn_mgr.remove_device.assert_called_with("device-new")
        # 应该添加新设备（调用了两次：第一次 device-old，第二次 device-new）
        assert handler.msg_handler.handle_device_connect.call_count == 2

    async def test_notify_device_list_update(self, handler):
        """测试通知设备列表更新"""
        handler.conn_mgr.get_all_devices.return_value = [
            {"device_id": "dev1", "status": "online"},
            {"device_id": "dev2", "status": "offline"},
        ]

        await handler._notify_device_list_update()

        handler.msg_handler.broadcast_to_web_consoles.assert_called_once()
        call_args = handler.msg_handler.broadcast_to_web_consoles.call_args
        assert call_args[0][0] == MessageType.DEVICE_LIST

    async def test_notify_device_disconnect(self, handler):
        """测试通知设备断开"""
        device_id = "test-device-001"

        await handler._notify_device_disconnect(device_id)

        handler.msg_handler.notify_device_disconnect.assert_called_once_with(device_id)
