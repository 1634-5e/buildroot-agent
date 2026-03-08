import asyncio
import json
import logging
import websockets
import secrets
from websockets.server import WebSocketServerProtocol
from typing import Optional

from protocol.constants import MessageType
from protocol.codec import MessageCodec
from database.repositories import (
    DeviceRepository,
    WebConsoleSessionRepository,
    AuditLogRepository,
)
from server.auth import validate_token
from datetime import datetime


logger = logging.getLogger(__name__)


class WebSocketHandler:
    """WebSocket 连接处理器"""

    def __init__(self, conn_mgr, msg_handler):
        self.conn_mgr = conn_mgr
        self.msg_handler = msg_handler

    @staticmethod
    def generate_token(user_id: str = "anonymous") -> str:
        """生成认证 token"""
        token = secrets.token_urlsafe(32)
        VALID_TOKENS[token] = (user_id, asyncio.get_event_loop().time())
        logger.info(f"[AUTH] 生成 token: {token[:8]}... for user: {user_id}")
        return token

    @staticmethod
    def validate_token(token: str) -> Optional[str]:
        """验证 token，返回 user_id 或 None"""
        if not token:
            return None
        
        # 清理过期 token
        current_time = asyncio.get_event_loop().time()
        expired = [t for t, (_, created) in VALID_TOKENS.items() 
                   if current_time - created > TOKEN_EXPIRY]
        for t in expired:
            del VALID_TOKENS[t]
        
        if token in VALID_TOKENS:
            user_id, _ = VALID_TOKENS[token]
            return user_id
        return None

    async def agent_handler(self, websocket: WebSocketServerProtocol) -> None:
        try:
            remote = getattr(websocket, "remote_address", "unknown")
        except Exception:
            remote = "unknown"
        logger.info(f"新连接: {remote}")

        # === 认证检查 ===
        auth_token = None
        try:
            # 从 URL query 参数获取 token
            path = getattr(websocket, "path", "")
            if "?" in path:
                query = path.split("?", 1)[1]
                params = dict(p.split("=") for p in query.split("&") if "=" in p)
                auth_token = params.get("token")
            
            # 从 headers 获取 token
            if not auth_token:
                request_headers = getattr(websocket, "request_headers", {})
                if request_headers:
                    auth_token = request_headers.get("x-auth-token", "")
        except Exception as e:
            logger.debug(f"获取认证信息失败: {e}")

        # 验证 token（开发模式可选）
        # 生产环境应该强制验证
        user_id = self.validate_token(auth_token) if auth_token else None
        
        if not user_id:
            # 开发模式：允许无认证连接，但记录警告
            logger.warning(f"[AUTH] 未认证连接: {remote} (开发模式允许)")
            user_id = f"anonymous_{secrets.token_hex(4)}"
        else:
            logger.info(f"[AUTH] 认证成功: {user_id}")

        self.conn_mgr.add_console(websocket)

        console_id = None
        console_info = self.conn_mgr.get_console_info(websocket)
        if console_info:
            console_id = console_info.get("console_id")

        device_id: str | None = None

        user_agent = None
        try:
            request_headers = getattr(websocket, "request_headers", {})
            if request_headers:
                user_agent = request_headers.get("user-agent", "")

            remote_addr = getattr(websocket, "remote_address", "unknown")
            if isinstance(remote_addr, tuple):
                remote_addr = remote_addr[0] if remote_addr else "unknown"
            else:
                remote_addr = str(remote_addr)

            if console_id:
                user_id = f"web_{console_id}"
        except Exception as e:
            logger.debug(f"获取用户信息失败: {e}")

        if console_id:
            try:
                await WebConsoleSessionRepository.insert(
                    console_id=console_id,
                    remote_addr=remote_addr,
                    user_id=user_id,
                    user_agent=user_agent,
                )
                logger.info(
                    f"[DB] Web控制台会话已创建: console_id={console_id}, user_id={user_id}"
                )
            except Exception as e:
                logger.error(f"[DB] 创建Web控制台会话失败: {e}")

        try:
            if not hasattr(websocket, "__aiter__"):
                logger.error("WebSocket不支持异步迭代")
                return

            async for message in websocket:
                if len(message) < 1:
                    continue

                msg_type = message[0]

                try:
                    logger.debug(
                        f"[RECV_WEB] raw_hex={message.hex()[:50]}...{message.hex()[-30:] if len(message.hex()) > 80 else ''}, len={len(message)}"
                    )
                    json_len = (message[1] << 8) | message[2]
                    logger.debug(
                        f"[RECV_WEB] msg_type=0x{message[0]:02X}, json_len={json_len}, len_high={message[1]:02X}, len_low={message[2]:02X}"
                    )
                    json_str = message[3 : 3 + json_len].decode("utf-8")
                    json_data = json.loads(json_str)

                    console_id = json_data.pop("console_id", None)
                    device_id = json_data.get("device_id")

                    console_info = self.conn_mgr.get_console_info(websocket)
                    if console_info:
                        if device_id:
                            self.conn_mgr.set_console_device(websocket, device_id)
                        session_id = json_data.get("session_id")
                        if session_id:
                            try:
                                self.conn_mgr.add_console_session(
                                    websocket, int(session_id)
                                )
                            except (ValueError, TypeError):
                                logger.warning(f"无效的session_id: {session_id}")
                        request_id = json_data.get("request_id")
                        if request_id and device_id:
                            self.conn_mgr.add_request_session(
                                request_id,
                                console_info.get("console_id", ""),
                                device_id,
                            )

                    device_info = device_id if device_id else "所有设备"
                    actual_console_id = (
                        console_info.get("console_id", console_id)
                        if console_info
                        else console_id
                    )
                    logger.info(
                        f"Web控制台 [{actual_console_id}] 收到消息 [0x{msg_type:02X}] for device: {device_info}, data: {json_str[:200]}"
                    )

                    # Special handling for status command: query from database instead of forwarding to agent
                    if (
                        msg_type == MessageType.CMD_REQUEST
                        and json_data.get("cmd") == "status"
                    ):
                        request_id = json_data.get("request_id")
                        logger.info(
                            f"Web控制台请求设备状态 [{device_id}], 从数据库查询(跳过缓存), request_id={request_id}"
                        )

                        try:
                            device = await DeviceRepository.get_by_device_id(
                                device_id, use_cache=False
                            )
                            if device and device.get("current_status"):
                                response = MessageCodec.encode(
                                    MessageType.CMD_RESPONSE,
                                    {
                                        "device_id": device_id,
                                        "request_id": request_id,
                                        "status": "completed",
                                        "exit_code": 0,
                                        "success": True,
                                        "status_timestamp": device.get(
                                            "last_status_reported_at"
                                        ).isoformat()
                                        if device.get("last_status_reported_at")
                                        else None,
                                        **device["current_status"],
                                    },
                                )
                                if hasattr(websocket, "send") and callable(
                                    getattr(websocket, "send", None)
                                ):
                                    await websocket.send(response)
                                    logger.info(
                                        f"设备状态已从数据库发送到web控制台: {device_id}"
                                    )
                            else:
                                logger.warning(
                                    f"设备[{device_id}]没有缓存的status数据，转发到agent"
                                )
                                success = await self.msg_handler.send_to_device(
                                    device_id, msg_type, json_data
                                )
                                if success:
                                    logger.info(f"消息已转发到设备 {device_id}")
                                else:
                                    logger.warning(f"转发消息到设备失败: {device_id}")
                        except Exception as e:
                            logger.error(f"查询设备状态失败: {e}, 转发到agent")
                            success = await self.msg_handler.send_to_device(
                                device_id, msg_type, json_data
                            )
                            if success:
                                logger.info(f"消息已转发到设备 {device_id}")
                            else:
                                logger.warning(f"转发消息到设备失败: {device_id}")
                        continue

                    # Special handling for ping command
                    if (
                        msg_type == MessageType.CMD_REQUEST
                        and json_data.get("cmd") == "ping"
                    ):
                        request_id = json_data.get("request_id")
                        logger.info(
                            f"Web控制台请求Ping状态 [{device_id}], 从数据库查询, request_id={request_id}"
                        )

                        try:
                            device = await DeviceRepository.get_by_device_id(
                                device_id, use_cache=False
                            )
                            if (
                                device
                                and device.get("current_status")
                                and device["current_status"].get("ping_status")
                            ):
                                ping_status = device["current_status"]["ping_status"]
                                response = MessageCodec.encode(
                                    MessageType.CMD_RESPONSE,
                                    {
                                        "device_id": device_id,
                                        "request_id": request_id,
                                        "status": "completed",
                                        "exit_code": 0,
                                        "success": True,
                                        **ping_status,
                                    },
                                )
                                if hasattr(websocket, "send") and callable(
                                    getattr(websocket, "send", None)
                                ):
                                    await websocket.send(response)
                                    logger.info(
                                        f"Ping状态已从数据库发送到web控制台: {device_id}"
                                    )
                            else:
                                logger.warning(
                                    f"设备[{device_id}]没有缓存的ping数据，转发到agent"
                                )
                                success = await self.msg_handler.send_to_device(
                                    device_id, msg_type, json_data
                                )
                                if success:
                                    logger.info(f"消息已转发到设备 {device_id}")
                                else:
                                    logger.warning(f"转发消息到设备失败: {device_id}")
                        except Exception as e:
                            logger.error(f"查询Ping状态失败: {e}, 转发到agent")
                            success = await self.msg_handler.send_to_device(
                                device_id, msg_type, json_data
                            )
                            if success:
                                logger.info(f"消息已转发到设备 {device_id}")
                            else:
                                logger.warning(f"转发消息到设备失败: {device_id}")
                        continue
                    
                    # 服务端本地处理的消息类型
                    SERVER_HANDLED_TYPES = (
                        MessageType.DEVICE_LIST,
                        MessageType.DEVICE_DISCONNECT,
                        MessageType.DEVICE_UPDATE,
                    )

                    if device_id and msg_type not in SERVER_HANDLED_TYPES:
                        logger.info(
                            f"Web控制台消息 [0x{msg_type:02X}] 转发到设备: {device_id}"
                        )
                        success = await self.msg_handler.send_to_device(
                            device_id, msg_type, json_data
                        )
                        if success:
                            logger.info(f"消息已转发到设备 {device_id}")
                        else:
                            logger.warning(f"转发消息到设备失败: {device_id}")
                        continue

                    # 服务端本地处理的消息
                    if msg_type == MessageType.DEVICE_LIST:
                        page = json_data.get("page", 0)
                        page_size = json_data.get("page_size", 20)
                        search_keyword = json_data.get("search_keyword", "").lower()
                        sort_by = json_data.get("sort_by", "device_id")
                        sort_order = json_data.get("sort_order", "asc")

                        all_devices = self.conn_mgr.get_all_devices()

                        filtered_devices = all_devices
                        if search_keyword:
                            filtered_devices = [
                                d
                                for d in all_devices
                                if search_keyword in d.get("device_id", "").lower()
                            ]

                        if sort_by:
                            reverse = sort_order.lower() == "desc"
                            filtered_devices.sort(
                                key=lambda x: x.get(sort_by, ""),
                                reverse=reverse,
                            )

                        total_count = len(filtered_devices)
                        start_index = page * page_size
                        end_index = start_index + page_size
                        paged_devices = filtered_devices[start_index:end_index]

                        response = MessageCodec.encode(
                            MessageType.DEVICE_LIST,
                            {
                                "devices": paged_devices,
                                "total_count": total_count,
                                "page": page,
                                "page_size": page_size,
                            },
                        )
                        if hasattr(websocket, "send") and callable(
                            getattr(websocket, "send", None)
                        ):
                            await websocket.send(response)
                            logger.info("设备列表已发送到web控制台")

                    elif msg_type == MessageType.DEVICE_UPDATE:
                        device_id = json_data.get("device_id")
                        name = json_data.get("name")
                        tags = json_data.get("tags")

                        logger.info(
                            f"Web控制台更新设备信息: device_id={device_id}, name={name}, tags={tags}"
                        )

                        try:
                            await DeviceRepository.update_device_info(
                                device_id=device_id,
                                name=name,
                                tags=tags,
                            )
                            logger.info(f"[DB] 设备信息已更新: {device_id}")

                            response = MessageCodec.encode(
                                MessageType.DEVICE_UPDATE,
                                {
                                    "success": True,
                                    "device_id": device_id,
                                    "message": "设备信息已更新",
                                },
                            )
                            if hasattr(websocket, "send") and callable(
                                getattr(websocket, "send", None)
                            ):
                                await websocket.send(response)

                            asyncio.create_task(
                                AuditLogRepository.insert(
                                    event_type="device_update",
                                    action="update_device_info",
                                    actor_type="web_console",
                                    actor_id=console_id,
                                    device_id=device_id,
                                    resource_type="device",
                                    resource_id=device_id,
                                    status="success",
                                    details={
                                        "name": name,
                                        "tags": tags,
                                    },
                                )
                            )
                        except Exception as e:
                            logger.error(f"[DB] 更新设备信息失败: {e}")
                            response = MessageCodec.encode(
                                MessageType.DEVICE_UPDATE,
                                {
                                    "success": False,
                                    "device_id": device_id,
                                    "message": f"更新失败: {str(e)}",
                                },
                            )
                            if hasattr(websocket, "send") and callable(
                                getattr(websocket, "send", None)
                            ):
                                await websocket.send(response)
                except Exception as e:
                    logger.error(f"Web控制台消息处理失败: {e}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Web控制台断开: {remote}, code: {e.code}, reason: {e.reason}")
            device_id, session_ids = await self.conn_mgr.remove_console(websocket)
            if (
                device_id
                and session_ids
                and await self.conn_mgr.is_device_connected(device_id)
            ):
                for session_id in session_ids:
                    await self.msg_handler.send_to_device(
                        device_id,
                        MessageType.PTY_CLOSE,
                        {
                            "session_id": session_id,
                            "reason": "console disconnected",
                        },
                    )
        except Exception as e:
            logger.error(f"连接处理错误: {e}")
        finally:
            device_id, session_ids = await self.conn_mgr.remove_console(websocket)
            if (
                device_id
                and session_ids
                and await self.conn_mgr.is_device_connected(device_id)
            ):
                for session_id in session_ids:
                    await self.msg_handler.send_to_device(
                        device_id,
                        MessageType.PTY_CLOSE,
                        {
                            "session_id": session_id,
                            "reason": "console disconnected",
                        },
                    )

            if console_id:
                try:
                    await WebConsoleSessionRepository.update_closed(
                        console_id=console_id,
                        disconnected_at=datetime.now(),
                        is_active=False,
                    )
                    logger.info(f"[DB] Web控制台会话已关闭: console_id={console_id}")
                except Exception as e:
                    logger.error(f"[DB] 更新Web控制台会话失败: {e}")