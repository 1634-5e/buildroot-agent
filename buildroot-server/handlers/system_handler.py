import logging
from websockets.server import WebSocketServerProtocol

from handlers.base import BaseHandler
from protocol.constants import MessageType
from protocol.models import Heartbeat, SystemStatus, LogUpload, ScriptRecv, ScriptResult

logger = logging.getLogger(__name__)


class SystemHandler(BaseHandler):
    async def handle_heartbeat(self, device_id: str, data: dict) -> None:
        logger.debug(f"收到心跳: {device_id}")

    async def handle_system_status(self, device_id: str, data: dict) -> None:
        logger.info(
            f"设备状态 [{device_id}]: "
            f"CPU={data.get('cpu_usage', 0):.1f}%, "
            f"MEM={data.get('mem_used', 0):.0f}/{data.get('mem_total', 0):.0f}MB, "
            f"Load={data.get('load_1min', 0):.2f}"
        )

        request_id = data.get("request_id")
        if request_id:
            status_data = {"device_id": device_id, **data}
            await self.unicast_by_request_id(
                MessageType.SYSTEM_STATUS,
                status_data,
                request_id,
            )

    async def handle_log_upload(self, device_id: str, data: dict) -> None:
        filepath = data.get("filepath", "unknown")
        if "chunk" in data:
            chunk = data.get("chunk", 0)
            total = data.get("total_chunks", 1)
            logger.info(f"收到日志分片 [{device_id}]: {filepath} ({chunk + 1}/{total})")
        elif "line" in data:
            line = data.get("line", "")
            logger.info(f"实时日志 [{device_id}] {filepath}: {line}")
        elif "lines" in data:
            lines = data.get("lines", 0)
            logger.info(f"收到日志 [{device_id}]: {filepath} ({lines} 行)")

    async def handle_script_result(self, device_id: str, data: dict) -> None:
        script_id = data.get("script_id", "unknown")
        exit_code = data.get("exit_code", -1)
        success = data.get("success", False)
        output = data.get("output", "")

        status = "成功" if success else "失败"
        logger.info(f"脚本执行{status} [{device_id}]: {script_id}, 退出码={exit_code}")
        if output:
            logger.info(f"输出:\n{output[:500]}")
