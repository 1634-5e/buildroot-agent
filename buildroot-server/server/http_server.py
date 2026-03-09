#!/usr/bin/env python3
"""
Buildroot Agent Server - HTTP API Server
提供 REST API 接口，配合 WebSocket 使用
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database.repositories import (
    DeviceRepository,
    CommandHistoryRepository,
    FileTransferRepository,
)
from server.cloud_server import CloudServer
from protocol.constants import MessageType

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Buildroot Agent API",
    description="Buildroot Agent 管理控制台 REST API",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 认证 API ============


@app.get("/api/auth/token")
async def get_auth_token():
    """获取 WebSocket 认证 token"""
    from server.auth import generate_token

    token = generate_token()
    return {
        "token": token,
        "expires_in": 86400,  # 24 hours
        "message": "Use this token in WebSocket connection: ws://host:port?token=xxx",
    }


# ============ Pydantic 模型 ============


class DeviceInfo(BaseModel):
    id: int
    device_id: str
    name: Optional[str] = None
    version: Optional[str] = None
    status: str
    is_online: bool
    last_seen_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime


class DeviceDisconnectResponse(BaseModel):
    success: bool
    message: str


class CommandRequest(BaseModel):
    command: str


class CommandResponse(BaseModel):
    command_id: str
    status: str


class FileListRequest(BaseModel):
    path: str = "/"


class FileListResponse(BaseModel):
    files: List[dict]
    current_path: str


class FileDeleteRequest(BaseModel):
    path: str


class FileMkdirRequest(BaseModel):
    path: str


class GenericResponse(BaseModel):
    success: bool
    message: Optional[str] = None


# ============ 辅助函数 ============


def get_conn_mgr():
    """获取连接管理器实例"""
    return CloudServer.conn_mgr


# ============ 系统监控端点 ============


@app.get("/api/system/stats")
async def get_system_stats():
    """获取 Agent 系统统计数据 - 所有已连接设备的总览"""

    try:
        # 获取所有设备
        devices = await DeviceRepository.list_devices(limit=1000)
        online_devices = [d for d in devices if d.get("is_online")]
        offline_devices = [d for d in devices if not d.get("is_online")]

        # 计算所有在线设备的资源总和
        total_cpu = 0
        total_memory = 0
        total_memory_used = 0
        total_memory_available = 0
        total_net_tx = 0
        total_net_rx = 0
        total_disk_used = 0
        total_disk_total = 0
        device_count = 0

        for device in online_devices:
            status = device.get("current_status") or {}
            if status:
                total_cpu += status.get("cpu_usage", 0)
                total_memory += status.get("mem_usage_percent", 0)
                total_memory_used += status.get("mem_used", 0)
                total_memory_available += status.get("mem_total", 0)
                total_net_tx += status.get("net_tx_bytes", 0)
                total_net_rx += status.get("net_rx_bytes", 0)
                total_disk_used += status.get("disk_used", 0)
                total_disk_total += status.get("disk_total", 0)
                device_count += 1

        # 平均值
        avg_cpu = total_cpu / device_count if device_count > 0 else 0
        avg_memory = total_memory / device_count if device_count > 0 else 0

        # 连接统计
        conn_mgr = get_conn_mgr()
        ws_connections = len(conn_mgr.get_all_consoles()) if conn_mgr else 0
        agent_connections = len(conn_mgr.get_all_devices()) if conn_mgr else 0

        return {
            # Agent 总览
            "agents": {
                "total": len(devices),
                "online": len(online_devices),
                "offline": len(offline_devices),
                "connections": agent_connections,
            },
            # 资源监控（所有 Agent 的平均值/总和）
            "resources": {
                "avg_cpu": round(avg_cpu, 1),
                "avg_memory": round(avg_memory, 1),
                "total_memory_used": total_memory_used,
                "total_memory_available": total_memory_available,
                "total_net_tx": total_net_tx,
                "total_net_rx": total_net_rx,
                "total_disk_used": total_disk_used,
                "total_disk_total": total_disk_total,
            },
            # WebSocket 连接
            "connections": {
                "websocket": ws_connections,
                "agents": agent_connections,
            },
            # 时间戳
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        devices = await DeviceRepository.list_devices(limit=1000)
        return {
            "agents": {
                "total": len(devices),
                "online": len([d for d in devices if d.get("is_online")]),
                "offline": len([d for d in devices if not d.get("is_online")]),
                "connections": 0,
            },
            "resources": {
                "avg_cpu": 0,
                "avg_memory": 0,
                "total_memory_used": 0,
                "total_memory_available": 0,
                "total_net_tx": 0,
                "total_net_rx": 0,
                "total_disk_used": 0,
                "total_disk_total": 0,
            },
            "connections": {
                "websocket": 0,
                "agents": 0,
            },
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


# ============ 设备管理端点 ============


@app.get("/api/devices", response_model=List[DeviceInfo])
async def list_devices(
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(100, description="返回数量限制"),
    offset: int = Query(0, description="偏移量"),
):
    """获取设备列表"""
    try:
        devices = await DeviceRepository.list_devices(
            status=status,
            limit=limit,
            offset=offset,
        )
        return devices
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices/{device_id}", response_model=DeviceInfo)
async def get_device(device_id: str):
    """获取单个设备详情"""
    try:
        device = await DeviceRepository.get_by_device_id(device_id, use_cache=False)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return device
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/devices/{device_id}/disconnect", response_model=DeviceDisconnectResponse
)
async def disconnect_device(device_id: str):
    """断开设备连接"""
    conn_mgr = get_conn_mgr()
    if not conn_mgr:
        raise HTTPException(status_code=503, detail="Server not ready")

    try:
        # 检查设备是否连接
        is_connected = await conn_mgr.is_device_connected(device_id)
        if not is_connected:
            raise HTTPException(status_code=404, detail="Device not connected")

        # 发送断开消息
        await conn_mgr.send_to_device(device_id, MessageType.DEVICE_DISCONNECT, {})

        # 移除连接
        await conn_mgr.remove_device(device_id)

        # 更新设备状态
        await DeviceRepository.update_connection_status(
            device_id=device_id,
            status="offline",
            is_online=False,
            last_disconnected_at=datetime.now(),
        )

        logger.info(f"Device disconnected: {device_id}")
        return {"success": True, "message": "Device disconnected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/devices/{device_id}", response_model=GenericResponse)
async def delete_device(device_id: str):
    """删除设备"""
    conn_mgr = get_conn_mgr()
    try:
        # 断开连接（如果已连接）
        if conn_mgr and await conn_mgr.is_device_connected(device_id):
            await conn_mgr.send_to_device(device_id, MessageType.DEVICE_DISCONNECT, {})
            await conn_mgr.remove_device(device_id)

        # 从数据库删除
        success = await DeviceRepository.delete_device(device_id)

        if success:
            logger.info(f"Device deleted: {device_id}")
            return {"success": True, "message": "Device deleted"}
        else:
            raise HTTPException(status_code=404, detail="Device not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/devices/{device_id}", response_model=DeviceInfo)
async def update_device(
    device_id: str,
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """更新设备信息"""
    try:
        success = await DeviceRepository.update_device_info(
            device_id=device_id,
            name=name,
            tags=tags,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Device not found")

        # 返回更新后的设备信息
        device = await DeviceRepository.get_by_device_id(device_id, use_cache=False)
        return device
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 文件管理端点 ============


@app.get("/api/devices/{device_id}/files", response_model=FileListResponse)
async def list_files(device_id: str, path: str = Query("/", description="文件路径")):
    """列出设备上的文件（通过 WebSocket 获取）"""
    try:
        # 检查设备是否在线
        device = await DeviceRepository.get_by_device_id(device_id, use_cache=False)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if not device.get("is_online", False):
            raise HTTPException(status_code=400, detail="Device is offline")

        # 发送文件列表请求到设备（通过 WebSocket）
        # 注意：这需要在前端通过 WebSocket 实现，这里只是占位符
        # 前端应该直接使用 WebSocket FILE_LIST_REQUEST/FILE_LIST_RESPONSE
        raise HTTPException(
            status_code=501,
            detail="Use WebSocket FILE_LIST_REQUEST/FILE_LIST_RESPONSE instead",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/devices/{device_id}/files/upload")
async def upload_file(
    device_id: str,
    file: bytes,
    path: str = Query("/", description="目标路径"),
    filename: str = Query(..., description="文件名"),
):
    """上传文件（HTTP，适用于小文件 <10MB）"""
    conn_mgr = get_conn_mgr()
    if not conn_mgr:
        raise HTTPException(status_code=503, detail="Server not ready")

    try:
        # 检查设备是否在线
        device = await DeviceRepository.get_by_device_id(device_id, use_cache=False)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if not device.get("is_online", False):
            raise HTTPException(status_code=400, detail="Device is offline")

        # 构建完整路径
        full_path = path.rstrip("/") + "/" + filename

        # 通过 WebSocket 发送文件数据（转换为 Base64）
        import base64

        # 发送文件上传请求
        await conn_mgr.send_to_device(
            device_id,
            MessageType.FILE_REQUEST,
            {
                "action": "write",
                "filepath": full_path,
                "content": base64.b64encode(file).decode("utf-8"),
                "mtime": datetime.now().timestamp(),
                "force": True,
            },
        )

        logger.info(f"File uploaded: {device_id} - {full_path} ({len(file)} bytes)")
        return {"success": True, "message": "File uploaded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices/{device_id}/files/download")
async def download_file(
    device_id: str,
    path: str = Query(..., description="文件路径"),
):
    """下载文件（HTTP，适用于小文件 <10MB）"""
    try:
        # 检查设备是否在线
        device = await DeviceRepository.get_by_device_id(device_id, use_cache=False)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if not device.get("is_online", False):
            raise HTTPException(status_code=400, detail="Device is offline")

        # 注意：大文件应该通过 WebSocket 下载
        # 这里只是占位符，小文件下载需要通过 WebSocket 实现
        raise HTTPException(
            status_code=501,
            detail="Use WebSocket FILE_DOWNLOAD_REQUEST/FILE_DOWNLOAD_DATA for file download",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/devices/{device_id}/files", response_model=GenericResponse)
async def delete_file(device_id: str, request: FileDeleteRequest):
    """删除文件（通过 WebSocket）"""
    conn_mgr = get_conn_mgr()
    try:
        # 检查设备是否在线
        device = await DeviceRepository.get_by_device_id(device_id, use_cache=False)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if not device.get("is_online", False):
            raise HTTPException(status_code=400, detail="Device is offline")

        # 通过 WebSocket 发送删除请求
        await conn_mgr.send_to_device(
            device_id,
            MessageType.FILE_REQUEST,
            {
                "action": "delete",
                "filepath": request.path,
            },
        )

        logger.info(f"File deleted: {device_id} - {request.path}")
        return {"success": True, "message": "File deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/devices/{device_id}/files/mkdir", response_model=GenericResponse)
async def create_directory(device_id: str, request: FileMkdirRequest):
    """创建目录（通过 WebSocket）"""
    conn_mgr = get_conn_mgr()
    try:
        # 检查设备是否在线
        device = await DeviceRepository.get_by_device_id(device_id, use_cache=False)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if not device.get("is_online", False):
            raise HTTPException(status_code=400, detail="Device is offline")

        # 通过 WebSocket 发送创建目录请求
        # 注意：需要后端支持相应的消息类型
        # 这里使用 FILE_REQUEST 作为示例
        await conn_mgr.send_to_device(
            device_id,
            MessageType.FILE_REQUEST,
            {
                "action": "mkdir",
                "filepath": request.path,
            },
        )

        logger.info(f"Directory created: {device_id} - {request.path}")
        return {"success": True, "message": "Directory created"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 命令历史端点 ============


@app.get("/api/devices/{device_id}/commands")
async def list_commands(
    device_id: str,
    limit: int = Query(50, description="返回数量限制"),
):
    """获取命令历史"""
    try:
        commands = await CommandHistoryRepository.list_by_device(
            device_id=device_id,
            limit=limit,
        )
        return commands
    except Exception as e:
        logger.error(f"Failed to list commands: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 文件传输历史端点 ============


@app.get("/api/devices/{device_id}/files/transfers")
async def list_file_transfers(device_id: str):
    """获取文件传输历史"""
    try:
        transfers = await FileTransferRepository.list_by_device(device_id)
        return transfers
    except Exception as e:
        logger.error(f"Failed to list file transfers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 系统统计端点 ============


@app.get("/api/stats")
async def get_stats():
    """获取系统统计信息"""
    try:
        # 获取所有设备
        devices = await DeviceRepository.list_devices(limit=1000)

        online_count = sum(1 for d in devices if d.get("is_online", False))
        offline_count = len(devices) - online_count

        # TODO: 添加更多统计数据（命令数、传输数等）

        return {
            "total_devices": len(devices),
            "online_devices": online_count,
            "offline_devices": offline_count,
            "total_commands": 0,  # 待实现
            "total_transfers": 0,  # 待实现
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查端点 ============


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ============ 启动说明 ============
#
# 使用 uvicorn 运行：
#   uvicorn server.http_server:app --host 0.0.0.0 --port 8000
#
# 或在 main.py 中异步运行：
#   config = uvicorn.Config(app, host="0.0.0.0", port=8000)
#   server = uvicorn.Server(config)
#   await server.serve()
