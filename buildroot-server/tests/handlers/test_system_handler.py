"""
SystemHandler 单元测试
测试系统消息处理（心跳、状态、日志、脚本）
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from handlers.system_handler import SystemHandler
from protocol.constants import MessageType


@pytest.mark.asyncio
class TestSystemHandler:
    """系统处理器测试类"""

    @pytest.fixture
    def mock_conn_mgr(self):
        """创建模拟连接管理器"""
        mock = Mock()
        mock.is_device_connected = Mock(return_value=True)
        mock.get_device = Mock(
            return_value={"connection": AsyncMock(), "type": "websocket"}
        )
        return mock

    @pytest.fixture
    def handler(self, mock_conn_mgr):
        """创建 SystemHandler 实例"""
        return SystemHandler(mock_conn_mgr)

    async def test_handle_heartbeat_success(self, handler):
        """测试处理心跳消息成功"""
        device_id = "test-device-001"
        data = {"timestamp": 1234567890}

        with patch("handlers.system_handler.DeviceRepository") as mock_repo:
            mock_repo.update_connection_status = AsyncMock()

            await handler.handle_heartbeat(device_id, data)

            mock_repo.update_connection_status.assert_called_once()
            call_kwargs = mock_repo.update_connection_status.call_args[1]
            assert call_kwargs["device_id"] == device_id
            assert call_kwargs["status"] == "online"
            assert call_kwargs["is_online"] is True

    async def test_handle_heartbeat_db_failure(self, handler):
        """测试处理心跳时数据库失败"""
        device_id = "test-device-001"
        data = {"timestamp": 1234567890}

        with patch("handlers.system_handler.DeviceRepository") as mock_repo:
            mock_repo.update_connection_status = AsyncMock(
                side_effect=Exception("DB Error")
            )

            # 不应该抛出异常
            await handler.handle_heartbeat(device_id, data)

    async def test_handle_system_status_success(self, handler):
        """测试处理系统状态消息成功"""
        device_id = "test-device-001"
        data = {
            "cpu_usage": 45.5,
            "cpu_cores": 4,
            "cpu_user": 30.0,
            "cpu_system": 15.5,
            "mem_total": 8192.0,
            "mem_used": 4096.0,
            "mem_free": 4096.0,
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
            "ip_addr": "192.168.1.100",
            "mac_addr": "00:11:22:33:44:55",
        }

        with (
            patch("handlers.system_handler.DeviceRepository") as mock_repo,
            patch(
                "handlers.system_handler.get_status_history_buffer"
            ) as mock_status_buffer,
            patch("handlers.system_handler.get_audit_log_buffer") as mock_audit_buffer,
        ):
            mock_repo.update_current_status = AsyncMock()
            mock_repo.update_device_info = AsyncMock()
            mock_repo.update_uptime_seconds = AsyncMock()

            mock_buffer = MagicMock()
            mock_buffer.add_status = AsyncMock()
            mock_buffer.add_log = AsyncMock()
            mock_status_buffer.return_value = mock_buffer
            mock_audit_buffer.return_value = mock_buffer

            await handler.handle_system_status(device_id, data)

            mock_repo.update_current_status.assert_called_once()
            mock_repo.update_device_info.assert_called_once()
            mock_repo.update_uptime_seconds.assert_called_once()

    async def test_handle_system_status_with_request_id(self, handler):
        """测试带 request_id 的系统状态消息"""
        device_id = "test-device-001"
        request_id = "req-12345"
        data = {
            "cpu_usage": 45.5,
            "request_id": request_id,
        }

        with (
            patch("handlers.system_handler.DeviceRepository") as mock_repo,
            patch(
                "handlers.system_handler.get_status_history_buffer"
            ) as mock_status_buffer,
            patch("handlers.system_handler.get_audit_log_buffer") as mock_audit_buffer,
            patch.object(
                handler, "unicast_by_request_id", new_callable=AsyncMock
            ) as mock_unicast,
        ):
            mock_repo.update_current_status = AsyncMock()
            mock_repo.update_device_info = AsyncMock()
            mock_repo.update_uptime_seconds = AsyncMock()

            mock_buffer = MagicMock()
            mock_buffer.add_status = AsyncMock()
            mock_buffer.add_log = AsyncMock()
            mock_status_buffer.return_value = mock_buffer
            mock_audit_buffer.return_value = mock_buffer

            await handler.handle_system_status(device_id, data)

            mock_unicast.assert_called_once()

    async def test_handle_log_upload_chunk(self, handler):
        """测试处理日志分片上传"""
        device_id = "test-device-001"
        data = {
            "filepath": "/var/log/test.log",
            "chunk": 0,
            "total_chunks": 5,
        }

        with patch("handlers.system_handler.get_audit_log_buffer") as mock_audit_buffer:
            mock_buffer = MagicMock()
            mock_buffer.add_log = AsyncMock()
            mock_audit_buffer.return_value = mock_buffer

            await handler.handle_log_upload(device_id, data)

            mock_buffer.add_log.assert_called_once()

    async def test_handle_log_upload_lines(self, handler):
        """测试处理完整日志上传"""
        device_id = "test-device-001"
        data = {
            "filepath": "/var/log/test.log",
            "lines": 100,
        }

        with patch("handlers.system_handler.get_audit_log_buffer") as mock_audit_buffer:
            mock_buffer = MagicMock()
            mock_buffer.add_log = AsyncMock()
            mock_audit_buffer.return_value = mock_buffer

            await handler.handle_log_upload(device_id, data)

            mock_buffer.add_log.assert_called_once()
            call_kwargs = mock_buffer.add_log.call_args[1]
            assert call_kwargs["details"]["lines"] == 100

    async def test_handle_script_result_success(self, handler):
        """测试处理脚本执行成功结果"""
        device_id = "test-device-001"
        script_id = "script-001"
        request_id = "req-12345"
        data = {
            "script_id": script_id,
            "request_id": request_id,
            "exit_code": 0,
            "success": True,
            "output": "Script output",
            "error": "",
        }

        with (
            patch(
                "handlers.system_handler.ScriptHistoryRepository"
            ) as mock_script_repo,
            patch("handlers.system_handler.get_audit_log_buffer") as mock_audit_buffer,
        ):
            mock_script_repo.update_result = AsyncMock()
            mock_buffer = MagicMock()
            mock_buffer.add_log = AsyncMock()
            mock_audit_buffer.return_value = mock_buffer

            await handler.handle_script_result(device_id, data)

            mock_script_repo.update_result.assert_called_once()
            call_kwargs = mock_script_repo.update_result.call_args[1]
            assert call_kwargs["status"] == "completed"
            assert call_kwargs["success"] is True
            assert call_kwargs["exit_code"] == 0

    async def test_handle_script_result_failure(self, handler):
        """测试处理脚本执行失败结果"""
        device_id = "test-device-001"
        script_id = "script-001"
        request_id = "req-12345"
        data = {
            "script_id": script_id,
            "request_id": request_id,
            "exit_code": 1,
            "success": False,
            "output": "",
            "error": "Error message",
        }

        with (
            patch(
                "handlers.system_handler.ScriptHistoryRepository"
            ) as mock_script_repo,
            patch("handlers.system_handler.get_audit_log_buffer") as mock_audit_buffer,
        ):
            mock_script_repo.update_result = AsyncMock()
            mock_buffer = MagicMock()
            mock_buffer.add_log = AsyncMock()
            mock_audit_buffer.return_value = mock_buffer

            await handler.handle_script_result(device_id, data)

            mock_script_repo.update_result.assert_called_once()
            call_kwargs = mock_script_repo.update_result.call_args[1]
            assert call_kwargs["status"] == "failed"
            assert call_kwargs["success"] is False

    async def test_handle_script_result_no_request_id(self, handler):
        """测试无 request_id 的脚本结果"""
        device_id = "test-device-001"
        data = {
            "script_id": "script-001",
            "exit_code": 0,
            "success": True,
            "output": "Output",
            "error": "",
        }

        with (
            patch(
                "handlers.system_handler.ScriptHistoryRepository"
            ) as mock_script_repo,
            patch("handlers.system_handler.get_audit_log_buffer") as mock_audit_buffer,
        ):
            mock_script_repo.update_result = AsyncMock()
            mock_buffer = MagicMock()
            mock_buffer.add_log = AsyncMock()
            mock_audit_buffer.return_value = mock_buffer

            await handler.handle_script_result(device_id, data)

            # 不应该调用 update_result（因为没有 request_id）
            mock_script_repo.update_result.assert_not_called()
            # 但是应该记录审计日志
            mock_buffer.add_log.assert_called_once()
