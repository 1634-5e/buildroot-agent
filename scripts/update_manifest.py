#!/usr/bin/env python3
# 自动修复manifest.json，确保文件大小和SHA256与实际文件匹配

import json
import os
import hashlib
import sys
from datetime import datetime


def calculate_sha256(filepath):
    """计算文件的SHA256校验和"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def compare_versions(v1, v2):
    """比较版本号，返回: -1(v1<v2), 0(v1==v2), 1(v1>v2)"""
    try:
        v1_parts = list(map(int, v1.split(".")))
        v2_parts = list(map(int, v2.split(".")))

        # 补齐版本号长度
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        else:
            return 0
    except:
        return 0


def update_manifest(updates_dir, manifest_file):
    """更新manifest文件"""
    print("=" * 40)
    print("更新 Manifest 文件")
    print("=" * 40)
    print(f"位置: {manifest_file}")
    print()

    # 加载现有manifest
    if os.path.exists(manifest_file):
        with open(manifest_file, "r") as f:
            try:
                manifest = json.load(f)
            except json.JSONDecodeError as e:
                print(f"错误: manifest.json格式错误: {e}")
                return False
    else:
        print("警告: manifest.json不存在，创建新文件")
        manifest = {
            "manifest_version": "1.0",
            "channel": "stable",
            "latest_version": "1.0.0",
            "release_date": datetime.utcnow().isoformat() + "Z",
            "changes": [],
            "architectures": {},
        }

    # 获取所有tar文件
    tar_files = [
        f
        for f in os.listdir(updates_dir)
        if f.startswith("buildroot-agent-") and f.endswith(".tar")
    ]

    updated = False
    latest_version = "1.0.0"

    # 收集所有版本信息
    arch_versions = {}
    for tar_file in tar_files:
        # 解析文件名获取版本和架构
        parts = tar_file.replace(".tar", "").split("-")
        if len(parts) >= 3:
            version = parts[2]
            arch = parts[3] if len(parts) > 3 else "x86_64"

            # 更新最新版本
            if compare_versions(version, latest_version) > 0:
                latest_version = version

            # 为每个架构保留最新版本
            if arch not in arch_versions:
                arch_versions[arch] = (version, tar_file)
            else:
                existing_version, _ = arch_versions[arch]
                if compare_versions(version, existing_version) > 0:
                    arch_versions[arch] = (version, tar_file)

    # 为每个架构选择最新版本
    for arch, (version, tar_file) in arch_versions.items():
        filepath = os.path.join(updates_dir, tar_file)

        # 计算文件信息
        file_size = os.path.getsize(filepath)
        sha256_checksum = calculate_sha256(filepath)

        # 检查manifest中是否已有此架构
        arch_info = manifest.get("architectures", {}).get(arch, {})

        old_file = arch_info.get("file", "")
        old_size = arch_info.get("size", 0)
        old_sha256 = arch_info.get("sha256", "")
        old_version = (
            old_file.split("-")[2] if old_file and "-" in old_file else "0.0.0"
        )

        # 检查是否需要更新（新版本或文件变化）
        needs_update = False
        if compare_versions(version, old_version) > 0:
            print(f"更新 {arch}: 新版本 {old_version} -> {version}")
            needs_update = True
        elif arch_info.get("file") != tar_file and version == old_version:
            print(f"更新 {arch}: 文件变化但版本相同")
            needs_update = True
        elif old_size != file_size:
            print(f"更新 {arch}: 大小变化 {old_size} -> {file_size}")
            needs_update = True
        elif old_sha256 != sha256_checksum:
            print(f"更新 {arch}: SHA256变化")
            needs_update = True

        if needs_update:
            # 更新manifest
            if "architectures" not in manifest:
                manifest["architectures"] = {}

            manifest["architectures"][arch] = {
                "file": tar_file,
                "size": file_size,
                "sha256": sha256_checksum,
                "mandatory": False,
            }
            updated = True
            print(f"  文件: {tar_file}")
            print(f"  大小: {file_size}")
            print(f"  SHA256: {sha256_checksum[:16]}...")
            print()

    # 更新最新版本
    manifest["latest_version"] = latest_version
    manifest["release_date"] = datetime.utcnow().isoformat() + "Z"

    if updated:
        # 备份旧manifest
        if os.path.exists(manifest_file):
            backup_file = manifest_file + ".bak"
            if os.path.exists(backup_file):
                os.remove(backup_file)
            os.rename(manifest_file, backup_file)
            print(f"已备份旧manifest到: {backup_file}")

        # 写入新manifest
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

        print("=" * 40)
        print("✓ Manifest已更新")
        print("=" * 40)
        return True
    else:
        print("=" * 40)
        print("✓ Manifest已是最新，无需更新")
        print("=" * 40)
        return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    updates_dir = os.path.join(project_root, "buildroot-server", "updates")
    manifest_file = os.path.join(updates_dir, "manifest.json")

    if not os.path.exists(updates_dir):
        print(f"错误: updates目录不存在: {updates_dir}")
        return 1

    if not os.path.isdir(updates_dir):
        print(f"错误: updates不是目录: {updates_dir}")
        return 1

    try:
        update_manifest(updates_dir, manifest_file)
        return 0
    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
