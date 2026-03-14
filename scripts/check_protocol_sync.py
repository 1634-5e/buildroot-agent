#!/usr/bin/env python3
"""
协议同步检查脚本
验证 C 端 agent.h 和 Python 端 constants.py 的消息类型定义是否一致
"""

import re
import sys
from pathlib import Path


def parse_c_message_types(header_path: Path) -> dict[str, int]:
    """解析 C 头文件中的消息类型定义"""
    if not header_path.exists():
        print(f"错误: C 头文件不存在: {header_path}")
        return {}

    content = header_path.read_text()
    pattern = r"MSG_TYPE_(\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)"
    matches = re.findall(pattern, content)

    result = {}
    for name, value in matches:
        result[name] = int(value, 16) if value.startswith("0x") else int(value)

    return result


def parse_python_message_types(constants_path: Path) -> dict[str, int]:
    """解析 Python constants.py 中的消息类型定义"""
    if not constants_path.exists():
        print(f"错误: Python constants.py 不存在: {constants_path}")
        return {}

    content = constants_path.read_text()
    pattern = r"(\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)"
    matches = re.findall(pattern, content)

    result = {}
    for name, value in matches:
        result[name] = int(value, 16) if value.startswith("0x") else int(value)

    return result


def compare_protocols(c_types: dict, py_types: dict) -> list[str]:
    """比较两端协议定义，返回差异列表"""
    differences = []

    c_names = set(c_types.keys())
    py_names = set(py_types.keys())

    only_in_c = c_names - py_names
    only_in_py = py_names - c_names
    common = c_names & py_names

    for name in only_in_c:
        differences.append(f"C端独有: MSG_TYPE_{name} = 0x{c_types[name]:02X}")

    for name in only_in_py:
        differences.append(f"Python端独有: {name} = 0x{py_types[name]:02X}")

    for name in common:
        c_val = c_types[name]
        py_val = py_types[name]
        if c_val != py_val:
            differences.append(
                f"值不匹配: MSG_TYPE_{name}(C)=0x{c_val:02X} vs {name}(Py)=0x{py_val:02X}"
            )

    return differences


def main():
    project_root = Path(__file__).parent.parent

    c_header = project_root / "buildroot-agent" / "include" / "agent.h"
    py_constants = project_root / "buildroot-server" / "protocol" / "constants.py"

    print("=" * 60)
    print("协议同步检查")
    print("=" * 60)
    print(f"C 头文件: {c_header}")
    print(f"Python 文件: {py_constants}")
    print()

    c_types = parse_c_message_types(c_header)
    py_types = parse_python_message_types(py_constants)

    print(f"C 端消息类型数量: {len(c_types)}")
    print(f"Python 端消息类型数量: {len(py_types)}")
    print()

    differences = compare_protocols(c_types, py_types)

    if differences:
        print("发现差异:")
        print("-" * 40)
        for diff in differences:
            print(f"  {diff}")
        print()
        print(f"总计 {len(differences)} 个差异")
        return 1
    else:
        print("✓ 协议定义完全一致")
        return 0


if __name__ == "__main__":
    sys.exit(main())
