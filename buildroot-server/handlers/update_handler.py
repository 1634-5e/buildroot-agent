import logging
from typing import Dict, Any
from datetime import datetime

from handlers.base import BaseHandler
from protocol.constants import MessageType
from managers.update import UpdateManager

logger = logging.getLogger(__name__)


class UpdateHandler(BaseHandler):
    def __init__(
        self,
        conn_mgr,
        updates_dir: str = "./updates",
        latest_yaml: str = "./updates/latest.yml",
    ):
        super().__init__(conn_mgr)
        self.update_manager = UpdateManager(updates_dir, latest_yaml)
        self.update_manager._broadcast_update_progress = self._broadcast_update_progress
        self.update_manager._broadcast_update_status = self._broadcast_update_status

    async def handle_update_check(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        try:
            result = await self.update_manager.handle_update_check(device_id, json_data)
            await self.send_to_device(device_id, MessageType.UPDATE_INFO, result)
            logger.info(f"[{device_id}] 已发送更新信息响应")
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新检查失败: {e}")
            error_response = {
                "has_update": "false",
                "error": f"更新检查失败: {str(e)}",
                "current_version": json_data.get("current_version", ""),
                "latest_version": json_data.get("current_version", ""),
                "request_id": f"check-{device_id}-{int(datetime.now().timestamp())}",
            }
            await self.send_to_device(
                device_id, MessageType.UPDATE_INFO, error_response
            )

    async def handle_update_download(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        try:
            result = await self.update_manager.handle_update_download(
                device_id, json_data
            )
            if result.get("status") == "approved":
                await self.send_to_device(device_id, MessageType.UPDATE_APPROVE, result)
                logger.info(f"[{device_id}] 已批准下载: {result.get('download_url')}")
            else:
                await self.send_to_device(device_id, MessageType.UPDATE_ERROR, result)
                logger.error(f"[{device_id}] 下载请求被拒绝: {result.get('error')}")
        except Exception as e:
            logger.error(f"[{device_id}] 处理下载请求失败: {e}")
            error_response = {
                "status": "error",
                "error": f"下载请求处理失败: {str(e)}",
                "request_id": json_data.get("request_id", ""),
            }
            await self.send_to_device(
                device_id, MessageType.UPDATE_ERROR, error_response
            )

    async def handle_update_progress(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        try:
            await self.update_manager.handle_update_progress(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_PROGRESS, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新进度失败: {e}")

    async def handle_update_complete(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        try:
            await self.update_manager.handle_update_complete(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_COMPLETE, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新完成通知失败: {e}")

    async def handle_update_error(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        try:
            await self.update_manager.handle_update_error(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ERROR, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新错误通知失败: {e}")

    async def handle_update_rollback(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        try:
            await self.update_manager.handle_update_rollback(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ROLLBACK, {"device_id": device_id, **json_data}
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新回滚通知失败: {e}")

    async def _broadcast_update_progress(
        self, device_id: str, progress_data: Dict[str, Any]
    ) -> None:
        await self.broadcast_to_web_consoles(MessageType.UPDATE_PROGRESS, progress_data)

    async def _broadcast_update_status(
        self, device_id: str, status_data: Dict[str, Any]
    ) -> None:
        event_type = status_data.get("event", "update_status")
        if event_type == "update_complete":
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_COMPLETE, status_data
            )
        elif event_type == "update_error":
            await self.broadcast_to_web_consoles(MessageType.UPDATE_ERROR, status_data)
        elif event_type == "update_rollback":
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ROLLBACK, status_data
            )
        else:
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_PROGRESS, status_data
            )
