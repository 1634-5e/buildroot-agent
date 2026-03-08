import asyncio
import logging

from database.repositories import DeviceRepository
from database.batch_buffer import (
    get_audit_log_buffer,
    get_ping_history_buffer,
)
from handlers.base import BaseHandler
from protocol.constants import MessageType

logger = logging.getLogger(__name__)


class PingHandler(BaseHandler):
    async def handle_ping_status(self, device_id: str, data: dict) -> None:
        timestamp = data.get("timestamp", 0)
        results = data.get("results", [])

        result_count = len(results)

        if result_count > 0:
            first_result = results[0]
            logger.info(
                f"Ping状态 [{device_id}]: "
                f"{result_count}个目标, "
                f"状态={first_result.get('status', 0)}"
            )
        else:
            logger.warning(f"Ping状态 [{device_id}]: 无结果")

        try:
            await DeviceRepository.update_current_status(
                device_id=device_id,
                current_status={"ping_status": data},
            )
            logger.debug(f"[DB] Ping状态已更新: {device_id}")
        except Exception as e:
            logger.error(f"[DB] 更新Ping状态失败: {e}")

        # 存储 ping 历史记录到专门的 ping_history 表
        ping_buffer = get_ping_history_buffer()
        for result in results:
            asyncio.create_task(
                ping_buffer.add_ping(
                    device_id=device_id,
                    target_ip=result.get("ip", ""),
                    status=result.get("status", 0),
                    avg_time=result.get("avg_time"),
                    min_time=result.get("min_time"),
                    max_time=result.get("max_time"),
                    packet_loss=result.get("packet_loss"),
                    packets_sent=result.get("packets_sent", 0),
                    packets_received=result.get("packets_received", 0),
                    raw_data=result,
                )
            )

        buffer = get_audit_log_buffer()
        asyncio.create_task(
            buffer.add_log(
                event_type="ping_status",
                action="report_ping",
                actor_type="device",
                actor_id=device_id,
                device_id=device_id,
                status="success",
                details={
                    "result_count": result_count,
                    "timestamp": timestamp,
                },
            )
        )

        # 广播给所有Web控制台
        status_data = {"device_id": device_id, **data}
        await self.broadcast_to_web_consoles(
            MessageType.PING_STATUS,
            status_data,
        )
