#!/usr/bin/env python3
"""
Buildroot Agent Server - SQLModel Repository with Cache
使用SQLModel ORM进行数据访问，带缓存支持
"""

import logging
from typing import List, Optional
from datetime import datetime

from sqlmodel import select, and_, or_

from database.models import (
    Device,
    DeviceStatusHistory,
    PingHistory,
    CommandHistory,
    ScriptHistory,
    FileTransfer,
    UpdateHistory,
    UpdateApproval,
    WebConsoleSession,
    PtySession,
    AuditLog,
)
from database.db_manager import db_manager
from database.cache import device_detail_cache, device_list_cache

logger = logging.getLogger(__name__)


class DeviceRepository:
    """设备数据仓储"""

    @staticmethod
    async def get_by_device_id(
        device_id: str, use_cache: bool = True
    ) -> Optional[dict]:
        """通过设备ID获取设备（带缓存）

        Args:
            device_id: 设备ID
            use_cache: 是否使用缓存，查询实时状态时应设为 False
        """
        cache_key = f"device_{device_id}"

        # 只有使用缓存时才检查缓存
        if use_cache:
            cached_value = await device_detail_cache.get(cache_key)
            if cached_value is not None:
                return cached_value

        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()
            if device:
                device_data = {
                    "id": device.id,
                    "device_id": device.device_id,
                    "name": device.name,
                    "version": device.version,
                    "hostname": device.hostname,
                    "kernel_version": device.kernel_version,
                    "ip_addr": device.ip_addr,
                    "mac_addr": device.mac_addr,
                    "status": device.status,
                    "is_online": device.is_online,
                    "last_connected_at": device.last_connected_at,
                    "last_disconnected_at": device.last_disconnected_at,
                    "last_seen_at": device.last_seen_at,
                    "current_status": device.current_status,
                    "last_status_reported_at": device.last_status_reported_at,
                    "auto_update": device.auto_update,
                    "tags": device.tags,
                    "created_at": device.created_at,
                    "updated_at": device.updated_at,
                }
                # 只有使用缓存时才设置缓存
                if use_cache:
                    await device_detail_cache.set(cache_key, device_data, ttl=60.0)
                return device_data
            return None

    @staticmethod
    async def create_or_update(
        device_id: str,
        name: str = None,
        version: str = None,
        hostname: str = None,
        kernel_version: str = None,
        ip_addr: str = None,
        mac_addr: str = None,
        tags: list = None,
        last_connected_at: datetime = None,
    ) -> Optional[dict]:
        """创建或更新设备（并清除缓存）"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device:
                if name is not None:
                    device.name = name
                if version is not None:
                    device.version = version
                if hostname is not None:
                    device.hostname = hostname
                if kernel_version is not None:
                    device.kernel_version = kernel_version
                if ip_addr is not None:
                    device.ip_addr = ip_addr
                if mac_addr is not None:
                    device.mac_addr = mac_addr
                if tags is not None:
                    device.tags = tags
                if last_connected_at is not None:
                    device.last_connected_at = last_connected_at

            else:
                device = Device(
                    device_id=device_id,
                    name=name,
                    version=version,
                    hostname=hostname,
                    kernel_version=kernel_version,
                    ip_addr=ip_addr,
                    mac_addr=mac_addr,
                    status="offline",
                    tags=tags,
                )
                session.add(device)

            await session.commit()
            await session.refresh(device)

            await device_detail_cache.delete(f"device_{device_id}")
            await device_list_cache.clear()

            return {
                "id": device.id,
                "device_id": device.device_id,
                "name": device.name,
                "version": device.version,
                "status": device.status,
                "created_at": device.created_at,
                "updated_at": device.updated_at,
            }

    @staticmethod
    async def update_connection_status(
        device_id: str,
        status: str,
        is_online: bool,
        remote_addr: str = None,
        last_seen_at: datetime = None,
    ) -> bool:
        """更新设备连接状态（并清除缓存）"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device:
                device.status = status
                device.is_online = is_online
                device.last_seen_at = last_seen_at or datetime.now()
                if is_online:
                    device.last_connected_at = datetime.now()
                else:
                    device.last_disconnected_at = datetime.now()
                device.connection_count = (device.connection_count or 0) + 1

                await session.commit()
                await session.refresh(device)
                await device_detail_cache.delete(f"device_{device_id}")
                await device_list_cache.clear()

                return True
            return False

    @staticmethod
    async def update_current_status(
        device_id: str,
        current_status: dict,
    ) -> bool:
        """更新设备当前系统状态（并清除缓存）"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device:
                # 合并新旧状态，而不是完全替换
                existing_status = device.current_status or {}
                merged_status = {**existing_status, **current_status}
                device.current_status = merged_status
                device.last_status_reported_at = datetime.now()

                await session.commit()

                await device_detail_cache.delete(f"device_{device_id}")

                return True

    @staticmethod
    async def list_devices(
        status: str = None,
        tags: list = None,
        last_connected_at: datetime = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """获取设备列表（带缓存）"""
        cache_key = f"list_devices_{status}_{tags}_{limit}_{offset}"
        cached_value = await device_list_cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        async with db_manager.get_session() as session:
            query = select(Device)

            if status:
                query = query.where(Device.status == status)
            if tags:
                conditions = []
                for tag in tags:
                    conditions.append(Device.tags.contains(tag))
                query = query.where(or_(*conditions))

            query = query.order_by(Device.last_seen_at.desc())

            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            devices = result.scalars().all()

            device_list = [
                {
                    "id": d.id,
                    "device_id": d.device_id,
                    "name": d.name,
                    "version": d.version,
                    "status": d.status,
                    "is_online": d.is_online,
                    "last_seen_at": d.last_seen_at,
                    "tags": d.tags,
                    "created_at": d.created_at,
                    "updated_at": d.updated_at,
                }
                for d in devices
            ]

            await device_list_cache.set(cache_key, device_list, ttl=30.0)

            return device_list

    @staticmethod
    async def delete_device(device_id: str) -> bool:
        """删除设备（并清除缓存）"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device:
                await session.delete(device)
                await session.commit()

                await device_detail_cache.delete(f"device_{device_id}")
                await device_list_cache.clear()

                return True
            return False

    @staticmethod
    async def update_device_info(
        device_id: str,
        hostname: str = None,
        kernel_version: str = None,
        ip_addr: str = None,
        mac_addr: str = None,
        name: str = None,
        tags: list = None,
    ) -> bool:
        """更新设备基本信息"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device:
                if hostname is not None:
                    device.hostname = hostname
                if kernel_version is not None:
                    device.kernel_version = kernel_version
                if ip_addr is not None:
                    device.ip_addr = ip_addr
                if mac_addr is not None:
                    device.mac_addr = mac_addr
                if name is not None:
                    device.name = name
                if tags is not None:
                    device.tags = tags

                await session.commit()
                await device_detail_cache.delete(f"device_{device_id}")
                await device_list_cache.clear()
                return True
            return False

    @staticmethod
    async def update_uptime_seconds(
        device_id: str,
        uptime_seconds: int,
    ) -> bool:
        """更新设备运行时间（直接存储当前uptime值）"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device:
                device.total_uptime_seconds = uptime_seconds
                await session.commit()
                await device_detail_cache.delete(f"device_{device_id}")
                return True
            return False


