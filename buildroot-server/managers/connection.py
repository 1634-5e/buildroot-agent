import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Set, Any, Optional
from websockets.server import WebSocketServerProtocol

from models.file_transfer import FileTransferSession

logger = logging.getLogger(__name__)


class ConnectionManager:
    """连接管理器"""

    def __init__(self, file_transfer_manager):
        self.connected_devices: Dict[str, Dict[str, Any]] = {}
        self.web_consoles: Set[WebSocketServerProtocol] = set()
        self.console_info: Dict[WebSocketServerProtocol, Dict[str, Any]] = {}
        self.pty_sessions: Dict[str, Dict[int, asyncio.Queue]] = {}
        self.request_sessions: Dict[str, Dict[str, str]] = {}
        self.file_transfer = file_transfer_manager

    def add_device(
        self, device_id: str, connection: Any, conn_type: str = "websocket"
    ) -> None:
        self.connected_devices[device_id] = {
            "type": conn_type,
            "connection": connection,
        }
        self.pty_sessions[device_id] = {}

        logger.info(
            f"[ADD_DEVICE] 设备已添加 - device_id={device_id}, "
            f"conn_type={conn_type}, "
            f"当前设备数={len(self.connected_devices)}, "
            f"所有设备={list(self.connected_devices.keys())}"
        )

    def remove_device(self, device_id: str) -> None:
        existed = device_id in self.connected_devices
        self.connected_devices.pop(device_id, None)
        self.pty_sessions.pop(device_id, None)

        if existed:
            logger.info(
                f"[REMOVE_DEVICE] 设备已移除 - device_id={device_id}, "
                f"剩余设备数={len(self.connected_devices)}, "
                f"所有设备={list(self.connected_devices.keys())}"
            )
        else:
            logger.warning(
                f"[REMOVE_DEVICE] 尝试移除不存在的设备 - device_id={device_id}"
            )

    def add_console(self, websocket: WebSocketServerProtocol) -> None:
        console_id = str(uuid.uuid4())[:8]
        self.web_consoles.add(websocket)
        self.console_info[websocket] = {
            "console_id": console_id,
            "device_id": None,
            "session_ids": set(),
            "connected_time": time.time(),
        }
        logger.info(f"Web控制台连接: console_id={console_id}")

    def remove_console(
        self, websocket: WebSocketServerProtocol
    ) -> tuple[Optional[str], Set[int]]:
        console_id = self.console_info.get(websocket, {}).get("console_id", "unknown")
        device_id = None
        session_ids = set()

        if websocket in self.console_info:
            device_id = self.console_info[websocket].get("device_id")
            session_ids = self.console_info[websocket].get("session_ids", set()).copy()
            self.web_consoles.discard(websocket)
            self.console_info.pop(websocket, None)

        logger.info(
            f"Web控制台断开: console_id={console_id}, device_id={device_id}, sessions={session_ids}"
        )
        return device_id, session_ids

    def set_console_device(
        self, websocket: WebSocketServerProtocol, device_id: str
    ) -> None:
        if websocket in self.console_info:
            old_device = self.console_info[websocket].get("device_id")
            self.console_info[websocket]["device_id"] = device_id
            logger.info(
                f"控制台 {self.console_info[websocket]['console_id']} 切换设备: {old_device} -> {device_id}"
            )

    def add_console_session(
        self, websocket: WebSocketServerProtocol, session_id: int
    ) -> None:
        if websocket in self.console_info:
            self.console_info[websocket]["session_ids"].add(session_id)

    def get_console_by_session(
        self, device_id: str, session_id: int
    ) -> Optional[WebSocketServerProtocol]:
        for websocket, info in self.console_info.items():
            if info.get("device_id") == device_id and session_id in info.get(
                "session_ids", set()
            ):
                return websocket
        logger.warning(
            f"get_console_by_session未找到: device_id={device_id}, session_id={session_id}, "
            f"已注册sessions: {[(info.get('device_id'), info.get('session_ids')) for info in self.console_info.values()]}"
        )
        return None

    def add_request_session(
        self, request_id: str, console_id: str, device_id: str
    ) -> None:
        if not request_id:
            return
        self.request_sessions[request_id] = {
            "console_id": console_id,
            "device_id": device_id,
        }
        logger.debug(
            f"注册request_session: request_id={request_id}, console_id={console_id}, device_id={device_id}"
        )

    def get_console_by_request(
        self, request_id: str
    ) -> Optional[WebSocketServerProtocol]:
        if not request_id or request_id not in self.request_sessions:
            return None
        req_info = self.request_sessions[request_id]
        target_console_id = req_info.get("console_id")
        target_device_id = req_info.get("device_id")

        for websocket, info in self.console_info.items():
            if (
                info.get("console_id") == target_console_id
                and info.get("device_id") == target_device_id
            ):
                return websocket
        return None

    def get_console_info(
        self, websocket: WebSocketServerProtocol
    ) -> Optional[Dict[str, Any]]:
        return self.console_info.get(websocket)

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        return self.connected_devices.get(device_id)

    def is_device_connected(self, device_id: str) -> bool:
        return device_id in self.connected_devices

    def get_all_devices(self) -> list[Dict[str, Any]]:
        logger.debug(
            f"[GET_ALL_DEVICES] 查询设备列表 - "
            f"connected_devices数量={len(self.connected_devices)}, "
            f"设备IDs={list(self.connected_devices.keys())}"
        )

        devices = []
        for device_id, dev_info in self.connected_devices.items():
            conn = dev_info["connection"]
            conn_type = dev_info["type"]
            remote_addr = self._get_remote_address(conn, conn_type)
            devices.append(
                {
                    "device_id": device_id,
                    "connected_time": datetime.now().isoformat(),
                    "status": "online",
                    "connection_type": conn_type,
                    "remote_addr": remote_addr,
                }
            )

        logger.debug(
            f"[GET_ALL_DEVICES] 返回设备列表 - 数量={len(devices)}, "
            f"设备IDs={[d['device_id'] for d in devices]}"
        )

        return devices

    def _get_remote_address(self, connection: Any, conn_type: str) -> str:
        try:
            if conn_type == "websocket":
                remote = getattr(connection, "remote_address", "unknown")
                return remote[0] if isinstance(remote, tuple) else str(remote)
            elif conn_type == "socket":
                writer = connection
                addr = writer.get_extra_info("peername")
                return f"{addr[0]}:{addr[1]}" if addr else "unknown"
            else:
                return "unknown"
        except:
            return "unknown"
