import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from database.repositories import (
    UpdateHistoryRepository,
    UpdateApprovalRepository,
    AuditLogRepository,
)
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
        """处理更新检查"""
        current_version = json_data.get("current_version", "")
        latest_version = json_data.get("latest_version", "")
        request_id = json_data.get(
            "request_id", f"check-{device_id}-{int(datetime.now().timestamp())}"
        )

        try:
            result = await self.update_manager.handle_update_check(device_id, json_data)
            await self.send_to_device(device_id, MessageType.UPDATE_INFO, result)
            logger.info(f"[{device_id}] 已发送更新信息响应")

            # 数据库操作：记录更新检查
            if latest_version and latest_version != current_version:
                await UpdateHistoryRepository.insert(
                    device_id=device_id,
                    old_version=current_version,
                    new_version=latest_version,
                    status="check_requested",
                    request_id=request_id,
                )
                logger.info(f"[DB] 更新检查已记录: {device_id}")

                # 记录审计日志
                await AuditLogRepository.insert(
                    event_type="update_operation",
                    action="check_update",
                    actor_type="device",
                    actor_id=device_id,
                    device_id=device_id,
                    resource_type="update",
                    resource_id=latest_version,
                    status="success",
                    details={
                        "current_version": current_version,
                        "latest_version": latest_version,
                    },
                )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新检查失败: {e}")
            error_response = {
                "has_update": False,
                "error": f"更新检查失败: {str(e)}",
                "current_version": json_data.get("current_version", ""),
                "latest_version": json_data.get("current_version", ""),
                "request_id": request_id,
            }
            await self.send_to_device(
                device_id, MessageType.UPDATE_INFO, error_response
            )

            # 记录审计日志（异步）
            asyncio.create_task(AuditLogRepository.insert(
                event_type="update_operation",
                action="check_update",
                actor_type="device",
                actor_id=device_id,
                device_id=device_id,
                resource_type="update",
                resource_id=latest_version,
                status="failure",
                result_message=str(e),
            ))

    async def handle_update_download(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新下载请求"""
        request_id = json_data.get("request_id", "")

        try:
            result = await self.update_manager.handle_update_download(
                device_id, json_data
            )

            if result.get("status") == "approved":
                await self.send_to_device(
                    device_id, MessageType.UPDATE_APPROVE_DOWNLOAD, result
                )
                logger.info(f"[{device_id}] 已批准下载: {result.get('download_url')}")

                # 数据库操作：记录下载批准
                await UpdateHistoryRepository.update_download_approved(
                    request_id=request_id,
                    download_approved_at=datetime.now(),
                )
                await UpdateApprovalRepository.insert(
                    device_id=device_id,
                    action_type="download",
                    action="approve",
                    version=result.get("version"),
                    file_size=result.get("file_size"),
                    approval_time=datetime.now(),
                    request_id=request_id,
                )
                logger.info(f"[DB] 下载批准已记录: {request_id}")

                # 记录审计日志
                await AuditLogRepository.insert(
                    event_type="update_operation",
                    action="approve_download",
                    actor_type="web_console",
                    actor_id=result.get("console_id"),
                    device_id=device_id,
                    resource_type="update",
                    resource_id=result.get("version"),
                    status="success",
                    details=result,
                )
            else:
                await self.send_to_device(device_id, MessageType.UPDATE_ERROR, result)
                logger.error(f"[{device_id}] 下载请求被拒绝: {result.get('error')}")

                # 记录审计日志
                await AuditLogRepository.insert(
                    event_type="update_operation",
                    action="deny_download",
                    actor_type="system",
                    device_id=device_id,
                    resource_type="update",
                    resource_id=request_id,
                    status="failure",
                    result_message=result.get("error"),
                )
        except Exception as e:
            logger.error(f"[{device_id}] 处理下载请求失败: {e}")
            error_response = {
                "status": "error",
                "error": f"下载请求处理失败: {str(e)}",
                "request_id": request_id,
            }
            await self.send_to_device(
                device_id, MessageType.UPDATE_ERROR, error_response
            )

    async def handle_update_progress(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新进度"""
        request_id = json_data.get("request_id", "")
        progress_percent = json_data.get("progress", 0)
        status = json_data.get("status", "downloading")

        try:
            await self.update_manager.handle_update_progress(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_PROGRESS, {"device_id": device_id, **json_data}
            )

            # 数据库操作：更新进度
            if request_id:
                await UpdateHistoryRepository.update_progress(
                    request_id=request_id,
                    progress=progress_percent,
                )
                logger.debug(f"[DB] 更新进度已更新: {request_id}, {progress_percent}%")
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新进度失败: {e}")

    async def handle_update_complete(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新完成"""
        request_id = json_data.get("request_id", "")
        new_version = json_data.get("version", "")
        success = json_data.get("success", True)

        try:
            await self.update_manager.handle_update_complete(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_COMPLETE, {"device_id": device_id, **json_data}
            )

            # 数据库操作：更新完成状态
            if request_id:
                await UpdateHistoryRepository.update_status(
                    request_id=request_id,
                    status="completed" if success else "failed",
                    completed_at=datetime.now(),
                )
                logger.info(f"[DB] 更新完成已记录: {request_id}")

                # 记录审计日志
                await AuditLogRepository.insert(
                    event_type="update_operation",
                    action="update_complete" if success else "update_failed",
                    actor_type="device",
                    actor_id=device_id,
                    device_id=device_id,
                    resource_type="update",
                    resource_id=new_version,
                    status="success" if success else "failure",
                    details={
                        "version": new_version,
                        "request_id": request_id,
                    },
                )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新完成通知失败: {e}")

    async def handle_update_error(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新错误"""
        request_id = json_data.get("request_id", "")
        error_message = json_data.get("error", "")
        error_stage = json_data.get("stage", "unknown")

        try:
            await self.update_manager.handle_update_error(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ERROR, {"device_id": device_id, **json_data}
            )

            # 数据库操作：记录错误
            if request_id:
                await UpdateHistoryRepository.update_error(
                    request_id=request_id,
                    error_message=error_message,
                    error_stage=error_stage,
                    status="error",
                )
                logger.info(f"[DB] 更新错误已记录: {request_id}")

                # 记录审计日志
                await AuditLogRepository.insert(
                    event_type="update_operation",
                    action="update_error",
                    actor_type="device",
                    actor_id=device_id,
                    device_id=device_id,
                    resource_type="update",
                    resource_id=request_id,
                    status="failure",
                    result_message=error_message,
                    details={
                        "stage": error_stage,
                        "error": error_message,
                    },
                )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新错误通知失败: {e}")

    async def handle_update_rollback(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新回滚"""
        request_id = json_data.get("request_id", "")
        reason = json_data.get("reason", "")

        try:
            await self.update_manager.handle_update_rollback(device_id, json_data)
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_ROLLBACK, {"device_id": device_id, **json_data}
            )

            # 数据库操作：记录回滚
            if request_id:
                await UpdateHistoryRepository.update_rollback(
                    request_id=request_id,
                    rollback_reason=reason,
                    rollback_requested_at=datetime.now(),
                )
                logger.info(f"[DB] 更新回滚已记录: {request_id}")

                # 记录审计日志
                await AuditLogRepository.insert(
                    event_type="update_operation",
                    action="update_rollback",
                    actor_type="device",
                    actor_id=device_id,
                    device_id=device_id,
                    resource_type="update",
                    resource_id=request_id,
                    status="success",
                    details={
                        "reason": reason,
                        "request_id": request_id,
                    },
                )
        except Exception as e:
            logger.error(f"[{device_id}] 处理更新回滚通知失败: {e}")

    async def handle_update_request_approval(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新批准请求"""
        try:
            logger.info(f"[{device_id}] 收到更新批准请求，转发到Web")
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_REQUEST_APPROVAL,
                {"device_id": device_id, **json_data},
            )

            # 记录审计日志
            await AuditLogRepository.insert(
                event_type="update_operation",
                action="request_approval",
                actor_type="device",
                actor_id=device_id,
                device_id=device_id,
                resource_type="update",
                resource_id=json_data.get("version", ""),
                status="pending",
                details={
                    "version": json_data.get("version"),
                },
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理批准请求失败: {e}")

    async def handle_update_download_ready(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理下载完成通知"""
        try:
            logger.info(f"[{device_id}] 下载完成，转发到Web")
            await self.broadcast_to_web_consoles(
                MessageType.UPDATE_DOWNLOAD_READY, {"device_id": device_id, **json_data}
            )

            # 数据库操作：更新下载完成状态
            await UpdateHistoryRepository.update_status(
                request_id=json_data.get("request_id", ""),
                status="download_ready",
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理下载完成通知失败: {e}")

    async def handle_update_approve_install(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理安装批准"""
        request_id = json_data.get("request_id", "")

        try:
            logger.info(f"[{device_id}] 收到安装批准，转发到Agent")
            logger.debug(f"[{device_id}] 完整数据: {json_data}")
            await self.send_to_device(
                device_id, MessageType.UPDATE_APPROVE_INSTALL, json_data
            )

            # 数据库操作：记录安装批准
            if request_id:
                await UpdateHistoryRepository.update_install_approved(
                    request_id=request_id,
                    install_approved_at=datetime.now(),
                )
                await UpdateApprovalRepository.insert(
                    device_id=device_id,
                    action_type="install",
                    action="approve",
                    version=json_data.get("version"),
                    approval_time=datetime.now(),
                    request_id=request_id,
                )
                logger.info(f"[DB] 安装批准已记录: {request_id}")

                # 记录审计日志
                await AuditLogRepository.insert(
                    event_type="update_operation",
                    action="approve_install",
                    actor_type="web_console",
                    actor_id=json_data.get("console_id"),
                    device_id=device_id,
                    resource_type="update",
                    resource_id=json_data.get("version"),
                    status="success",
                    details=json_data,
                )
        except Exception as e:
            logger.error(f"[{device_id}] 处理安装批准失败: {e}")

    async def handle_update_deny(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理拒绝请求"""
        request_id = json_data.get("request_id", "")
        reason = json_data.get("reason", "")

        try:
            logger.info(f"[{device_id}] 收到拒绝请求，转发到Agent")
            await self.send_to_device(device_id, MessageType.UPDATE_DENY, json_data)

            # 记录审计日志
            await UpdateApprovalRepository.insert(
                device_id=device_id,
                action_type="install",
                action="deny",
                version=json_data.get("version"),
                approval_time=datetime.now(),
                reason=reason,
                request_id=request_id,
            )

            await AuditLogRepository.insert(
                event_type="update_operation",
                action="deny_install",
                actor_type="web_console",
                actor_id=json_data.get("console_id"),
                device_id=device_id,
                resource_type="update",
                resource_id=request_id,
                status="success",
                details={
                    "reason": reason,
                },
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理拒绝请求失败: {e}")

    async def handle_update_approve_download(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理Web下载批准"""
        request_id = json_data.get("request_id", "")
        version = json_data.get("version", "")
        file_size = json_data.get("file_size", 0)

        try:
            logger.info(f"[{device_id}] 收到Web下载批准，转发到Agent")
            # 从版本信息获取下载URL和校验信息
            version_info = json_data.get("version", "")
            latest_yaml_data = self.update_manager._load_latest_yaml()

            if not latest_yaml_data:
                logger.error(f"[{device_id}] 无法加载版本信息")
                await self.send_to_device(
                    device_id,
                    MessageType.UPDATE_ERROR,
                    {
                        "status": "error",
                        "error": "版本信息不可用",
                        "request_id": request_id,
                    },
                )
                return

            latest_version = latest_yaml_data.get("version", "")
            if version != latest_version:
                logger.warning(
                    f"[{device_id}] 请求的版本 {version} 与最新版本 {latest_version} 不匹配"
                )

            # 获取文件信息
            filename = self.update_manager._get_file_path()
            if not filename:
                await self.send_to_device(
                    device_id,
                    MessageType.UPDATE_ERROR,
                    {
                        "status": "error",
                        "error": "未找到更新包文件",
                        "request_id": request_id,
                    },
                )
                return

            package_path = self.update_manager._get_package_file_path()
            if not package_path or not package_path.exists():
                await self.send_to_device(
                    device_id,
                    MessageType.UPDATE_ERROR,
                    {
                        "status": "error",
                        "error": f"更新包文件不存在: {filename}",
                        "request_id": request_id,
                    },
                )
                return

            # 构建批准响应
            response = {
                "status": "approved",
                "download_url": filename,
                "file_size": file_size,
                "sha512_checksum": self.update_manager._get_file_checksum(),
                "md5_checksum": "",
                "sha256_checksum": "",
                "request_id": request_id,
                "version": latest_version,
                "mandatory": False,
                "approval_time": datetime.utcnow().isoformat() + "Z",
            }

            logger.info(f"[{device_id}] 下载已批准: {filename}, size={file_size}")
            await self.send_to_device(
                device_id, MessageType.UPDATE_APPROVE_DOWNLOAD, response
            )

            # 记录审计日志
            await UpdateApprovalRepository.insert(
                device_id=device_id,
                action_type="download",
                action="approve",
                version=latest_version,
                file_size=file_size,
                approval_time=datetime.now(),
                request_id=request_id,
            )

            await AuditLogRepository.insert(
                event_type="update_operation",
                action="approve_download",
                actor_type="web_console",
                actor_id=json_data.get("console_id"),
                device_id=device_id,
                resource_type="update",
                resource_id=latest_version,
                status="success",
                details={
                    "version": latest_version,
                    "file_size": file_size,
                },
            )
        except Exception as e:
            logger.error(f"[{device_id}] 处理Web下载批准失败: {e}")
            error_response = {
                "status": "error",
                "error": f"下载批准处理失败: {str(e)}",
                "request_id": request_id,
            }
            await self.send_to_device(
                device_id, MessageType.UPDATE_ERROR, error_response
            )

    async def _broadcast_update_progress(
        self, device_id: str, progress_data: Dict[str, Any]
    ) -> None:
        """广播更新进度"""
        await self.broadcast_to_web_consoles(
            MessageType.UPDATE_PROGRESS, {"device_id": device_id, **progress_data}
        )

    async def _broadcast_update_status(
        self, device_id: str, status_data: Dict[str, Any]
    ) -> None:
        """广播更新状态"""
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
