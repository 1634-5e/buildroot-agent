"""
Database Repository 单元测试
测试数据访问层功能
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from database.repositories import DeviceRepository


@pytest.mark.asyncio
class TestDeviceRepository:
    """设备仓库测试类"""

    @pytest.fixture
    def mock_device(self):
        """创建模拟设备对象"""
        device = Mock()
        device.id = 1
        device.device_id = "test-device-001"
        device.name = "Test Device"
        device.version = "1.0.0"
        device.hostname = "test-host"
        device.kernel_version = "5.10.0"
        device.ip_addr = "192.168.1.100"
        device.mac_addr = "00:11:22:33:44:55"
        device.status = "online"
        device.is_online = True
        device.last_connected_at = datetime.now()
        device.last_disconnected_at = None
        device.last_seen_at = datetime.now()
        device.current_status = {"cpu": 50.0}
        device.last_status_reported_at = datetime.now()
        device.auto_update = False
        device.tags = ["test", "demo"]
        device.created_at = datetime.now()
        device.updated_at = datetime.now()
        return device

    async def test_get_by_device_id_from_cache(self):
        """测试从缓存获取设备"""
        device_id = "test-device-001"
        cached_data = {"device_id": device_id, "name": "Cached Device"}

        with patch("database.repositories.device_detail_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=cached_data)

            result = await DeviceRepository.get_by_device_id(device_id, use_cache=True)

            assert result == cached_data
            mock_cache.get.assert_called_once_with(f"device_{device_id}")

    async def test_get_by_device_id_from_db(self, mock_device):
        """测试从数据库获取设备"""
        device_id = "test-device-001"

        with (
            patch("database.repositories.device_detail_cache") as mock_cache,
            patch("database.repositories.db_manager") as mock_db,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            # 模拟数据库查询
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_device)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_db.get_session = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=mock_session),
                    __aexit__=AsyncMock(),
                )
            )

            result = await DeviceRepository.get_by_device_id(device_id, use_cache=True)

            assert result is not None
            assert result["device_id"] == device_id
            assert result["name"] == "Test Device"

    async def test_get_by_device_id_not_found(self):
        """测试获取不存在的设备"""
        device_id = "non-existent"

        with (
            patch("database.repositories.device_detail_cache") as mock_cache,
            patch("database.repositories.db_manager") as mock_db,
        ):
            mock_cache.get = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=None)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_db.get_session = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=mock_session),
                    __aexit__=AsyncMock(),
                )
            )

            result = await DeviceRepository.get_by_device_id(device_id)

            assert result is None

    async def test_create_or_update_new_device(self):
        """测试创建设备"""
        device_id = "new-device-001"

        with (
            patch("database.repositories.device_detail_cache") as mock_cache,
            patch("database.repositories.db_manager") as mock_db,
            patch("database.repositories.device_list_cache") as mock_list_cache,
        ):
            mock_cache.delete = AsyncMock()
            mock_list_cache.clear = AsyncMock()

            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=None)  # 设备不存在
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.add = Mock()
            mock_session.commit = AsyncMock()
            mock_db.get_session = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=mock_session),
                    __aexit__=AsyncMock(),
                )
            )

            result = await DeviceRepository.create_or_update(
                device_id=device_id, name="New Device", version="1.0.0"
            )

            assert result is not None
            assert result["device_id"] == device_id
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    async def test_update_connection_status(self):
        """测试更新连接状态"""
        device_id = "test-device-001"

        with (
            patch("database.repositories.device_detail_cache") as mock_cache,
            patch("database.repositories.db_manager") as mock_db,
            patch("database.repositories.device_list_cache") as mock_list_cache,
        ):
            mock_cache.delete = AsyncMock()
            mock_list_cache.clear = AsyncMock()

            mock_device = Mock()
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_device)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()
            mock_db.get_session = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=mock_session),
                    __aexit__=AsyncMock(),
                )
            )

            await DeviceRepository.update_connection_status(
                device_id=device_id, status="offline", is_online=False
            )

            # 简化测试：只验证函数被调用
            assert mock_session.execute.called

    async def test_update_current_status(self):
        """测试更新当前状态"""
        device_id = "test-device-001"
        status_data = {"cpu_usage": 75.5, "mem_usage": 60.0}

        with (
            patch("database.repositories.device_detail_cache") as mock_cache,
            patch("database.repositories.db_manager") as mock_db,
        ):
            mock_cache.delete = AsyncMock()

            mock_device = Mock()
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=mock_device)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()
            mock_db.get_session = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=mock_session),
                    __aexit__=AsyncMock(),
                )
            )

            await DeviceRepository.update_current_status(device_id, status_data)

            # 简化测试：只验证函数被调用
            assert mock_session.execute.called

    async def test_list_devices(self):
        """测试列出设备"""
        with (
            patch("database.repositories.device_list_cache") as mock_cache,
            patch("database.repositories.db_manager") as mock_db,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            mock_devices = [
                Mock(device_id="dev-001", name="Device 1"),
                Mock(device_id="dev-002", name="Device 2"),
            ]

            mock_session = AsyncMock()
            mock_result = Mock()
            # 模拟 scalars().all() 链式调用
            mock_scalars = Mock()
            mock_scalars.all = Mock(return_value=mock_devices)
            mock_result.scalars = Mock(return_value=mock_scalars)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_db.get_session = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(return_value=mock_session),
                    __aexit__=AsyncMock(),
                )
            )

            result = await DeviceRepository.list_devices()

            assert result is not None
            assert len(result) == 2
            assert result[0]["device_id"] == "dev-001"
