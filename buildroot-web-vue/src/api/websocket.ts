// API: WebSocket Management
// 与 Buildroot Agent Server WebSocket 协议交互（二进制协议）

import { getWebSocketClient } from './websocket-client'

// WebSocket 配置 - 使用 Vite 代理
const WS_URL = import.meta.env.VITE_WS_URL || '/ws'

// 获取全局 WebSocket 客户端
const wsClient = getWebSocketClient(WS_URL)

// 消息类型常量（对应后端 MessageType）
export const MessageType = {
  HEARTBEAT: 0x01,
  SYSTEM_STATUS: 0x02,
  LOG_UPLOAD: 0x03,
  SCRIPT_RECV: 0x04,
  SCRIPT_RESULT: 0x05,
  PTY_CREATE: 0x10,
  PTY_DATA: 0x11,
  PTY_RESIZE: 0x12,
  PTY_CLOSE: 0x13,
  FILE_REQUEST: 0x20,
  FILE_DATA: 0x21,
  FILE_LIST_REQUEST: 0x22,
  FILE_LIST_RESPONSE: 0x23,
  DOWNLOAD_PACKAGE: 0x24,
  FILE_DOWNLOAD_REQUEST: 0x25,
  FILE_DOWNLOAD_DATA: 0x26,
  CMD_REQUEST: 0x30,
  CMD_RESPONSE: 0x31,
  DEVICE_LIST: 0x50,
  DEVICE_DISCONNECT: 0x51,
  DEVICE_UPDATE: 0x52,
  REGISTER: 0xF0,
  REGISTER_RESULT: 0xF1,
  UPDATE_CHECK: 0x60,
  UPDATE_INFO: 0x61,
  UPDATE_DOWNLOAD: 0x62,
  UPDATE_PROGRESS: 0x63,
  UPDATE_COMPLETE: 0x65,
  UPDATE_ERROR: 0x66,
  UPDATE_ROLLBACK: 0x67,
  UPDATE_REQUEST_APPROVAL: 0x68,
  UPDATE_DOWNLOAD_READY: 0x69,
  UPDATE_APPROVE_INSTALL: 0x6A,
  UPDATE_DENY: 0x6B,
  UPDATE_APPROVE_DOWNLOAD: 0x6C,
  PING_STATUS: 0x70,
} as const

// 消息类型名称映射
const MessageTypeNames: Record<number, string> = {}
for (const [name, value] of Object.entries(MessageType)) {
  MessageTypeNames[value as number] = name
}

// 发送 WebSocket 消息（二进制协议）
export function sendWebSocketMessage(type: number, data: any): boolean {
  const typeName = MessageTypeNames[type] || `0x${type.toString(16)}`
  console.log(`[WebSocket] Sending ${typeName} (0x${type.toString(16)}):`, data)

  return wsClient.send(type, data)
}

// 连接 WebSocket
export function connectWebSocket(): void {
  console.log('[WebSocket] Connecting...')
  wsClient.connect()
}

// 断开 WebSocket
export function disconnectWebSocket(): void {
  console.log('[WebSocket] Disconnecting...')
  wsClient.disconnect()
}

// 检查连接状态
export function isWebSocketConnected(): boolean {
  return wsClient.isConnected()
}

// 注册消息处理器
export function onWebSocketMessage(type: number, handler: (data: any) => void): void {
  const typeName = MessageTypeNames[type] || `0x${type.toString(16)}`

  wsClient.on('message', (message: any) => {
    if (message.type === type) {
      console.log(`[WebSocket] Received ${typeName} (0x${type.toString(16)}):`, message.data)
      handler(message.data)
    }
  })
}

// 注册连接事件
export function onWebSocketConnected(handler: () => void): void {
  wsClient.on('connected', handler)
}

// 注册断开事件
export function onWebSocketDisconnected(handler: (data: any) => void): void {
  wsClient.on('disconnected', handler)
}

// 注册错误事件
export function onWebSocketError(handler: (data: any) => void): void {
  wsClient.on('error', handler)
}

// PTY 相关 API
export function createPTYSession(
  deviceId: string,
  cols: number = 80,
  rows: number = 24
): boolean {
  return sendWebSocketMessage(MessageType.PTY_CREATE, {
    device_id: deviceId,
    cols,
    rows,
  })
}

export function sendPTYData(sessionId: number, data: string): boolean {
  return sendWebSocketMessage(MessageType.PTY_DATA, {
    session_id: sessionId,
    data: data,
  })
}

export function resizePTYSession(sessionId: number, cols: number, rows: number): boolean {
  return sendWebSocketMessage(MessageType.PTY_RESIZE, {
    session_id: sessionId,
    cols,
    rows,
  })
}

export function closePTYSession(sessionId: number): boolean {
  return sendWebSocketMessage(MessageType.PTY_CLOSE, {
    session_id: sessionId,
  })
}

// 文件相关 API
export function requestFileList(deviceId: string, path: string = '/'): boolean {
  return sendWebSocketMessage(MessageType.FILE_LIST_REQUEST, {
    device_id: deviceId,
    path: path,
  })
}

export function requestFileUpload(
  deviceId: string,
  filename: string,
  size: number
): boolean {
  return sendWebSocketMessage(MessageType.FILE_REQUEST, {
    device_id: deviceId,
    filename: filename,
    size: size,
  })
}

export function sendFileData(
  deviceId: string,
  chunkIndex: number,
  data: string
): boolean {
  return sendWebSocketMessage(MessageType.FILE_DATA, {
    device_id: deviceId,
    chunk_index: chunkIndex,
    data: data,
  })
}

// 导出 WebSocket 客户端实例，供高级使用
export { wsClient, getWebSocketClient }
