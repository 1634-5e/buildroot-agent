import asyncio
import websockets
import json


async def test_device():
    uri = "ws://localhost:8765/agent"
    async with websockets.connect(uri) as websocket:
        # 发送认证消息
        auth_msg = {
            "device_id": "test-device",
            "token": "test-token-123",
            "version": "1.0",
        }
        await websocket.send(bytes([0xF0]) + json.dumps(auth_msg).encode("utf-8"))

        # 接收认证结果
        response = await websocket.recv()
        msg_type = response[0]
        # 处理response可能是bytes或str的情况
        response_data = response[1:]
        if isinstance(response_data, bytes):
            json_str = response_data.decode("utf-8")
        else:
            json_str = response_data
        json_data = json.loads(json_str)
        print(f"认证结果: 类型={msg_type}, 数据={json_data}")

        # 保持连接并定期发送心跳
        for i in range(5):  # 发送5次心跳
            await asyncio.sleep(5)
            heartbeat = {"timestamp": 123456 + i}
            await websocket.send(bytes([0x01]) + json.dumps(heartbeat).encode("utf-8"))
            print(f"已发送心跳 {i + 1}")

        print("测试完成，断开连接")


if __name__ == "__main__":
    asyncio.run(test_device())