class DeviceStatusHistoryRepository:
    """设备状态历史数据仓储"""

    @staticmethod
    async def insert(
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
    ) -> bool:
        """插入设备状态历史记录"""
        try:
            async with db_manager.get_session() as session:
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
                session.add(history)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save device status history: {e}")
            return False

    @staticmethod
    async def get_history(
        device_id: str,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[dict]:
        """获取设备状态历史"""
        async with db_manager.get_session() as session:
            query = select(DeviceStatusHistory).where(
                DeviceStatusHistory.device_id == device_id
            )

            if start_time:
                query = query.where(DeviceStatusHistory.reported_at >= start_time)
            if end_time:
                query = query.where(DeviceStatusHistory.reported_at <= end_time)

            query = query.order_by(DeviceStatusHistory.reported_at.desc()).limit(limit)

            result = await session.execute(query)
            records = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "device_id": r.device_id,
                    "reported_at": r.reported_at,
                    "cpu_usage": r.cpu_usage,
                    "mem_used": r.mem_used,
                    "mem_total": r.mem_total,
                    "load_1min": r.load_1min,
                    "uptime": r.uptime,
                    "net_rx_bytes": r.net_rx_bytes,
                    "net_tx_bytes": r.net_tx_bytes,
                }
                for r in records
            ]


