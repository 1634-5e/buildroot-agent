#!/usr/bin/env python3
"""
Buildroot Agent 云端服务器示例
使用 Python websockets 库实现

安装依赖: pip install websockets

运行: python3 server_example.py
"""

import asyncio
import json
import base64
import struct
import logging
from datetime import datetime
from typing import Dict, Set

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    print("请先安装 websockets: pip install websockets")
    exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 消息类型定义 (与Agent保持一致)
MSG_TYPE_HEARTBEAT = 0x01
MSG_TYPE_SYSTEM_STATUS = 0x02
MSG_TYPE_LOG_UPLOAD = 0x03
MSG_TYPE_SCRIPT_RECV = 0x04
MSG_TYPE_SCRIPT_RESULT = 0x05
MSG_TYPE_PTY_CREATE = 0x10
MSG_TYPE_PTY_DATA = 0x11
MSG_TYPE_PTY_RESIZE = 0x12
MSG_TYPE_PTY_CLOSE = 0x13
MSG_TYPE_FILE_REQUEST = 0x20
MSG_TYPE_FILE_DATA = 0x21
MSG_TYPE_CMD_REQUEST = 0x30
MSG_TYPE_CMD_RESPONSE = 0x31
MSG_TYPE_AUTH = 0xF0
MSG_TYPE_AUTH_RESULT = 0xF1

# 有效的认证Token (生产环境应从数据库读取)
VALID_TOKENS = {
    "test-token-123": "测试设备1",
    "your-auth-token": "默认设备",
}

# 已连接的设备
connected_devices: Dict[str, WebSocketServerProtocol] = {}
# PTY会话
pty_sessions: Dict[str, Dict[int, asyncio.Queue]] = {}


def create_message(msg_type: int, data: dict) -> bytes:
    """创建消息"""
    json_data = json.dumps(data).encode('utf-8')
    return bytes([msg_type]) + json_data


def parse_message(data: bytes) -> tuple:
    """解析消息"""
    if len(data) < 1:
        return None, None
    msg_type = data[0]
    try:
        json_data = json.loads(data[1:].decode('utf-8'))
    except:
        json_data = {}
    return msg_type, json_data


async def handle_auth(websocket: WebSocketServerProtocol, data: dict) -> bool:
    """处理认证"""
    device_id = data.get('device_id', 'unknown')
    token = data.get('token', '')
    version = data.get('version', 'unknown')
    
    if token in VALID_TOKENS:
        logger.info(f"设备认证成功: {device_id} (版本: {version})")
        connected_devices[device_id] = websocket
        pty_sessions[device_id] = {}
        
        response = create_message(MSG_TYPE_AUTH_RESULT, {
            'success': True,
            'message': f'欢迎, {VALID_TOKENS[token]}'
        })
        await websocket.send(response)
        return True
    else:
        logger.warning(f"设备认证失败: {device_id}, 无效Token")
        response = create_message(MSG_TYPE_AUTH_RESULT, {
            'success': False,
            'message': '认证失败: Token无效'
        })
        await websocket.send(response)
        return False


async def handle_heartbeat(device_id: str, data: dict):
    """处理心跳"""
    logger.debug(f"收到心跳: {device_id}")


async def handle_system_status(device_id: str, data: dict):
    """处理系统状态"""
    logger.info(f"设备状态 [{device_id}]: "
                f"CPU={data.get('cpu_usage', 0):.1f}%, "
                f"MEM={data.get('mem_used', 0):.0f}/{data.get('mem_total', 0):.0f}MB, "
                f"Load={data.get('load_1min', 0):.2f}")


async def handle_log_upload(device_id: str, data: dict):
    """处理日志上传"""
    filepath = data.get('filepath', 'unknown')
    if 'chunk' in data:
        chunk = data.get('chunk', 0)
        total = data.get('total_chunks', 1)
        logger.info(f"收到日志分片 [{device_id}]: {filepath} ({chunk+1}/{total})")
    elif 'line' in data:
        line = data.get('line', '')
        logger.info(f"实时日志 [{device_id}] {filepath}: {line}")
    elif 'lines' in data:
        lines = data.get('lines', 0)
        logger.info(f"收到日志 [{device_id}]: {filepath} ({lines} 行)")


