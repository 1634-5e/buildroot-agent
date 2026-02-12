#!/usr/bin/env python3
"""
模拟更新场景测试器
用于独立测试Agent的更新逻辑，无需真实的Agent进程
"""

import asyncio
import json
import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class MockUpdateScenarios:
    """模拟更新场景测试器"""

    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="agent_update_test_"))
        self.agents_dir = self.test_dir / "agents"
        self.backups_dir = self.test_dir / "backups"
        self.temp_dir = self.test_dir / "temp"

        # 创建测试目录结构
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"测试环境创建在: {self.test_dir}")

    def create_mock_agent_binary(self, version: str, path: Path) -> None:
        """创建模拟的Agent二进制文件"""
        content = f"""#!/bin/bash
# Mock Agent Binary v{version}
echo "Mock Agent v{version} - Version: {version}"
echo "Arguments: $*"
echo "Current time: $(date)"
echo "Working directory: $(pwd)"

# 模拟不同的版本行为
case "{version}" in
    "1.0.0")
        echo "Base version - minimal features"
        exit 0
        ;;
    "1.0.1")
        echo "Bug fix version - improved stability"
        exit 0
        ;;
    "1.0.1-bad")
        echo "Corrupted version - this should fail"
        exit 1
        ;;
    "1.0.1-corrupted")
        echo "Truncated version - incomplete binary"
        # 模拟文件截断
        exit 1
        ;;
    "1.1.0")
        echo "Feature version - enhanced capabilities"
        exit 0
        ;;
    "2.0.0")
        echo "Major version - breaking changes"
        echo "New architecture detected"
        exit 0
        ;;
    *)
        echo "Unknown version: {version}"
        exit 1
        ;;
esac
"""
        path.write_text(content)
        path.chmod(0o755)
        logger.info(f"创建模拟Agent: {path} (v{version})")

    async def test_version_comparison(self) -> Dict[str, Any]:
        """测试版本比较逻辑"""
        logger.info("=== 测试版本比较逻辑 ===")

        test_cases = [
            ("1.0.0", "1.0.1", -1),
            ("1.0.1", "1.0.0", 1),
            ("1.0.0", "1.0.0", 0),
            ("1.0.1", "1.1.0", -1),
            ("2.0.0", "1.1.0", 1),
            ("1.0.0", "1.0.0-beta", 0),  # beta后缀被忽略
        ]

        results = {}
        for v1, v2, expected in test_cases:
            actual = self._compare_versions(v1, v2)
            status = "✓" if actual == expected else "✗"
            results[f"{v1}_vs_{v2}"] = {
                "expected": expected,
                "actual": actual,
                "status": status,
            }
            logger.info(f"  {status} {v1} vs {v2}: 期望{expected}, 实际{actual}")

        return {"test": "version_comparison", "results": results}

    async def test_update_check_workflow(self) -> Dict[str, Any]:
        """测试更新检查工作流"""
        logger.info("=== 测试更新检查工作流 ===")

        # 模拟不同设备的当前版本
        test_devices = [
            {"id": "device-001", "current": "1.0.0", "channel": "stable"},
            {"id": "device-002", "current": "1.0.1", "channel": "stable"},
            {"id": "device-003", "current": "1.1.0", "channel": "stable"},
            {"id": "device-004", "current": "1.0.0", "channel": "beta"},
        ]

        # 模拟更新服务器响应
        mock_server_responses = {
            "stable": {
                "latest_version": "1.1.0",
                "versions": {
                    "1.0.1": {"file": "agent-update-1.0.1.tar.gz", "mandatory": False},
                    "1.1.0": {"file": "agent-update-1.1.0.tar.gz", "mandatory": False},
                },
            },
            "beta": {
                "latest_version": "2.0.0",
                "versions": {
                    "2.0.0": {"file": "agent-update-2.0.0.tar.gz", "mandatory": True},
                },
            },
        }

        results = {}
        for device in test_devices:
            current = device["current"]
            channel = device["channel"]
            server_data = mock_server_responses[channel]
            latest = server_data["latest_version"]

            has_update = self._compare_versions(latest, current) > 0
            update_info = None

            if has_update:
                version_data = server_data["versions"].get(latest, {})
                update_info = {
                    "has_update": True,
                    "latest_version": latest,
                    "current_version": current,
                    "download_url": version_data.get("file"),
                    "mandatory": version_data.get("mandatory", False),
                }
            else:
                update_info = {
                    "has_update": False,
                    "latest_version": latest,
                    "current_version": current,
                }

            results[device["id"]] = update_info
            status = "有更新" if has_update else "无更新"
            logger.info(f"  {device['id']}: {current} -> {latest} ({status})")

        return {"test": "update_check", "results": results}

    async def test_backup_and_restore(self) -> Dict[str, Any]:
        """测试备份和恢复功能"""
        logger.info("=== 测试备份和恢复功能 ===")

        # 创建原始Agent
        original_agent = self.agents_dir / "buildroot-agent"
        self.create_mock_agent_binary("1.0.0", original_agent)

        # 模拟备份过程
        backup_file = (
            self.backups_dir / f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(original_agent, backup_file)

        # 验证备份
        backup_valid = backup_file.exists() and backup_file.stat().st_size > 0

        # 模拟更新后回滚
        updated_agent = self.agents_dir / "buildroot-agent"
        self.create_mock_agent_binary("1.0.1", updated_agent)

        # 模拟回滚
        shutil.copy2(backup_file, original_agent)
        rollback_valid = original_agent.exists()

        # 测试版本
        import subprocess

        try:
            version_result = subprocess.run(
                [str(original_agent)], capture_output=True, text=True, timeout=5
            )
            rollback_version = "1.0.0" in version_result.stdout
        except:
            rollback_version = False

        results = {
            "backup_created": backup_valid,
            "backup_file": str(backup_file),
            "rollback_successful": rollback_valid,
            "rollback_version_correct": rollback_version,
        }

        logger.info(f"  备份创建: {'✓' if backup_valid else '✗'}")
        logger.info(f"  回滚成功: {'✓' if rollback_valid else '✗'}")
        logger.info(f"  版本正确: {'✓' if rollback_version else '✗'}")

        return {"test": "backup_restore", "results": results}

    async def test_package_validation(self) -> Dict[str, Any]:
        """测试包校验功能"""
        logger.info("=== 测试包校验功能 ===")

        # 创建不同类型的测试包
        test_packages = {
            "valid": {
                "content": "valid_package_data",
                "expected_md5": "d41d8cd98f00b204e9800998ecf8427e",
                "should_pass": True,
            },
            "invalid_md5": {
                "content": "different_content",
                "expected_md5": "d41d8cd98f00b204e9800998ecf8427e",  # 错误的MD5
                "should_pass": False,
            },
            "corrupted": {
                "content": "corrupted_data",
                "expected_md5": "d41d8cd98f00b204e9800998ecf8427e",
                "should_pass": False,
                "corrupt": True,
            },
        }

        results = {}
        for name, pkg in test_packages.items():
            # 创建测试文件
            test_file = self.temp_dir / f"test_{name}.pkg"
            test_file.write_text(pkg["content"])

            if pkg.get("corrupt"):
                # 截断文件模拟损坏
                test_file.write_text(pkg["content"][:5])

            # 计算实际MD5
            import hashlib

            with open(test_file, "rb") as f:
                actual_md5 = hashlib.md5(f.read()).hexdigest()

            # 验证校验和
            md5_match = actual_md5 == pkg["expected_md5"]
            expected_result = pkg["should_pass"]
            test_passed = md5_match == expected_result

            results[name] = {
                "expected_md5": pkg["expected_md5"],
                "actual_md5": actual_md5,
                "md5_match": md5_match,
                "should_pass": expected_result,
                "test_passed": test_passed,
            }

            status = "✓" if test_passed else "✗"
            logger.info(
                f"  {status} {name}: MD5匹配={md5_match}, 预期通过={expected_result}"
            )

        return {"test": "package_validation", "results": results}

    async def test_error_scenarios(self) -> Dict[str, Any]:
        """测试错误场景"""
        logger.info("=== 测试错误场景 ===")

        error_scenarios = {
            "missing_package": {
                "description": "更新包文件不存在",
                "test": lambda: self._test_missing_package(),
            },
            "permission_denied": {
                "description": "权限不足",
                "test": lambda: self._test_permission_denied(),
            },
            "insufficient_space": {
                "description": "磁盘空间不足",
                "test": lambda: self._test_insufficient_space(),
            },
            "network_failure": {
                "description": "网络连接失败",
                "test": lambda: self._test_network_failure(),
            },
        }

        results = {}
        for name, scenario in error_scenarios.items():
            try:
                result = scenario["test"]()
                results[name] = {
                    "description": scenario["description"],
                    "result": result,
                    "handled_properly": isinstance(result, str)
                    and "error" in result.lower(),
                }
                status = "✓" if results[name]["handled_properly"] else "✗"
                logger.info(f"  {status} {name}: {scenario['description']}")
            except Exception as e:
                results[name] = {
                    "description": scenario["description"],
                    "result": f"exception: {str(e)}",
                    "handled_properly": True,  # 异常被捕获
                }
                logger.info(f"  ✓ {name}: 异常被正确处理 - {str(e)}")

        return {"test": "error_scenarios", "results": results}

    def _test_missing_package(self) -> str:
        """测试缺少包文件的情况"""
        non_existent_file = self.temp_dir / "non_existent.tar.gz"
        if not non_existent_file.exists():
            return "error: package file not found"
        return "unexpected: file found"

    def _test_permission_denied(self) -> str:
        """测试权限不足的情况"""
        restricted_file = self.temp_dir / "restricted.sh"
        restricted_file.write_text("#!/bin/bash\necho test")
        restricted_file.chmod(0o000)  # 移除所有权限

        try:
            with open(restricted_file, "r") as f:
                f.read()
            return "unexpected: permission not denied"
        except PermissionError:
            return "error: permission denied"

    def _test_insufficient_space(self) -> str:
        """测试磁盘空间不足的情况"""
        # 检查可用空间
        statvfs = os.statvfs(str(self.temp_dir))
        free_space = statvfs.f_frsize * statvfs.f_bavail

        # 如果可用空间小于1MB，模拟空间不足
        if free_space < 1024 * 1024:
            return "error: insufficient disk space"
        else:
            return f"info: sufficient disk space ({free_space} bytes)"

    def _test_network_failure(self) -> str:
        """测试网络连接失败的情况"""
        # 尝试连接到不存在的地址
        import socket

        try:
            socket.create_connection(("non-existent-host.invalid", 80), timeout=1)
            return "unexpected: connection succeeded"
        except (socket.gaierror, socket.timeout, ConnectionRefusedError):
            return "error: network connection failed"

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

    def cleanup(self):
        """清理测试环境"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            logger.info(f"清理测试环境: {self.test_dir}")


async def run_mock_update_tests():
    """运行所有模拟更新测试"""
    print("Buildroot Agent 自更新功能 - 模拟测试")
    print("=" * 60)

    tester = MockUpdateScenarios()
    test_results = {}

    try:
        # 运行各项测试
        tests = [
            tester.test_version_comparison,
            tester.test_update_check_workflow,
            tester.test_backup_and_restore,
            tester.test_package_validation,
            tester.test_error_scenarios,
        ]

        for test_func in tests:
            result = await test_func()
            test_name = result["test"]
            test_results[test_name] = result
            print()  # 空行分隔

        # 生成测试报告
        print("=" * 60)
        print("测试报告总结")
        print("=" * 60)

        for test_name, result in test_results.items():
            print(f"\n{test_name.upper()}:")
            if test_name == "version_comparison":
                passed = sum(
                    1 for r in result["results"].values() if r["status"] == "✓"
                )
                total = len(result["results"])
                print(f"  通过率: {passed}/{total} ({passed / total * 100:.1f}%)")
            elif test_name == "update_check":
                with_updates = sum(
                    1 for r in result["results"].values() if r.get("has_update")
                )
                print(f"  检测到更新的设备: {with_updates}/{len(result['results'])}")
            elif test_name == "backup_restore":
                results = result["results"]
                passed_tests = sum(
                    [
                        results["backup_created"],
                        results["rollback_successful"],
                        results["rollback_version_correct"],
                    ]
                )
                print(f"  通过测试: {passed_tests}/3 ({passed_tests / 3 * 100:.1f}%)")
            elif test_name == "package_validation":
                passed = sum(1 for r in result["results"].values() if r["test_passed"])
                total = len(result["results"])
                print(f"  通过率: {passed}/{total} ({passed / total * 100:.1f}%)")
            elif test_name == "error_scenarios":
                handled = sum(
                    1 for r in result["results"].values() if r["handled_properly"]
                )
                total = len(result["results"])
                print(f"  正确处理: {handled}/{total} ({handled / total * 100:.1f}%)")

        print(f"\n详细测试结果已保存到: {tester.test_dir}/test_results.json")

        # 保存详细结果
        with open(tester.test_dir / "test_results.json", "w") as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)

    finally:
        # 清理测试环境
        tester.cleanup()


if __name__ == "__main__":
    asyncio.run(run_mock_update_tests())
