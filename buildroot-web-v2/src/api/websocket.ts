/**
 * WebSocket 客户端 - Buildroot Agent 二进制协议
 * 支持自动重连、消息队列
 */

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected'

// WebSocket 配置
const WS_CONFIG = {
  reconnectInterval: 5000,
  maxReconnectAttempts: 10,
} as const

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
} as const

export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private status: ConnectionStatus = 'disconnected'
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private eventHandlers = new Map<string, Set<(...args: unknown[]) => void>>()
  private messageQueue: Array<{ type: number; data: unknown }> = []

  constructor(url: string) {
    this.url = url
  }

  connect(): void {
    if (this.status === 'connected' || this.status === 'connecting') {
      return
    }

    this.status = 'connecting'
    this.emit('connecting')

    try {
      this.ws = new WebSocket(this.url)  // 不指定子协议
      this.setupWebSocketHandlers()
    } catch (error) {
      console.error('[WebSocket] Connection error:', error)
      this.status = 'disconnected'
      this.emit('error', { error })
      this.scheduleReconnect()
    }
  }

  private setupWebSocketHandlers(): void {
    if (!this.ws) return

    this.ws.onopen = () => {
      console.log('[WebSocket] Connected')
      this.status = 'connected'
      this.reconnectAttempts = 0

      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }

      this.emit('connected')
      this.flushMessageQueue()
    }

    this.ws.onmessage = async (event: MessageEvent) => {
      try {
        const rawData = event.data instanceof ArrayBuffer
          ? event.data
          : await (event.data as Blob).arrayBuffer()

        const buffer = new Uint8Array(rawData)
        const message = this.decodeMessage(buffer)

        if (message) {
          this.emit('message', message)
        }
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error)
      }
    }

    this.ws.onclose = (event: CloseEvent) => {
      console.log('[WebSocket] Disconnected:', event.code, event.reason)
      this.status = 'disconnected'
      this.emit('disconnected', { code: event.code, reason: event.reason })

      if (!event.wasClean) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
      this.emit('error', { error })
    }
  }

  /**
   * 编码消息为二进制格式
   * 格式: [msg_type: 1字节] [length: 2字节大端序] [json_data]
   */
  private encodeMessage(msgType: number, data: unknown): Uint8Array {
    const jsonData = typeof data === 'object' ? data : { data }
    const jsonString = JSON.stringify(jsonData)
    const jsonBytes = new TextEncoder().encode(jsonString)
    const jsonLen = jsonBytes.length

    const buffer = new Uint8Array(3 + jsonLen)
    buffer[0] = msgType
    buffer[1] = (jsonLen >> 8) & 0xff
    buffer[2] = jsonLen & 0xff
    buffer.set(jsonBytes, 3)

    return buffer
  }

  /**
   * 解码二进制消息
   */
  private decodeMessage(rawData: Uint8Array): { type: number; data: unknown } | null {
    if (rawData.length < 3) {
      return null
    }

    const msgType = rawData[0]
    const jsonLen = (rawData[1] << 8) | rawData[2]

    if (rawData.length < 3 + jsonLen) {
      return null
    }

    try {
      const jsonBytes = rawData.slice(3, 3 + jsonLen)
      const jsonString = new TextDecoder().decode(jsonBytes)
      const data = JSON.parse(jsonString)
      return { type: msgType, data }
    } catch {
      return null
    }
  }

  send(type: number, data: unknown): boolean {
    const message = this.encodeMessage(type, data)

    if (this.status !== 'connected') {
      this.messageQueue.push({ type, data })
      return false
    }

    if (!this.ws) {
      return false
    }

    try {
      this.ws.send(message)
      return true
    } catch {
      return false
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const msg = this.messageQueue.shift()
      if (msg) {
        this.send(msg.type, msg.data)
      }
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting')
      this.ws = null
    }

    this.status = 'disconnected'
    this.reconnectAttempts = 0
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= WS_CONFIG.maxReconnectAttempts) {
      return
    }

    this.reconnectAttempts++
    const delay = WS_CONFIG.reconnectInterval * Math.min(this.reconnectAttempts, 5)

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  on(event: string, handler: (...args: unknown[]) => void): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set())
    }
    this.eventHandlers.get(event)!.add(handler)
  }

  off(event: string, handler: (...args: unknown[]) => void): void {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.delete(handler)
    }
  }

  private emit(event: string, data?: unknown): void {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data)
        } catch (error) {
          console.error(`[WebSocket] Error in handler for "${event}":`, error)
        }
      })
    }
  }

  getStatus(): ConnectionStatus {
    return this.status
  }

  isConnected(): boolean {
    return this.status === 'connected'
  }
}

// 全局实例
let wsClient: WebSocketClient | null = null

export function getWebSocketClient(url = '/ws'): WebSocketClient {
  if (!wsClient) {
    wsClient = new WebSocketClient(url)
  }
  return wsClient
}