class PingHistoryRepository:
    """Ping 历史数据仓储"""

    @staticmethod
    async def insert(
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
    ) -> bool:
        """插入 ping 历史记录"""
        try:
            async with db_manager.get_session() as session:
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
                session.add(history)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save ping history: {e}")
            return False

    @staticmethod
    async def get_history(
        device_id: str,
        target_ip: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[dict]:
        """获取 ping 历史记录"""
        async with db_manager.get_session() as session:
            query = select(PingHistory).where(PingHistory.device_id == device_id)

            if target_ip:
                query = query.where(PingHistory.target_ip == target_ip)
            if start_time:
                query = query.where(PingHistory.reported_at >= start_time)
            if end_time:
                query = query.where(PingHistory.reported_at <= end_time)

            query = query.order_by(PingHistory.reported_at.desc()).limit(limit)

            result = await session.execute(query)
            records = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "device_id": r.device_id,
                    "reported_at": r.reported_at,
                    "target_ip": r.target_ip,
                    "status": r.status,
                    "avg_time": float(r.avg_time) if r.avg_time else None,
                    "min_time": float(r.min_time) if r.min_time else None,
                    "max_time": float(r.max_time) if r.max_time else None,
                    "packet_loss": float(r.packet_loss) if r.packet_loss else None,
                    "packets_sent": r.packets_sent,
                    "packets_received": r.packets_received,
                    "raw_data": r.raw_data,
                }
                for r in records
            ]

    @staticmethod
    async def get_latest(
        device_id: str,
        target_ip: str = None,
    ) -> Optional[dict]:
        """获取最新的 ping 记录"""
        async with db_manager.get_session() as session:
            query = select(PingHistory).where(PingHistory.device_id == device_id)

            if target_ip:
                query = query.where(PingHistory.target_ip == target_ip)

            query = query.order_by(PingHistory.reported_at.desc()).limit(1)

            result = await session.execute(query)
            record = result.scalar_one_or_none()

            if record:
                return {
                    "id": record.id,
                    "device_id": record.device_id,
                    "reported_at": record.reported_at,
                    "target_ip": record.target_ip,
                    "status": record.status,
                    "avg_time": float(record.avg_time) if record.avg_time else None,
                    "min_time": float(record.min_time) if record.min_time else None,
                    "max_time": float(record.max_time) if record.max_time else None,
                    "packet_loss": float(record.packet_loss)
                    if record.packet_loss
                    else None,
                    "packets_sent": record.packets_sent,
                    "packets_received": record.packets_received,
                    "raw_data": record.raw_data,
                }
            return None


