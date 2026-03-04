#!/usr/bin/env python3
"""
Buildroot Agent Server - Batch Write Buffer
批量写入缓冲器，用于高频写入表（device_status_history, audit_logs）
"""

import asyncio
import logging
from typing import List, Any, Optional
from dataclasses import dataclass, field

from database.models import DeviceStatusHistory, AuditLog, PingHistory
from database.db_manager import db_manager

logger = logging.getLogger(__name__)


@dataclass
class BufferConfig:
    """缓冲器配置"""

    max_size: int = 100  # 最大缓冲条目数
    flush_interval: float = 5.0  # 自动刷新间隔（秒）
    max_retries: int = 3  # 批量写入失败重试次数


@dataclass
class BatchBuffer:
    """批量写入缓冲器基类"""

    config: BufferConfig
    buffer: List[Any] = field(default_factory=list)
    flush_task: Optional[asyncio.Task] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = False

    async def add(self, item: Any) -> None:
        """添加条目到缓冲区"""
        if self.closed:
            logger.warning("Buffer is closed, item dropped")
            return

        async with self.lock:
            self.buffer.append(item)
            logger.debug(f"Added item to buffer, size: {len(self.buffer)}")

            if len(self.buffer) >= self.config.max_size:
                await self._flush()

    async def _flush(self) -> None:
        """刷新缓冲区（批量写入数据库）"""
        if not self.buffer:
            return

        items = self.buffer.copy()
        self.buffer.clear()

        if not items:
            return

        logger.info(f"Flushing {len(items)} items...")

        for attempt in range(self.config.max_retries):
            try:
                async with db_manager.get_session() as session:
                    for item in items:
                        session.add(item)
                    await session.commit()
                logger.info(f"Successfully flushed {len(items)} items")
                break
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    logger.error(
                        f"Failed to flush buffer after {self.config.max_retries} attempts: {e}"
                    )
                else:
                    logger.warning(
                        f"Flush attempt {attempt + 1} failed, retrying...: {e}"
                    )
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避

    async def _auto_flush_loop(self) -> None:
        """自动刷新循环"""
        while not self.closed:
            try:
                await asyncio.sleep(self.config.flush_interval)
                if self.buffer:
                    async with self.lock:
                        await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto flush loop: {e}")

    def start(self) -> None:
        """启动自动刷新"""
        if self.flush_task is None or self.flush_task.done():
            self.flush_task = asyncio.create_task(self._auto_flush_loop())
            logger.info("Started auto flush loop")

    async def stop(self) -> None:
        """停止并刷新缓冲区"""
        self.closed = True
        if self.flush_task and not self.flush_task.done():
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass

        # 刷新剩余数据
        async with self.lock:
            await self._flush()

        logger.info("Batch buffer stopped")


class StatusHistoryBuffer(BatchBuffer):
    """设备状态历史缓冲器"""

    async def add_status(
        self,
        device_id: str,
        cpu_usage: float,
        cpu_cores: int,
        cpu_user: float,
        cpu_system: float,
        mem_total: float,
        mem_used: float,
        mem_free: float,
        disk_total: float,
        disk_used: float,
        load_1min: float,
        load_5min: float,
        load_15min: float,
        uptime: int,
        net_rx_bytes: int,
        net_tx_bytes: int,
        hostname: str = None,
        kernel_version: str = None,
        ip_addr: str = None,
        mac_addr: str = None,
        raw_data: dict = None,
    ) -> None:
        """添加设备状态记录"""
        history = DeviceStatusHistory(
            device_id=device_id,
            cpu_usage=cpu_usage,
            cpu_cores=cpu_cores,
            cpu_user=cpu_user,
            cpu_system=cpu_system,
            mem_total=mem_total,
            mem_used=mem_used,
            mem_free=mem_free,
            disk_total=disk_total,
            disk_used=disk_used,
            load_1min=load_1min,
            load_5min=load_5min,
            load_15min=load_15min,
            uptime=uptime,
            net_rx_bytes=net_rx_bytes,
            net_tx_bytes=net_tx_bytes,
            hostname=hostname,
            kernel_version=kernel_version,
            ip_addr=ip_addr,
            mac_addr=mac_addr,
            raw_data=raw_data,
        )
        await self.add(history)


class AuditLogBuffer(BatchBuffer):
    """审计日志缓冲器"""

    async def add_log(
        self,
        event_type: str,
        action: str,
        actor_type: str = None,
        actor_id: str = None,
        device_id: str = None,
        console_id: str = None,
        resource_type: str = None,
        resource_id: str = None,
        status: str = "success",
        result_message: str = None,
        ip_address: str = None,
        user_agent: str = None,
        details: dict = None,
    ) -> None:
        """添加审计日志记录"""
        log = AuditLog(
            event_type=event_type,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            device_id=device_id,
            console_id=console_id,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            result_message=result_message,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        await self.add(log)


class PingHistoryBuffer(BatchBuffer):
    """Ping 历史缓冲器"""

    async def add_ping(
        self,
        device_id: str,
        target_ip: str,
        status: int = 0,
        avg_time: float = None,
        min_time: float = None,
        max_time: float = None,
        packet_loss: float = None,
        packets_sent: int = 0,
        packets_received: int = 0,
        raw_data: dict = None,
    ) -> None:
        """添加 ping 历史记录"""
        history = PingHistory(
            device_id=device_id,
            target_ip=target_ip,
            status=status,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            packet_loss=packet_loss,
            packets_sent=packets_sent,
            packets_received=packets_received,
            raw_data=raw_data,
        )
        await self.add(history)


# 全局缓冲器实例
_status_history_buffer: Optional[StatusHistoryBuffer] = None
_audit_log_buffer: Optional[AuditLogBuffer] = None
_ping_history_buffer: Optional[PingHistoryBuffer] = None


def get_status_history_buffer() -> StatusHistoryBuffer:
    """获取设备状态历史缓冲器（单例）"""
    global _status_history_buffer
    if _status_history_buffer is None:
        _status_history_buffer = StatusHistoryBuffer(
            config=BufferConfig(max_size=100, flush_interval=5.0)
        )
        _status_history_buffer.start()
    return _status_history_buffer


def get_audit_log_buffer() -> AuditLogBuffer:
    """获取审计日志缓冲器（单例）"""
    global _audit_log_buffer
    if _audit_log_buffer is None:
        _audit_log_buffer = AuditLogBuffer(
            config=BufferConfig(max_size=100, flush_interval=5.0)
        )
        _audit_log_buffer.start()
    return _audit_log_buffer


def get_ping_history_buffer() -> PingHistoryBuffer:
    """获取 ping 历史缓冲器（单例）"""
    global _ping_history_buffer
    if _ping_history_buffer is None:
        _ping_history_buffer = PingHistoryBuffer(
            config=BufferConfig(max_size=200, flush_interval=5.0)
        )
        _ping_history_buffer.start()
    return _ping_history_buffer


async def start_batch_buffers():
    """启动所有批量缓冲器"""
    get_status_history_buffer()
    get_audit_log_buffer()
    get_ping_history_buffer()
    logger.info("Batch buffers started")


async def stop_batch_buffers():
    """停止所有批量缓冲器"""
    global _status_history_buffer, _audit_log_buffer, _ping_history_buffer

    if _status_history_buffer:
        await _status_history_buffer.stop()
        _status_history_buffer = None

    if _audit_log_buffer:
        await _audit_log_buffer.stop()
        _audit_log_buffer = None

    if _ping_history_buffer:
        await _ping_history_buffer.stop()
        _ping_history_buffer = None

    logger.info("Batch buffers stopped")
