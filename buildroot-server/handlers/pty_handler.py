import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from database.repositories import PtySessionRepository, AuditLogRepository
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
            logger.debug(
                f"PTY session 无对应 console (可能已断开): device={device_id}, session={session_id}"
            )
    async def handle_pty_create(self, device_id: str, data: dict) -> None:
        session_id = int(data.get("session_id", -1))
        status = data.get("status", "unknown")
        rows = data.get("rows", 24)
        cols = data.get("cols", 80)

        logger.info(
            f"PTY会话创建 [{device_id}]: session={session_id}, "
            f"status={status}, size={cols}x{rows}"
        )

        if device_id not in self.conn_mgr.pty_sessions:
            self.conn_mgr.pty_sessions[device_id] = {}

        if session_id not in self.conn_mgr.pty_sessions[device_id]:
            import asyncio

            self.conn_mgr.pty_sessions[device_id][session_id] = asyncio.Queue()

        target_console_id = None
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
            logger.debug(
                f"PTY create 无对应 console (可能已断开): device={device_id}, session={session_id}"
            )
        # 数据库操作：记录 PTY 会话创建
        # 仅当 console_id 有效时记录
        if target_console_id:
            try:
                pty_session_id = await PtySessionRepository.insert(
                    session_id=session_id,
                    device_id=device_id,
                    console_id=target_console_id,
                    rows=rows,
                    cols=cols,
                    status='active' if status == 'created' else status,
                )
                logger.info(
                    f"[DB] PTY会话已记录: session_id={session_id}, pty_id={pty_session_id}"
                )

                # 记录审计日志（异步，不阻塞主流程）
                asyncio.create_task(AuditLogRepository.insert(
                    event_type="pty_session",
                    action="create_session",
                    actor_type="web_console",
                    actor_id=target_console_id,
                    device_id=device_id,
                    resource_type="pty_session",
                    resource_id=str(session_id),
                    status="success",
                    details={
                        "session_id": session_id,
                        "size": f"{cols}x{rows}",
                    },
                ))
            except Exception as e:
                logger.error(f"[DB] 记录 PTY 会话失败: {e}")
        else:
            logger.debug(f"[DB] 跳过PTY会话记录: 无有效console_id, session={session_id}")

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
            logger.debug(
                f"PTY resize 无对应 console (可能已断开): device={device_id}, session={session_id}"
            )
    async def handle_pty_close(self, device_id: str, data: dict) -> None:
        session_id = int(data.get("session_id", -1))
        reason = data.get("reason", "unknown")

        logger.info(f"PTY会话关闭 [{device_id}]: session={session_id}, reason={reason}")

        target_console_id = None
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
            logger.debug(
                f"PTY close 无对应 console (可能已断开): device={device_id}, session={session_id}"
            )
        # 数据库操作：更新 PTY 会话关闭状态
        if (
            device_id in self.conn_mgr.pty_sessions
            and session_id in self.conn_mgr.pty_sessions[device_id]
        ):
            del self.conn_mgr.pty_sessions[device_id][session_id]

        try:
            await PtySessionRepository.update_closed(
                session_id=session_id,
                device_id=device_id,
                closed_at=datetime.now(),
                closed_reason=reason,
                status="closed",
            )
            logger.info(f"[DB] PTY会话已关闭: session_id={session_id}")

            # 记录审计日志（异步，不阻塞主流程）
            console_id = target_console_id
            asyncio.create_task(AuditLogRepository.insert(
                event_type="pty_session",
                action="close_session",
                actor_type="web_console",
                actor_id=console_id,
                device_id=device_id,
                resource_type="pty_session",
                resource_id=str(session_id),
                status="success",
                details={
                    "session_id": session_id,
                    "reason": reason,
                },
            ))
        except Exception as e:
            logger.error(f"[DB] 更新 PTY 会话关闭状态失败: {e}")