class CommandHistoryRepository:
    """命令执行历史数据仓储"""

    @staticmethod
    async def insert(
        device_id: str,
        command: str,
        command_type: str = "shell",
        console_id: str = None,
        request_id: str = None,
    ) -> Optional[dict]:
        """插入命令执行记录"""
        async with db_manager.get_session() as session:
            history = CommandHistory(
                device_id=device_id,
                command=command,
                command_type=command_type,
                console_id=console_id,
                request_id=request_id,
            )
            session.add(history)
            await session.commit()
            return {
                "id": history.id,
                "device_id": history.device_id,
                "command": history.command,
                "command_type": history.command_type,
                "status": history.status,
                "requested_at": history.requested_at,
            }

    @staticmethod
    async def update_result(
        request_id: str,
        status: str,
        exit_code: int = None,
        success: bool = None,
        stdout: str = None,
        stderr: str = None,
        started_at: datetime = None,
        completed_at: datetime = None,
    ) -> bool:
        """更新命令执行结果"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(CommandHistory).where(CommandHistory.request_id == request_id)
            )
            history = result.scalar_one_or_none()

            if history:
                history.status = status
                if exit_code is not None:
                    history.exit_code = exit_code
                if success is not None:
                    history.success = success
                if stdout is not None:
                    history.stdout = stdout
                if stderr is not None:
                    history.stderr = stderr
                if started_at is not None:
                    history.started_at = started_at
                elif history.started_at is None:
                    history.started_at = history.requested_at
                if completed_at is not None:
                    history.completed_at = completed_at

                if history.started_at and (completed_at or history.completed_at):
                    start = history.started_at
                    end = completed_at or history.completed_at
                    history.duration_seconds = int((end - start).total_seconds())

                output_summary = (
                    (stdout or stderr or "")[:500] if (stdout or stderr) else None
                )
                history.output_summary = output_summary

                await session.commit()
                return True
            return False

    @staticmethod
    async def get_by_request_id(request_id: str) -> Optional[dict]:
        """通过请求ID获取命令历史"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(CommandHistory).where(CommandHistory.request_id == request_id)
            )
            history = result.scalar_one_or_none()

            if history:
                return {
                    "id": history.id,
                    "device_id": history.device_id,
                    "command": history.command,
                    "command_type": history.command_type,
                    "status": history.status,
                    "exit_code": history.exit_code,
                    "success": history.success,
                    "stdout": history.stdout,
                    "stderr": history.stderr,
                    "requested_at": history.requested_at,
                    "started_at": history.started_at,
                    "completed_at": history.completed_at,
                }
            return None

    @staticmethod
    async def list_by_device(
        device_id: str,
        status: str = None,
        limit: int = 50,
    ) -> List[dict]:
        """获取设备的命令执行历史"""
        async with db_manager.get_session() as session:
            query = select(CommandHistory).where(CommandHistory.device_id == device_id)

            if status:
                query = query.where(CommandHistory.status == status)

            query = query.order_by(CommandHistory.requested_at.desc()).limit(limit)

            result = await session.execute(query)
            histories = result.scalars().all()

            return [
                {
                    "id": h.id,
                    "device_id": h.device_id,
                    "command": h.command,
                    "command_type": h.command_type,
                    "status": h.status,
                    "exit_code": h.exit_code,
                    "success": h.success,
                    "requested_at": h.requested_at,
                    "completed_at": h.completed_at,
                }
                for h in histories
            ]


