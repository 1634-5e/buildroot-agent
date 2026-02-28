"""
Handler 测试的共享 fixtures
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock


@pytest.fixture
def mock_conn_mgr():
    """模拟连接管理器"""
    conn_mgr = Mock()
    conn_mgr.add_device = Mock()
    conn_mgr.remove_device = Mock()
    conn_mgr.get_device = Mock(return_value=None)
    conn_mgr.is_device_connected = Mock(return_value=False)
    conn_mgr.get_all_devices = Mock(return_value=[])
    return conn_mgr


@pytest.fixture
def mock_websocket():
    """模拟 WebSocket 连接"""
    ws = Mock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    ws.state = Mock()
    ws.state.name = "OPEN"
    ws.remote_address = ("192.168.1.100", 12345)
    return ws


@pytest.fixture
def mock_socket_writer():
    """模拟 Socket StreamWriter"""
    writer = Mock()
    writer.write = Mock()
    writer.drain = AsyncMock()
    writer.close = Mock()
    writer.wait_closed = AsyncMock()
    writer.get_extra_info = Mock(return_value=("192.168.1.100", 12345))
    return writer


@pytest.fixture
def mock_socket_reader():
    """模拟 Socket StreamReader"""
    reader = Mock()
    reader.readexactly = AsyncMock()
    return reader


@pytest.fixture
def mock_db_repositories():
    """模拟数据库仓库"""
    repos = {
        "device": Mock(),
        "audit_log": Mock(),
        "status_history": Mock(),
        "script_history": Mock(),
    }
    repos["device"].create_or_update = AsyncMock()
    repos["device"].update_connection_status = AsyncMock()
    repos["device"].update_current_status = AsyncMock()
    repos["device"].update_device_info = AsyncMock()
    repos["device"].update_uptime_seconds = AsyncMock()
    repos["audit_log"].insert = AsyncMock()
    repos["script_history"].update_result = AsyncMock()
    return repos
