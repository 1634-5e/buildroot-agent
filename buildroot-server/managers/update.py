#!/usr/bin/env python3
"""
Buildroot Agent 更新管理模块
为 server_example.py 添加缺失的更新处理功能
使用 Electron 风格的 YAML 版本格式
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from packaging import version
import yaml

logger = logging.getLogger(__name__)


class UpdateManager:
    """更新管理器 - 处理Agent更新请求"""

    def __init__(
        self, updates_dir: str = "./updates", latest_yaml: str = "./updates/latest.yml"
    ):
        self.updates_dir = Path(updates_dir)
        self.latest_yaml_path = Path(latest_yaml)
        self.latest_version_data = self._load_latest_yaml()

    def _load_latest_yaml(self) -> Optional[Dict[str, Any]]:
        """加载 latest.yml 文件"""
        if self.latest_yaml_path.exists():
            try:
                with open(self.latest_yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    logger.info(f"成功加载版本信息: {self.latest_yaml_path}")
                    return data
            except Exception as e:
                logger.error(f"加载 latest.yml 失败: {e}")
        else:
            logger.warning(f"latest.yml 不存在: {self.latest_yaml_path}")
        return None

    def _get_file_checksum(self) -> str:
        """从 YAML 获取文件校验和"""
        if self.latest_version_data:
            return self.latest_version_data.get("sha512", "")
        return ""

    def _get_file_size(self) -> int:
        """从 YAML 获取文件大小"""
        if self.latest_version_data:
            files = self.latest_version_data.get("files", [])
            if files:
                return files[0].get("size", 0)
        return 0

    def _get_file_path(self) -> str:
        """从 YAML 获取文件路径"""
        if self.latest_version_data:
            files = self.latest_version_data.get("files", [])
            if files:
                return files[0].get("url", "")
            return self.latest_version_data.get("path", "")
        return ""

    def _get_release_notes(self) -> str:
        """从 YAML 获取发布说明"""
        if self.latest_version_data:
            return self.latest_version_data.get("releaseNotes", "")
        return ""

    def _get_release_date(self) -> str:
        """从 YAML 获取发布日期"""
        if self.latest_version_data:
            return self.latest_version_data.get("releaseDate", "")
        return ""

    def _get_package_file_path(self) -> Optional[Path]:
        """获取更新包文件的完整路径"""
        filename = self._get_file_path()
        if not filename:
            return None
        package_path = self.updates_dir / filename
        if package_path.exists():
            return package_path
        return None

    async def handle_update_check(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理更新检查请求"""
        try:
            current_version = json_data.get("current_version", "1.0.0")
            device_id_request = json_data.get("device_id", device_id)

            logger.info(f"[{device_id}] 检查更新: 当前版本={current_version}")

            # 加载最新版本信息
            latest_yaml_data = self._load_latest_yaml()
            if not latest_yaml_data:
                logger.warning(f"[{device_id}] 无法加载版本信息")
                return {
                    "has_update": False,
                    "current_version": current_version,
                    "latest_version": current_version,
                    "request_id": f"check-{device_id}-{int(datetime.now().timestamp())}",
                }

            latest_version = latest_yaml_data.get("version", "1.0.0")

            # 使用 packaging.version 比较版本号
            try:
                has_update = version.parse(latest_version) > version.parse(
                    current_version
                )
            except Exception as e:
                logger.warning(f"[{device_id}] 版本号比较失败: {e}")
                has_update = False

            response = {
                "has_update": has_update,
                "current_version": current_version,
                "latest_version": latest_version,
                "channel": "stable",
                "request_id": f"check-{device_id}-{int(datetime.now().timestamp())}",
            }

            if has_update:
                response.update(
                    {
                        "version_code": int(
                            latest_version.replace(".", "")
                        ),  # 简单的版本号转换
                        "file_size": self._get_file_size(),
                        "download_url": self._get_file_path(),  # 相对路径
                        "sha512_checksum": self._get_file_checksum(),
                        "md5_checksum": "",  # 不再使用 MD5
                        "sha256_checksum": "",  # 不再使用 SHA256
                        "release_notes": self._get_release_notes(),
                        "mandatory": False,  # 固定为 false
                        "release_date": self._get_release_date(),
                        "changes": [],  # 使用 release_notes 代替
                    }
                )

            logger.info(
                f"[{device_id}] 更新检查结果: has_update={response['has_update']}, latest={latest_version}"
            )
            return response

        except Exception as e:
            logger.error(f"[{device_id}] 处理更新检查失败: {e}")
            return {
                "has_update": False,
                "error": f"更新检查失败: {str(e)}",
                "current_version": json_data.get("current_version", "1.0.0"),
                "latest_version": json_data.get("current_version", "1.0.0"),
                "request_id": f"check-{device_id}-{int(datetime.now().timestamp())}",
            }

    async def handle_update_download(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理更新下载请求"""
        try:
            version_requested = json_data.get("version", "")
            request_id = json_data.get("request_id", "")

            logger.info(
                f"[{device_id}] 请求下载更新: version={version_requested}, request_id={request_id}"
            )

            # 加载最新版本信息
            latest_yaml_data = self._load_latest_yaml()
            if not latest_yaml_data:
                return {
                    "status": "error",
                    "error": "版本信息不可用",
                    "request_id": request_id,
                }

            latest_version = latest_yaml_data.get("version", "")

            # 验证请求的版本
            if version_requested and version_requested != latest_version:
                logger.warning(
                    f"[{device_id}] 请求的版本 {version_requested} 与最新版本 {latest_version} 不匹配"
                )

            # 获取文件路径
            filename = self._get_file_path()
            if not filename:
                return {
                    "status": "error",
                    "error": "未找到更新包文件",
                    "request_id": request_id,
                }

            package_path = self._get_package_file_path()
            if not package_path or not package_path.exists():
                return {
                    "status": "error",
                    "error": f"更新包文件不存在: {filename}",
                    "request_id": request_id,
                }

            # 获取文件实际大小
            file_size = package_path.stat().st_size

            # 构建下载批准响应
            response = {
                "status": "approved",
                "download_url": filename,  # 相对路径
                "file_size": file_size,
                "sha512_checksum": self._get_file_checksum(),
                "md5_checksum": "",  # 不再使用 MD5
                "sha256_checksum": "",  # 不再使用 SHA256
                "request_id": request_id,
                "version": latest_version,
                "mandatory": False,  # 固定为 false
                "approval_time": datetime.utcnow().isoformat() + "Z",
            }

            logger.info(f"[{device_id}] 下载已批准: {filename}, size={file_size}")
            return response

        except Exception as e:
            logger.error(f"[{device_id}] 处理下载请求失败: {e}")
            return {
                "status": "error",
                "error": f"下载请求处理失败: {str(e)}",
                "request_id": json_data.get("request_id", ""),
            }

    async def handle_update_progress(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新进度报告"""
        try:
            progress = json_data.get("progress", 0)
            message = json_data.get("message", "")
            status = json_data.get("status", "")
            request_id = json_data.get("request_id", "")

            logger.info(f"[{device_id}] 更新进度: {progress}% - {message}")

            # 广播进度到Web控制台
            await self._broadcast_update_progress(
                device_id,
                {
                    "device_id": device_id,
                    "progress": progress,
                    "message": message,
                    "status": status,
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )

        except Exception as e:
            logger.error(f"[{device_id}] 处理更新进度失败: {e}")

    async def handle_update_complete(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新完成通知"""
        try:
            version = json_data.get("version", "")
            request_id = json_data.get("request_id", "")
            success = json_data.get("success", True)
            message = json_data.get("message", "")

            if success:
                logger.info(
                    f"[{device_id}] 更新完成: version={version}, request_id={request_id}"
                )
            else:
                logger.error(f"[{device_id}] 更新失败: {message}")

            # 广播完成状态到Web控制台
            await self._broadcast_update_status(
                device_id,
                {
                    "device_id": device_id,
                    "event": "update_complete",
                    "version": version,
                    "success": success,
                    "message": message,
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )

        except Exception as e:
            logger.error(f"[{device_id}] 处理更新完成通知失败: {e}")

    async def handle_update_error(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新错误通知"""
        try:
            error = json_data.get("error", "")
            request_id = json_data.get("request_id", "")
            status = json_data.get("status", "")

            logger.error(f"[{device_id}] 更新错误: {error} (status={status})")

            # 广播错误到Web控制台
            await self._broadcast_update_status(
                device_id,
                {
                    "device_id": device_id,
                    "event": "update_error",
                    "error": error,
                    "status": status,
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )

        except Exception as e:
            logger.error(f"[{device_id}] 处理更新错误通知失败: {e}")

    async def handle_update_rollback(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> None:
        """处理更新回滚通知"""
        try:
            backup_version = json_data.get("backup_version", "")
            reason = json_data.get("reason", "")
            success = json_data.get("success", True)

            if success:
                logger.info(
                    f"[{device_id}] 回滚成功: backup_version={backup_version}, reason={reason}"
                )
            else:
                logger.error(f"[{device_id}] 回滚失败: {reason}")

            # 广播回滚状态到Web控制台
            await self._broadcast_update_status(
                device_id,
                {
                    "device_id": device_id,
                    "event": "update_rollback",
                    "backup_version": backup_version,
                    "reason": reason,
                    "success": success,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            )

        except Exception as e:
            logger.error(f"[{device_id}] 处理更新回滚通知失败: {e}")

    async def _broadcast_update_progress(
        self, device_id: str, progress_data: Dict[str, Any]
    ) -> None:
        """广播更新进度到Web控制台 - 需要在主类中实现"""
        # 这个方法将在主类中被重写
        pass

    async def _broadcast_update_status(
        self, device_id: str, status_data: Dict[str, Any]
    ) -> None:
        """广播更新状态到Web控制台 - 需要在主类中实现"""
        # 这个方法将在主类中被重写
        pass


# 测试函数
def test_update_manager():
    """测试更新管理器"""
    import asyncio

    async def test():
        manager = UpdateManager()

        # 测试更新检查
        check_data = {
            "device_id": "test-device",
            "current_version": "1.0.0",
            "channel": "stable",
        }

        result = await manager.handle_update_check("test-device", check_data)
        print("更新检查结果:", result)

        # 测试下载请求
        if result.get("has_update"):
            download_data = {
                "version": result["latest_version"],
                "request_id": "test-123",
            }

            download_result = await manager.handle_update_download(
                "test-device", download_data
            )
            print("下载请求结果:", download_result)

    asyncio.run(test())


if __name__ == "__main__":
    test_update_manager()