class UpdateHistoryRepository:
    """更新历史数据仓储"""

    @staticmethod
    async def insert(
        device_id: str,
        old_version: str,
        new_version: str,
        update_channel: str = "stable",
        mandatory: bool = False,
        package_name: str = None,
        package_size: int = None,
        package_url: str = None,
        request_id: str = None,
    ) -> Optional[dict]:
        """插入更新记录"""
        async with db_manager.get_session() as session:
            update = UpdateHistory(
                device_id=device_id,
                old_version=old_version,
                new_version=new_version,
                update_channel=update_channel,
                mandatory=mandatory,
                package_name=package_name,
                package_size=package_size,
                package_url=package_url,
                request_id=request_id,
            )
            session.add(update)
            await session.commit()
            return {
                "id": update.id,
                "device_id": update.device_id,
                "old_version": update.old_version,
                "new_version": update.new_version,
                "status": update.status,
                "check_requested_at": update.check_requested_at,
            }

    @staticmethod
    async def update_status(
        request_id: str,
        status: str,
        error_message: str = None,
        error_stage: str = None,
        download_started_at: datetime = None,
        download_completed_at: datetime = None,
        install_started_at: datetime = None,
        completed_at: datetime = None,
    ) -> bool:
        """更新更新状态"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(UpdateHistory).where(UpdateHistory.request_id == request_id)
            )
            update = result.scalar_one_or_none()

            if update:
                update.status = status
                if error_message is not None:
                    update.error_message = error_message
                if error_stage is not None:
                    update.error_stage = error_stage
                if download_started_at is not None:
                    update.download_started_at = download_started_at
                if download_completed_at is not None:
                    update.download_completed_at = download_completed_at
                if install_started_at is not None:
                    update.install_started_at = install_started_at
                if completed_at is not None:
                    update.completed_at = completed_at

                await session.commit()
                return True
            return False

    @staticmethod
    async def get_latest_by_device(device_id: str) -> Optional[dict]:
        """获取设备的最新更新记录"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(UpdateHistory)
                .where(UpdateHistory.device_id == device_id)
                .order_by(UpdateHistory.check_requested_at.desc())
                .limit(1)
            )
            update = result.scalar_one_or_none()

            if update:
                return {
                    "id": update.id,
                    "device_id": update.device_id,
                    "old_version": update.old_version,
                    "new_version": update.new_version,
                    "status": update.status,
                    "check_requested_at": update.check_requested_at,
                }
            return None


class AuditLogRepository:
    """审计日志数据仓储"""

    @staticmethod
    async def insert(
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
    ) -> bool:
        """插入审计日志"""
        try:
            async with db_manager.get_session() as session:
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
                session.add(log)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            return False

    @staticmethod
    async def list(
        event_type: str = None,
        device_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[dict]:
        """获取审计日志列表"""
        async with db_manager.get_session() as session:
            query = select(AuditLog)

            if event_type:
                query = query.where(AuditLog.event_type == event_type)
            if device_id:
                query = query.where(AuditLog.device_id == device_id)
            if start_time:
                query = query.where(AuditLog.event_time >= start_time)
            if end_time:
                query = query.where(AuditLog.event_time <= end_time)

            query = query.order_by(AuditLog.event_time.desc()).limit(limit)

            result = await session.execute(query)
            logs = result.scalars().all()

            return [
                {
                    "id": l.id,
                    "event_type": l.event_type,
                    "event_time": l.event_time,
                    "actor_type": l.actor_type,
                    "actor_id": l.actor_id,
                    "device_id": l.device_id,
                    "console_id": l.console_id,
                    "action": l.action,
                    "resource_type": l.resource_type,
                    "resource_id": l.resource_id,
                    "status": l.status,
                    "result_message": l.result_message,
                    "ip_address": l.ip_address,
                }
                for l in logs
            ]


class ScriptHistoryRepository:
    """脚本执行历史数据仓储"""

    @staticmethod
    async def insert(
        script_id: str,
        device_id: str,
        console_id: str = None,
        request_id: str = None,
        script_name: str = None,
        script_content: str = None,
        script_type: str = "bash",
        status: str = "pending",
        exit_code: int = None,
        success: bool = None,
        output: str = None,
        output_summary: str = None,
        output_size: int = None,
        error_message: str = None,
        requested_at: datetime = None,
        started_at: datetime = None,
        completed_at: datetime = None,
        duration_seconds: int = None,
    ) -> dict:
        """插入脚本执行历史"""
        try:
            async with db_manager.get_session() as session:
                script = ScriptHistory(
                    script_id=script_id,
                    device_id=device_id,
                    console_id=console_id,
                    request_id=request_id,
                    script_name=script_name,
                    script_content=script_content,
                    script_type=script_type,
                    status=status,
                    exit_code=exit_code,
                    success=success,
                    output=output,
                    output_summary=output_summary,
                    output_size=output_size,
                    error_message=error_message,
                    requested_at=requested_at or datetime.now(),
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration_seconds,
                )
                session.add(script)
                await session.commit()
            result = {
                "id": script.id,
            }
            return result
        except Exception as e:
            logger.error(f"Failed to insert script history: {e}")
            return None

    @staticmethod
    async def update_result(
        script_id: str,
        status: str = "completed",
        exit_code: int = None,
        success: bool = None,
        output: str = None,
        error_message: str = None,
        completed_at: datetime = None,
        output_summary: str = None,
        output_size: int = None,
        duration_seconds: int = None,
    ) -> bool:
        """更新脚本执行结果"""
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(ScriptHistory).where(ScriptHistory.script_id == script_id)
                )
                script = result.scalar_one_or_none()
                if script:
                    script.status = status
                    script.exit_code = exit_code
                    script.success = success
                    script.output = output
                    script.error_message = error_message
                    script.completed_at = completed_at or datetime.now()

                    if output_summary is None:
                        output_summary = (output or "")[:500] if output else None
                    script.output_summary = output_summary

                    if output_size is None:
                        output_size = len(output) if output else 0
                    script.output_size = output_size

                    if duration_seconds is None and script.started_at:
                        duration_seconds = int(
                            (script.completed_at - script.started_at).total_seconds()
                        )
                    script.duration_seconds = duration_seconds

                    await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update script history: {e}")
            return False


