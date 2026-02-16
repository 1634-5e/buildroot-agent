#!/usr/bin/env python3
# 验证manifest.json中的文件大小和SHA256是否与实际文件匹配

import json
import os
import hashlib
import sys


def main():
    # 获取脚本目录和项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    updates_dir = os.path.join(project_root, "buildroot-server", "updates")
    manifest_file = os.path.join(updates_dir, "manifest.json")

    print("=" * 40)
    print("验证 Manifest 文件")
    print("=" * 40)
    print(f"位置: {manifest_file}")
    print()

    if not os.path.exists(manifest_file):
        print(f"错误: manifest.json 不存在于 {manifest_file}")
        return 1

    # 加载manifest
    with open(manifest_file, "r") as f:
        try:
            manifest = json.load(f)
        except json.JSONDecodeError as e:
            print(f"错误: manifest.json格式错误: {e}")
            return 1

    # 获取架构信息
    architectures = manifest.get("architectures", {})
    if not architectures:
        print("警告: manifest中没有架构信息")
        return 0

    total_errors = 0

    for arch, info in architectures.items():
        print(f"--- 架构: {arch} ---")

        filename = info.get("file")
        expected_size = info.get("size", 0)
        expected_sha256 = info.get("sha256", "")

        if not filename:
            print("  错误: 没有文件名")
            total_errors += 1
            continue

        full_path = os.path.join(updates_dir, filename)

        if not os.path.exists(full_path):
            print(f"  错误: 文件不存在: {full_path}")
            total_errors += 1
            continue

        # 获取实际文件信息
        actual_size = os.path.getsize(full_path)

        # 计算实际SHA256
        sha256_hash = hashlib.sha256()
        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        actual_sha256 = sha256_hash.hexdigest()

        print(f"  文件: {filename}")
        print(f"  期望大小: {expected_size} 字节")
        print(f"  实际大小: {actual_size} 字节")
        print(f"  期望SHA256: {expected_sha256[:16]}...")
        print(f"  实际SHA256: {actual_sha256[:16]}...")

        # 验证大小
        if expected_size == actual_size:
            print("  ✓ 文件大小匹配")
        else:
            print("  ✗ 文件大小不匹配！")
            total_errors += 1

        # 验证SHA256
        if expected_sha256 and expected_sha256 == actual_sha256:
            print("  ✓ SHA256校验通过")
        elif not expected_sha256:
            print("  ⚠️  manifest中没有SHA256，跳过校验")
        else:
            print("  ✗ SHA256校验失败！")
            total_errors += 1

        print()

    print("=" * 40)
    if total_errors == 0:
        print("✓ 所有文件验证通过")
        return 0
    else:
        print(f"✗ 发现 {total_errors} 个错误")
        return 1


if __name__ == "__main__":
    sys.exit(main())
