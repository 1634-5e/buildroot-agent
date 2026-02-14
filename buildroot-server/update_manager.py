#!/usr/bin/env python3
"""
Buildroot Agent 更新管理模块
为 server_example.py 添加缺失的更新处理功能
"""

import json
import os
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class UpdateManager:
    """更新管理器 - 处理Agent更新请求"""

    def __init__(self, updates_dir: str = "updates"):
        self.updates_dir = Path(updates_dir)
        self.update_metadata = self._load_update_metadata()

    def _load_update_metadata(self) -> Dict[str, Any]:
        """加载更新元数据"""
        metadata_file = self.updates_dir / "manifest.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"成功加载更新元数据: {metadata_file}")
                    return data
            except Exception as e:
                logger.error(f"加载更新元数据失败: {e}")

        # 返回默认元数据（标准格式）
        logger.warning("使用默认更新元数据")
        return {
            "manifest_version": "1.0",
            "channel": "stable",
            "latest_version": "1.0.0",
            "release_date": datetime.utcnow().isoformat() + "Z",
            "changes": [],
            "architectures": {},
        }

    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较版本号 - 返回: -1(v1<v2), 0(v1==v2), 1(v1>v2)"""

        def version_tuple(v):
            # 移除可能的后缀 (如 -beta, -dev)
            clean_v = v.split("-")[0]
            return tuple(map(int, (clean_v.split("."))))

        try:
            t1 = version_tuple(v1)
            t2 = version_tuple(v2)
            return (t1 > t2) - (t1 < t2)
        except:
            return 0

    async def handle_update_check(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理更新检查请求"""
        try:
            current_version = json_data.get("current_version", "1.0.0")
            channel = json_data.get("channel", "stable")
            arch = json_data.get("arch", "x86_64")

            logger.info(
                f"[{device_id}] 检查更新: 当前版本={current_version}, 渠道={channel}, 架构={arch}"
            )

            # 获取最新版本信息
            latest_version = self.update_metadata.get("latest_version", "1.0.0")
            manifest_channel = self.update_metadata.get("channel", "stable")

            # 检查是否有更新
            has_update = self._compare_versions(latest_version, current_version) > 0

            response = {
                "has_update": str(has_update).lower(),  # 转换为字符串 "true"/"false"
                "current_version": current_version,
                "latest_version": latest_version,
                "channel": channel,
                "arch": arch,
                "request_id": f"check-{device_id}-{int(datetime.now().timestamp())}",
            }

            if has_update:
                # 从 architectures 获取架构特定的信息
                architectures = self.update_metadata.get("architectures", {})
                arch_info = architectures.get(arch)

                if arch_info:
                    filename = arch_info.get(
                        "file", f"buildroot-agent-{latest_version}-{arch}.tar"
                    )
                    changes = self.update_metadata.get("changes", [])

                    response.update(
                        {
                            "version_code": int(
                                latest_version.replace(".", "")
                            ),  # 简单的版本号转换
                            "file_size": arch_info.get("size", 0),
                            "download_url": filename,  # 相对路径，由服务器处理
                            "sha256_checksum": arch_info.get("sha256", ""),
                            "release_notes": f"更新到版本 {latest_version}",
                            "mandatory": arch_info.get("mandatory", False),
                            "release_date": self.update_metadata.get(
                                "release_date", ""
                            ),
                            "changes": changes,
                        }
                    )
                else:
                    logger.warning(f"[{device_id}] 未找到架构 {arch} 的更新信息")
                    response["has_update"] = "false"
                    response["error"] = f"不支持架构: {arch}"

            logger.info(
                f"[{device_id}] 更新检查结果: has_update={response['has_update']}, latest={latest_version}"
            )
            return response

        except Exception as e:
            logger.error(f"[{device_id}] 处理更新检查失败: {e}")
            return {
                "has_update": "false",
                "error": f"更新检查失败: {str(e)}",
                "current_version": json_data.get("current_version", "1.0.0"),
                "latest_version": json_data.get("current_version", "1.0.0"),
            }

    async def handle_update_download(
        self, device_id: str, json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理更新下载请求"""
        try:
            version = json_data.get("version", "")
            request_id = json_data.get("request_id", "")

            logger.info(
                f"[{device_id}] 请求下载更新: version={version}, request_id={request_id}"
            )

            # 获取架构信息
            arch = json_data.get("arch", "x86_64")
            architectures = self.update_metadata.get("architectures", {})
            arch_info = architectures.get(arch)

            if not arch_info:
                return {
                    "status": "error",
                    "error": f"不支持架构: {arch}",
                    "request_id": request_id,
                }

            # 获取文件名
            filename = arch_info.get("file", f"buildroot-agent-{version}-{arch}.tar")
            package_path = self.updates_dir / filename

            if not package_path.exists():
                return {
                    "status": "error",
                    "error": f"更新包文件不存在: {filename}",
                    "request_id": request_id,
                }

            # 从 manifest 直接获取 SHA256
            sha256_checksum = arch_info.get("sha256", "")

            # 构建下载批准响应
            response = {
                "status": "approved",
                "download_url": filename,  # 文件名，服务器会处理
                "file_size": arch_info.get("size", package_path.stat().st_size),
                "sha256_checksum": sha256_checksum,
                "request_id": request_id,
                "version": version,
                "mandatory": arch_info.get("mandatory", False),
                "approval_time": datetime.utcnow().isoformat() + "Z",
            }

            logger.info(
                f"[{device_id}] 下载已批准: {filename}, size={response['file_size']}"
            )
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
        print("更新检查结果:", json.dumps(result, indent=2, ensure_ascii=False))

        # 测试下载请求
        if result.get("has_update") == "true":
            download_data = {
                "version": result["latest_version"],
                "request_id": "test-123",
            }

            download_result = await manager.handle_update_download(
                "test-device", download_data
            )
            print(
                "下载请求结果:",
                json.dumps(download_result, indent=2, ensure_ascii=False),
            )

    asyncio.run(test())


if __name__ == "__main__":
    test_update_manager()
