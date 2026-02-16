import logging

from handlers.base import BaseHandler
from protocol.constants import MessageType
from protocol.models import PtyCreate, PtyData, PtyResize, PtyClose

logger = logging.getLogger(__name__)


class PtyHandler(BaseHandler):
    async def handle_pty_data(self, device_id: str, data: dict) -> None:
        session_id = int(data.get("session_id", -1))
        pty_data = data.get("data", "")

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            try:
                await self.broadcast_to_web_consoles(
                    MessageType.PTY_DATA,
                    {
                        "device_id": device_id,
                        "session_id": session_id,
                        "data": pty_data,
                    },
                    target_console_id=target_console_id,
                )
            except Exception:
                pass
        else:
            logger.warning(
                f"未找到PTY session对应的console: device={device_id}, session={session_id}"
            )

    async def handle_pty_create(self, device_id: str, data: dict) -> None:
        session_id = int(data.get("session_id", -1))
        status = data.get("status", "unknown")
        rows = data.get("rows", 24)
        cols = data.get("cols", 80)

        logger.info(
            f"PTY会话创建 [{device_id}]: session={session_id}, status={status}, size={cols}x{rows}"
        )

        if device_id not in self.conn_mgr.pty_sessions:
            self.conn_mgr.pty_sessions[device_id] = {}

        if session_id not in self.conn_mgr.pty_sessions[device_id]:
            import asyncio

            self.conn_mgr.pty_sessions[device_id][session_id] = asyncio.Queue()

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            await self.broadcast_to_web_consoles(
                MessageType.PTY_CREATE,
                {"device_id": device_id, **data},
                target_console_id=target_console_id,
            )
        else:
            logger.warning(
                f"未找到PTY会话对应的web控制台 [{device_id}]: session={session_id}"
            )

    async def handle_pty_resize(self, device_id: str, data: dict) -> None:
        session_id = int(data.get("session_id", -1))
        rows = data.get("rows", 24)
        cols = data.get("cols", 80)

        logger.info(
            f"PTY调整大小 [{device_id}]: session={session_id}, size={cols}x{rows}"
        )

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            await self.broadcast_to_web_consoles(
                MessageType.PTY_RESIZE,
                {"device_id": device_id, **data},
                target_console_id=target_console_id,
            )
        else:
            logger.warning(
                f"未找到PTY resize对应的web控制台 [{device_id}]: session={session_id}"
            )

    async def handle_pty_close(self, device_id: str, data: dict) -> None:
        session_id = int(data.get("session_id", -1))
        reason = data.get("reason", "unknown")
        logger.info(f"PTY会话关闭 [{device_id}]: session={session_id}, reason={reason}")

        target_console = self.conn_mgr.get_console_by_session(device_id, session_id)
        if target_console:
            console_info = self.conn_mgr.get_console_info(target_console)
            target_console_id = console_info.get("console_id") if console_info else None
            await self.broadcast_to_web_consoles(
                MessageType.PTY_CLOSE,
                {"device_id": device_id, **data},
                target_console_id=target_console_id,
            )
        else:
            logger.warning(
                f"未找到PTY close对应的web控制台 [{device_id}]: session={session_id}"
            )

        if (
            device_id in self.conn_mgr.pty_sessions
            and session_id in self.conn_mgr.pty_sessions[device_id]
        ):
            del self.conn_mgr.pty_sessions[device_id][session_id]
