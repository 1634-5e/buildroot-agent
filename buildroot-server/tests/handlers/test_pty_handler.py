"""
PtyHandler 单元测试
测试 PTY 会话的创建、数据传输、调整大小、关闭
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from handlers.pty_handler import PtyHandler
from protocol.constants import MessageType


@pytest.mark.asyncio
class TestPtyHandler:
    """PTY 处理器测试类"""

    @pytest.fixture
    def mock_conn_mgr(self):
        """创建模拟连接管理器"""
        mock = Mock()
        mock.pty_sessions = {}
        mock.web_consoles = set()
        mock.get_console_by_session = Mock(return_value=None)
        mock.get_console_info = Mock(return_value=None)
        mock.remove_console = AsyncMock()
        return mock

    @pytest.fixture
    def mock_websocket(self):
        """创建模拟 WebSocket"""
        ws = Mock()
        ws.send = AsyncMock()
        ws.state = Mock()
        ws.state.name = "OPEN"
        return ws

    @pytest.fixture
    def handler(self, mock_conn_mgr):
        """创建 PtyHandler 实例"""
        return PtyHandler(mock_conn_mgr)

    @pytest.fixture
    def handler_with_console(self, mock_conn_mgr, mock_websocket):
        """创建带有 web console 的 PtyHandler 实例"""
        mock_conn_mgr.web_consoles.add(mock_websocket)
        mock_conn_mgr.get_console_by_session = Mock(return_value=mock_websocket)
        mock_conn_mgr.get_console_info = Mock(
            return_value={"console_id": "console-123", "device_id": "test-device-001"}
        )
        return PtyHandler(mock_conn_mgr), mock_websocket

    # ==================== PTY CREATE ====================

    async def test_handle_pty_create_success(self, handler_with_console):
        """测试 PTY 会话创建成功"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        data = {
            "session_id": 1,
            "status": "created",
            "rows": 30,
            "cols": 120,
        }

        with patch(
            "handlers.pty_handler.PtySessionRepository.insert",
            new_callable=AsyncMock,
            return_value={"id": 1},
        ) as mock_insert, patch(
            "handlers.pty_handler.AuditLogRepository.insert",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_audit:
            await handler.handle_pty_create(device_id, data)

        # 验证 pty_sessions 中创建了队列
        assert device_id in handler.conn_mgr.pty_sessions
        assert 1 in handler.conn_mgr.pty_sessions[device_id]
        assert isinstance(handler.conn_mgr.pty_sessions[device_id][1], asyncio.Queue)

        # 验证广播消息到 web console
        mock_ws.send.assert_called_once()
        call_args = mock_ws.send.call_args[0][0]
        assert call_args[0] == MessageType.PTY_CREATE

        # 验证数据库操作
        mock_insert.assert_called_once()
        mock_audit.assert_called_once()

    async def test_handle_pty_create_no_console(self, handler):
        """测试 PTY 创建但无对应 console（console 可能已断开）"""
        device_id = "test-device-001"
        data = {
            "session_id": 1,
            "status": "created",
            "rows": 24,
            "cols": 80,
        }

        await handler.handle_pty_create(device_id, data)

        # 应该仍然创建 pty_sessions 条目
        assert device_id in handler.conn_mgr.pty_sessions
        assert 1 in handler.conn_mgr.pty_sessions[device_id]

    async def test_handle_pty_create_multiple_sessions(self, handler_with_console):
        """测试同一设备创建多个 PTY 会话"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"

        with patch(
            "handlers.pty_handler.PtySessionRepository.insert",
            new_callable=AsyncMock,
            return_value={"id": 1},
        ), patch(
            "handlers.pty_handler.AuditLogRepository.insert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # 创建第一个会话
            await handler.handle_pty_create(device_id, {"session_id": 1})
            # 创建第二个会话
            await handler.handle_pty_create(device_id, {"session_id": 2})

        # 验证两个会话都存在
        assert 1 in handler.conn_mgr.pty_sessions[device_id]
        assert 2 in handler.conn_mgr.pty_sessions[device_id]

    async def test_handle_pty_create_db_failure(self, handler_with_console):
        """测试 PTY 创建时数据库操作失败"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        data = {"session_id": 1, "status": "created"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.insert",
            new_callable=AsyncMock,
            side_effect=Exception("DB Error"),
        ):
            # 不应该抛出异常
            await handler.handle_pty_create(device_id, data)

        # pty_sessions 仍然应该创建
        assert device_id in handler.conn_mgr.pty_sessions

    # ==================== PTY DATA ====================

    async def test_handle_pty_data_success(self, handler_with_console):
        """测试 PTY 数据传输成功"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        data = {"session_id": 1, "data": "Hello, PTY!"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_bytes_received",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update:
            await handler.handle_pty_data(device_id, data)

        # 验证广播消息
        mock_ws.send.assert_called_once()
        call_args = mock_ws.send.call_args[0][0]
        assert call_args[0] == MessageType.PTY_DATA

        # 验证更新字节计数
        mock_update.assert_called_once_with(
            device_id=device_id, session_id=1, bytes_received=len("Hello, PTY!")
        )

    async def test_handle_pty_data_no_console(self, handler):
        """测试 PTY 数据无对应 console"""
        device_id = "test-device-001"
        data = {"session_id": 1, "data": "test data"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_bytes_received",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # 不应该抛出异常
            await handler.handle_pty_data(device_id, data)

    async def test_handle_pty_data_empty(self, handler_with_console):
        """测试空 PTY 数据"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        data = {"session_id": 1, "data": ""}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_bytes_received",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update:
            await handler.handle_pty_data(device_id, data)

        # 仍然应该调用更新，但 bytes_received=0
        mock_update.assert_called_once_with(
            device_id=device_id, session_id=1, bytes_received=0
        )

    async def test_handle_pty_data_db_failure(self, handler_with_console):
        """测试 PTY 数据更新数据库失败"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        data = {"session_id": 1, "data": "test"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_bytes_received",
            new_callable=AsyncMock,
            side_effect=Exception("DB Error"),
        ):
            # 不应该抛出异常
            await handler.handle_pty_data(device_id, data)

        # 消息仍然应该发送
        mock_ws.send.assert_called_once()

    # ==================== PTY RESIZE ====================

    async def test_handle_pty_resize_success(self, handler_with_console):
        """测试 PTY 调整大小成功"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        data = {"session_id": 1, "rows": 40, "cols": 160}

        await handler.handle_pty_resize(device_id, data)

        # 验证广播消息
        mock_ws.send.assert_called_once()
        call_args = mock_ws.send.call_args[0][0]
        assert call_args[0] == MessageType.PTY_RESIZE

    async def test_handle_pty_resize_no_console(self, handler):
        """测试 PTY resize 无对应 console"""
        device_id = "test-device-001"
        data = {"session_id": 1, "rows": 40, "cols": 160}

        # 不应该抛出异常
        await handler.handle_pty_resize(device_id, data)

    async def test_handle_pty_resize_default_size(self, handler_with_console):
        """测试 PTY resize 使用默认大小"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        data = {"session_id": 1}  # 不传 rows/cols

        await handler.handle_pty_resize(device_id, data)

        mock_ws.send.assert_called_once()

    # ==================== PTY CLOSE ====================

    async def test_handle_pty_close_success(self, handler_with_console):
        """测试 PTY 会话关闭成功"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"

        # 先创建一个会话
        handler.conn_mgr.pty_sessions[device_id] = {1: asyncio.Queue()}

        data = {"session_id": 1, "reason": "user_closed"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_closed",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update, patch(
            "handlers.pty_handler.AuditLogRepository.insert",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_audit:
            await handler.handle_pty_close(device_id, data)

        # 验证 pty_sessions 中移除了会话
        assert 1 not in handler.conn_mgr.pty_sessions[device_id]

        # 验证广播消息
        mock_ws.send.assert_called_once()
        call_args = mock_ws.send.call_args[0][0]
        assert call_args[0] == MessageType.PTY_CLOSE

        # 验证数据库操作
        mock_update.assert_called_once()
        mock_audit.assert_called_once()

    async def test_handle_pty_close_no_console(self, handler):
        """测试 PTY 关闭无对应 console"""
        device_id = "test-device-001"
        handler.conn_mgr.pty_sessions[device_id] = {1: asyncio.Queue()}
        data = {"session_id": 1, "reason": "disconnect"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_closed",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await handler.handle_pty_close(device_id, data)

        # 应该仍然清理 pty_sessions
        assert 1 not in handler.conn_mgr.pty_sessions[device_id]

    async def test_handle_pty_close_session_not_exist(self, handler):
        """测试关闭不存在的 PTY 会话"""
        device_id = "test-device-001"
        data = {"session_id": 999, "reason": "unknown"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_closed",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # 不应该抛出异常
            await handler.handle_pty_close(device_id, data)

    async def test_handle_pty_close_db_failure(self, handler_with_console):
        """测试 PTY 关闭时数据库操作失败"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        handler.conn_mgr.pty_sessions[device_id] = {1: asyncio.Queue()}
        data = {"session_id": 1, "reason": "error"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_closed",
            new_callable=AsyncMock,
            side_effect=Exception("DB Error"),
        ):
            # 不应该抛出异常
            await handler.handle_pty_close(device_id, data)

        # pty_sessions 仍然应该清理
        assert 1 not in handler.conn_mgr.pty_sessions[device_id]

    async def test_handle_pty_close_device_not_in_sessions(self, handler):
        """测试关闭 PTY 时设备不在 pty_sessions 中"""
        device_id = "new-device"
        data = {"session_id": 1, "reason": "cleanup"}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_closed",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # 不应该抛出异常
            await handler.handle_pty_close(device_id, data)

    # ==================== 边界情况 ====================

    async def test_handle_pty_data_large_payload(self, handler_with_console):
        """测试大 PTY 数据包"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        large_data = "x" * 10000  # 10KB 数据
        data = {"session_id": 1, "data": large_data}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_bytes_received",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update:
            await handler.handle_pty_data(device_id, data)

        mock_update.assert_called_once_with(
            device_id=device_id, session_id=1, bytes_received=10000
        )

    async def test_handle_pty_create_with_unicode(self, handler_with_console):
        """测试 PTY 数据包含 Unicode 字符（字节计数正确）"""
        handler, mock_ws = handler_with_console
        device_id = "test-device-001"
        unicode_data = "你好，世界！🌍"
        data = {"session_id": 1, "data": unicode_data}

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_bytes_received",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update:
            await handler.handle_pty_data(device_id, data)

        # bytes_received 应该是 UTF-8 字节长度（22），不是字符数（7）
        expected_bytes = len(unicode_data.encode("utf-8"))
        mock_update.assert_called_once_with(
            device_id=device_id, session_id=1, bytes_received=expected_bytes
        )

    async def test_handle_pty_close_multiple_sessions_same_device(self, handler):
        """测试同一设备关闭多个 PTY 会话"""
        device_id = "test-device-001"
        handler.conn_mgr.pty_sessions[device_id] = {
            1: asyncio.Queue(),
            2: asyncio.Queue(),
            3: asyncio.Queue(),
        }

        with patch(
            "handlers.pty_handler.PtySessionRepository.update_closed",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # 关闭会话 1
            await handler.handle_pty_close(device_id, {"session_id": 1})
            assert 1 not in handler.conn_mgr.pty_sessions[device_id]
            assert 2 in handler.conn_mgr.pty_sessions[device_id]
            assert 3 in handler.conn_mgr.pty_sessions[device_id]

            # 关闭会话 2
            await handler.handle_pty_close(device_id, {"session_id": 2})
            assert 2 not in handler.conn_mgr.pty_sessions[device_id]
            assert 3 in handler.conn_mgr.pty_sessions[device_id]