async def handle_script_result(device_id: str, data: dict):
    """处理脚本执行结果"""
    script_id = data.get('script_id', 'unknown')
    exit_code = data.get('exit_code', -1)
    success = data.get('success', False)
    output = data.get('output', '')
    
    status = "成功" if success else "失败"
    logger.info(f"脚本执行{status} [{device_id}]: {script_id}, 退出码={exit_code}")
    if output:
        logger.info(f"输出:\n{output[:500]}")


async def handle_pty_data(device_id: str, data: dict):
    """处理PTY数据 (从设备到服务器)"""
    session_id = data.get('session_id', -1)
    pty_data = data.get('data', '')
    
    if device_id in pty_sessions and session_id in pty_sessions[device_id]:
        # 解码Base64
        try:
            decoded = base64.b64decode(pty_data).decode('utf-8', errors='replace')
            # 放入队列供终端显示
            await pty_sessions[device_id][session_id].put(decoded)
        except:
            pass


async def handle_pty_close(device_id: str, data: dict):
    """处理PTY关闭"""
    session_id = data.get('session_id', -1)
    reason = data.get('reason', 'unknown')
    logger.info(f"PTY会话关闭 [{device_id}]: session={session_id}, reason={reason}")
    
    if device_id in pty_sessions and session_id in pty_sessions[device_id]:
        del pty_sessions[device_id][session_id]


async def handle_message(websocket: WebSocketServerProtocol, device_id: str, data: bytes):
    """处理消息"""
    msg_type, json_data = parse_message(data)
    
    if msg_type == MSG_TYPE_HEARTBEAT:
        await handle_heartbeat(device_id, json_data)
    elif msg_type == MSG_TYPE_SYSTEM_STATUS:
        await handle_system_status(device_id, json_data)
    elif msg_type == MSG_TYPE_LOG_UPLOAD:
        await handle_log_upload(device_id, json_data)
    elif msg_type == MSG_TYPE_SCRIPT_RESULT:
        await handle_script_result(device_id, json_data)
    elif msg_type == MSG_TYPE_PTY_DATA:
        await handle_pty_data(device_id, json_data)
    elif msg_type == MSG_TYPE_PTY_CLOSE:
        await handle_pty_close(device_id, json_data)
    elif msg_type == MSG_TYPE_FILE_DATA:
        logger.info(f"收到文件数据 [{device_id}]: {json_data}")
    elif msg_type == MSG_TYPE_CMD_RESPONSE:
        logger.info(f"收到命令响应 [{device_id}]: {json_data}")
    else:
        logger.warning(f"未知消息类型: 0x{msg_type:02X}")


async def agent_handler(websocket: WebSocketServerProtocol, path: str):
    """WebSocket连接处理"""
    device_id = None
    authenticated = False
    
    remote = websocket.remote_address
    logger.info(f"新连接: {remote}")
    
    try:
        async for message in websocket:
            if isinstance(message, str):
                message = message.encode('utf-8')
            
            if not authenticated:
                # 等待认证
                msg_type, json_data = parse_message(message)
                if msg_type == MSG_TYPE_AUTH:
                    device_id = json_data.get('device_id', 'unknown')
                    authenticated = await handle_auth(websocket, json_data)
                    if not authenticated:
                        await websocket.close()
                        return
                else:
                    logger.warning(f"未认证的消息: 0x{msg_type:02X}")
            else:
                await handle_message(websocket, device_id, message)
    
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"连接关闭: {device_id or remote}")
    except Exception as e:
        logger.error(f"处理错误: {e}")
    finally:
        if device_id and device_id in connected_devices:
            del connected_devices[device_id]
            if device_id in pty_sessions:
                del pty_sessions[device_id]
            logger.info(f"设备断开: {device_id}")