class PtySessionRepository:
    """PTY 会话数据仓储"""

    @staticmethod
    async def insert(
        session_id: int,
        device_id: str,
        console_id: str = None,
        rows: int = 24,
        cols: int = 80,
        status: str = "active",
        created_by: str = None,
    ) -> dict:
        """插入 PTY 会话"""
        try:
            async with db_manager.get_session() as session:
                pty = PtySession(
                    session_id=session_id,
                    device_id=device_id,
                    console_id=console_id,
                    rows=rows,
                    cols=cols,
                    status=status,
                    created_by=created_by,
                )
                session.add(pty)
                await session.commit()
            result = {
                "id": pty.id,
            }
            return result
        except Exception as e:
            logger.error(f"Failed to insert pty session: {e}")
            return None

    @staticmethod
    async def update_closed(
        session_id: int,
        device_id: str,
        closed_at: datetime = None,
        closed_reason: str = None,
        status: str = "closed",
    ) -> bool:
        """更新 PTY 会话关闭状态"""
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(PtySession).where(
                        and_(
                            PtySession.session_id == session_id,
                            PtySession.device_id == device_id,
                        )
                    )
                )
                pty = result.scalar_one_or_none()
                if pty:
                    pty.closed_at = closed_at or datetime.now()
                    pty.closed_reason = closed_reason
                    pty.status = status
                    await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update pty session: {e}")
            return False

    @staticmethod
    async def update_bytes_received(
        device_id: str,
        session_id: int,
        bytes_received: int,
    ) -> bool:
        """更新 PTY 会话接收字节数"""
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(PtySession).where(
                        and_(
                            PtySession.session_id == session_id,
                            PtySession.device_id == device_id,
                            PtySession.status == "active",
                        )
                    )
                )
                pty = result.scalar_one_or_none()
                if pty:
                    pty.bytes_received = (pty.bytes_received or 0) + bytes_received
                    await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update PTY bytes received: {e}")
            return False

    @staticmethod
    async def update_bytes_sent(
        device_id: str,
        session_id: int,
    ) -> bool:
        """更新 PTY 会话发送字节数（server 计算）"""
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(PtySession).where(
                        and_(
                            PtySession.session_id == session_id,
                            PtySession.device_id == device_id,
                        )
                    )
                )
                pty = result.scalar_one_or_none()
                if pty:
                    await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update PTY bytes sent: {e}")
            return False


