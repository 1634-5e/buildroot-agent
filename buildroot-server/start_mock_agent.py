#!/usr/bin/env python3
"""
启动 Mock Agent - 连接到 Buildroot Server
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.fixtures.mock_agent import MockAgent


async def main():
    print("=" * 60)
    print("启动 Mock Agent")
    print("=" * 60)

    # 创建 Mock Agent
    agent = MockAgent(host="127.0.0.1", port=8766)
    print(f"Agent ID: {agent.device_id}")

    # 连接到 Server
    print("\n正在连接到 Server (127.0.0.1:8766)...")
    connected = await agent.connect()

    if not connected:
        print("❌ 连接失败")
        return

    print("✅ 连接成功")

    # 注册设备
    print("\n正在注册设备...")
    device_info = {
        "device_id": agent.device_id,
        "hostname": "test-buildroot-device",
        "ip": "192.168.1.100",
        "mac": "00:11:22:33:44:55",
        "version": "1.0.0",
        "kernel_version": "5.15.0",
        "cpu": "Intel Core i5",
        "memory": "8GB",
    }

    registered = await agent.register(device_info)

    if not registered:
        print("❌ 注册失败")
        await agent.disconnect()
        return

    print("✅ 注册成功")

    # 发送系统状态
    print("\n发送系统状态...")
    status = {
        "cpu_usage": 45.5,
        "memory_usage": 60.2,
        "disk_usage": 35.8,
        "uptime": 3600,
    }
    await agent.send_status(status)
    print("✅ 系统状态已发送")

    # 保持连接并发送心跳
    print("\n" + "=" * 60)
    print("Agent 运行中... (按 Ctrl+C 退出)")
    print("=" * 60)

    try:
        heartbeat_count = 0
        while agent.connected:
            await asyncio.sleep(10)  # 每 10 秒发送一次心跳
            heartbeat_count += 1
            print(f"[{heartbeat_count}] 发送心跳...")
            await agent.send_heartbeat()
            print(f"✅ 心跳已发送")

    except KeyboardInterrupt:
        print("\n\n正在断开连接...")
        await agent.disconnect()
        print("✅ 已断开连接")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n退出")