#!/usr/bin/env python3
"""
为 server_example.py 添加更新处理功能的补丁
将此代码集成到现有的 MessageHandler 类中
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 在 MessageHandler 类的 __init__ 方法中添加:
# from update_manager import UpdateManager
# self.update_manager = UpdateManager()

# 在 MessageHandler 类中添加以下方法:


async def handle_update_check(self, device_id: str, json_data: Dict[str, Any]) -> None:
    """处理更新检查请求"""
    try:
        result = await self.update_manager.handle_update_check(device_id, json_data)
        await self.send_to_device(device_id, MessageType.UPDATE_INFO, result)
        logger.info(f"[{device_id}] 已发送更新信息响应")
    except Exception as e:
        logger.error(f"[{device_id}] 处理更新检查失败: {e}")
        error_response = {
            "has_update": "false",
            "error": f"更新检查失败: {str(e)}",
            "current_version": json_data.get("current_version", "1.0.0"),
            "latest_version": json_data.get("current_version", "1.0.0"),
        }
        await self.send_to_device(device_id, MessageType.UPDATE_INFO, error_response)


async def handle_update_download(
    self, device_id: str, json_data: Dict[str, Any]
) -> None:
    """处理更新下载请求"""
    try:
        result = await self.update_manager.handle_update_download(device_id, json_data)
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
        await self.send_to_device(device_id, MessageType.UPDATE_ERROR, error_response)


async def handle_update_progress(
    self, device_id: str, json_data: Dict[str, Any]
) -> None:
    """处理更新进度报告"""
    try:
        await self.update_manager.handle_update_progress(device_id, json_data)
        # 广播进度到Web控制台
        await self.broadcast_to_web_consoles(
            MessageType.UPDATE_PROGRESS, {"device_id": device_id, **json_data}
        )
    except Exception as e:
        logger.error(f"[{device_id}] 处理更新进度失败: {e}")


async def handle_update_complete(
    self, device_id: str, json_data: Dict[str, Any]
) -> None:
    """处理更新完成通知"""
    try:
        await self.update_manager.handle_update_complete(device_id, json_data)
        # 广播完成状态到Web控制台
        await self.broadcast_to_web_consoles(
            MessageType.UPDATE_COMPLETE, {"device_id": device_id, **json_data}
        )
    except Exception as e:
        logger.error(f"[{device_id}] 处理更新完成通知失败: {e}")


async def handle_update_error(self, device_id: str, json_data: Dict[str, Any]) -> None:
    """处理更新错误通知"""
    try:
        await self.update_manager.handle_update_error(device_id, json_data)
        # 广播错误到Web控制台
        await self.broadcast_to_web_consoles(
            MessageType.UPDATE_ERROR, {"device_id": device_id, **json_data}
        )
    except Exception as e:
        logger.error(f"[{device_id}] 处理更新错误通知失败: {e}")


async def handle_update_rollback(
    self, device_id: str, json_data: Dict[str, Any]
) -> None:
    """处理更新回滚通知"""
    try:
        await self.update_manager.handle_update_rollback(device_id, json_data)
        # 广播回滚状态到Web控制台
        await self.broadcast_to_web_consoles(
            MessageType.UPDATE_ROLLBACK, {"device_id": device_id, **json_data}
        )
    except Exception as e:
        logger.error(f"[{device_id}] 处理更新回滚通知失败: {e}")


# 修改 handle_message 方法中的消息处理部分
# 在 handlers 字典中添加更新相关的处理:

# handlers = {
#     MessageType.HEARTBEAT: self.handle_heartbeat,
#     MessageType.SYSTEM_STATUS: self.handle_system_status,
#     MessageType.LOG_UPLOAD: self.handle_log_upload,
#     MessageType.SCRIPT_RESULT: self.handle_script_result,
#     MessageType.AUTH_RESULT: self.handle_auth_result,
#     # 添加更新处理器
#     MessageType.UPDATE_CHECK: self.handle_update_check,
#     MessageType.UPDATE_DOWNLOAD: self.handle_update_download,
#     MessageType.UPDATE_PROGRESS: self.handle_update_progress,
#     MessageType.UPDATE_COMPLETE: self.handle_update_complete,
#     MessageType.UPDATE_ERROR: self.handle_update_error,
#     MessageType.UPDATE_ROLLBACK: self.handle_update_rollback,
# }

# 或者更简单的集成方式，在 handle_message 方法的 else 分支前添加:

# elif msg_type == MessageType.UPDATE_CHECK:
#     await self.handle_update_check(device_id, json_data)
# elif msg_type == MessageType.UPDATE_DOWNLOAD:
#     await self.handle_update_download(device_id, json_data)
# elif msg_type == MessageType.UPDATE_PROGRESS:
#     await self.handle_update_progress(device_id, json_data)
# elif msg_type == MessageType.UPDATE_COMPLETE:
#     await self.handle_update_complete(device_id, json_data)
# elif msg_type == MessageType.UPDATE_ERROR:
#     await self.handle_update_error(device_id, json_data)
# elif msg_type == MessageType.UPDATE_ROLLBACK:
#     await self.handle_update_rollback(device_id, json_data)

# 修改 UpdateManager 类的广播方法:


async def _broadcast_update_progress(
    self, device_id: str, progress_data: Dict[str, Any]
) -> None:
    """广播更新进度到Web控制台"""
    # 这里通过回调方法调用主类的广播功能
    pass  # 在集成时会被覆盖


async def _broadcast_update_status(
    self, device_id: str, status_data: Dict[str, Any]
) -> None:
    """广播更新状态到Web控制台"""
    # 这里通过回调方法调用主类的广播功能
    pass  # 在集成时会被覆盖