async def send_to_device(device_id: str, msg_type: int, data: dict) -> bool:
    """发送消息到设备"""
    if device_id not in connected_devices:
        logger.warning(f"设备未连接: {device_id}")
        return False
    
    try:
        message = create_message(msg_type, data)
        await connected_devices[device_id].send(message)
        return True
    except Exception as e:
        logger.error(f"发送失败: {e}")
        return False


async def interactive_console():
    """交互式控制台"""
    await asyncio.sleep(2)  # 等待服务器启动
    
    print("\n" + "="*60)
    print("Buildroot Agent 云端控制台")
    print("="*60)
    print("命令:")
    print("  list              - 列出已连接设备")
    print("  status <device>   - 获取设备状态")
    print("  exec <device> <cmd> - 执行命令")
    print("  script <device>   - 发送测试脚本")
    print("  pty <device>      - 创建PTY会话")
    print("  tail <device> <file> - 查看日志")
    print("  quit              - 退出")
    print("="*60 + "\n")
    
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            # 非阻塞读取输入
            line = await loop.run_in_executor(None, input, "> ")
            line = line.strip()
            
            if not line:
                continue
            
            parts = line.split(maxsplit=2)
            cmd = parts[0].lower()
            
            if cmd == 'quit' or cmd == 'exit':
                print("退出...")
                break
            
            elif cmd == 'list':
                if connected_devices:
                    print("已连接设备:")
                    for dev_id in connected_devices:
                        print(f"  - {dev_id}")
                else:
                    print("没有已连接的设备")
            
            elif cmd == 'status' and len(parts) >= 2:
                device_id = parts[1]
                await send_to_device(device_id, MSG_TYPE_CMD_REQUEST, {
                    'cmd': 'status',
                    'request_id': 'status-1'
                })
                print(f"已请求设备状态: {device_id}")
            
            elif cmd == 'exec' and len(parts) >= 3:
                device_id = parts[1]
                command = parts[2]
                await send_to_device(device_id, MSG_TYPE_CMD_REQUEST, {
                    'cmd': command,
                    'request_id': f'exec-{datetime.now().timestamp()}'
                })
                print(f"已发送命令: {command}")
            
            elif cmd == 'script' and len(parts) >= 2:
                device_id = parts[1]
                await send_to_device(device_id, MSG_TYPE_SCRIPT_RECV, {
                    'script_id': 'test-script',
                    'content': '#!/bin/sh\necho "Hello from cloud!"\ndate\nuname -a\nfree -m\n',
                    'execute': True
                })
                print(f"已发送测试脚本到: {device_id}")
            
            elif cmd == 'pty' and len(parts) >= 2:
                device_id = parts[1]
                session_id = 1
                await send_to_device(device_id, MSG_TYPE_PTY_CREATE, {
                    'session_id': session_id,
                    'rows': 24,
                    'cols': 80
                })
                print(f"已请求创建PTY会话: {device_id}")
                print("(PTY交互功能需要在Web界面或专用客户端中使用)")
            
            elif cmd == 'tail' and len(parts) >= 3:
                device_id = parts[1]
                filepath = parts[2]
                await send_to_device(device_id, MSG_TYPE_FILE_REQUEST, {
                    'action': 'tail',
                    'filepath': filepath,
                    'lines': 50
                })
                print(f"已请求日志: {filepath}")
            
            else:
                print("未知命令，输入 'list' 查看已连接设备")
        
        except EOFError:
            break
        except Exception as e:
            print(f"错误: {e}")


async def main():
    """主函数"""
    host = "0.0.0.0"
    port = 8765
    
    logger.info(f"启动WebSocket服务器: ws://{host}:{port}/agent")
    
    # 启动WebSocket服务器
    server = await websockets.serve(
        agent_handler,
        host,
        port,
        ping_interval=30,
        ping_timeout=10
    )
    
    # 启动交互式控制台
    console_task = asyncio.create_task(interactive_console())
    
    try:
        await console_task
    except asyncio.CancelledError:
        pass
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已停止")