class WebConsoleSessionRepository:
    """Web控制台会话数据仓储"""

    @staticmethod
    async def insert(
        console_id: str,
        device_id: str = None,
        remote_addr: str = None,
        user_id: str = None,
        user_agent: str = None,
        last_seen_at: datetime = None,
    ) -> dict:
        """插入 Web 控制台会话"""
        try:
            async with db_manager.get_session() as session:
                console = WebConsoleSession(
                    console_id=console_id,
                    device_id=device_id,
                    remote_addr=remote_addr,
                    user_id=user_id,
                    user_agent=user_agent,
                )
                session.add(console)
                await session.commit()
            result = {
                "id": console.id,
            }
            return result
        except Exception as e:
            logger.error(f"Failed to insert web console session: {e}")
            return None

    @staticmethod
    async def update_closed(
        console_id: str,
        disconnected_at: datetime = None,
        is_active: bool = False,
    ) -> bool:
        """更新 Web 控制台断开"""
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(WebConsoleSession).where(
                        WebConsoleSession.console_id == console_id
                    )
                )
                console = result.scalar_one_or_none()
                if console:
                    console.disconnected_at = disconnected_at or datetime.now()
                    console.is_active = is_active
                    await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update web console session: {e}")
            return False


class UpdateApprovalRepository:
    """更新批准记录数据仓储"""

    @staticmethod
    async def insert(
        device_id: str,
        update_history_id: int = None,
        request_id: str = None,
        version: str = None,
        action_type: str = None,
        action: str = None,
        console_id: str = None,
        approval_time: datetime = None,
        reason: str = None,
        file_size: int = None,
    ) -> dict:
        """插入更新批准记录"""
        try:
            async with db_manager.get_session() as session:
                approval = UpdateApproval(
                    device_id=device_id,
                    update_history_id=update_history_id,
                    request_id=request_id,
                    version=version,
                    action_type=action_type,
                    action=action,
                    console_id=console_id,
                    approval_time=approval_time or datetime.now(),
                    reason=reason,
                    file_size=file_size,
                )
                session.add(approval)
                await session.commit()
            result = {
                "id": approval.id,
            }
            return result
        except Exception as e:
            logger.error(f"Failed to insert update approval: {e}")
            return None


class FileTransferRepository:
    """文件传输数据仓储"""

    @staticmethod
    async def insert(
        transfer_id: str,
        device_id: str,
        console_id: str = None,
        filename: str = None,
        filepath: str = None,
        file_size: int = None,
        direction: str = "upload",
        action_type: str = None,
        status: str = "pending",
        checksum: str = None,
        checksum_verified: bool = False,
        chunk_size: int = None,
        total_chunks: int = None,
        transferred_chunks: int = 0,
        created_at: datetime = None,
        started_at: datetime = None,
        completed_at: datetime = None,
        duration_seconds: int = None,
        error_message: str = None,
        retry_count: int = 0,
        request_id: str = None,
    ) -> dict:
        """插入文件传输记录"""
        try:
            async with db_manager.get_session() as session:
                transfer = FileTransfer(
                    transfer_id=transfer_id,
                    device_id=device_id,
                    console_id=console_id,
                    filename=filename,
                    filepath=filepath,
                    file_size=file_size,
                    direction=direction,
                    action_type=action_type,
                    status=status,
                    checksum=checksum,
                    checksum_verified=checksum_verified,
                    chunk_size=chunk_size,
                    total_chunks=total_chunks,
                    transferred_chunks=transferred_chunks,
                    created_at=created_at or datetime.now(),
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration_seconds,
                    error_message=error_message,
                    retry_count=retry_count,
                    request_id=request_id,
                )
                session.add(transfer)
                await session.commit()
            result = {
                "id": transfer.id,
            }
            return result
        except Exception as e:
            logger.error(f"Failed to insert file transfer: {e}")
            return None
