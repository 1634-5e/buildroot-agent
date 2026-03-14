// WebSocket Client - Buildroot Agent Binary Protocol
// 支持二进制协议和自动重连

type WebSocketEvent = {
  type: 'connected' | 'disconnected' | 'message' | 'error'
  data?: any
}

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected'

// WebSocket 配置常量
const WS_CONFIG = {
  reconnectInterval: 5000,
  maxReconnectAttempts: 10,
  messageQueueLimit: 100,
} as const

export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectInterval: number = WS_CONFIG.reconnectInterval
  private maxReconnectAttempts: number = WS_CONFIG.maxReconnectAttempts
  private reconnectAttempts: number = 0
  private reconnectTimer: NodeJS.Timeout | null = null
  private status: ConnectionStatus = 'disconnected'
  private eventHandlers: Map<string, Set<Function>> = new Map()
  private messageQueue: Array<{ type: number; data: any }> = []

  constructor(url: string) {
    this.url = url
  }

  connect(): void {
    if (this.status === 'connected' || this.status === 'connecting') {
      console.warn('[WebSocketClient] Already connecting or connected')
      return
    }

    console.log('[WebSocketClient] Connecting to:', this.url)
    this.status = 'connecting'
    this.emit('connecting')

    try {
      this.ws = new WebSocket(this.url, 'binary') // 指定二进制协议
      this.setupWebSocketHandlers()
    } catch (error) {
      console.error('[WebSocketClient] Connection error:', error)
      this.status = 'disconnected'
      this.emit('error', { error })
      this.scheduleReconnect()
    }
  }

  private setupWebSocketHandlers(): void {
    if (!this.ws) return

    this.ws.onopen = () => {
      console.log('[WebSocketClient] Connected')
      this.status = 'connected'
      this.reconnectAttempts = 0

      // 清除重连定时器
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }

      this.emit('connected')

      // 发送队列中的消息
      this.flushMessageQueue()
    }

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const rawData = event.data instanceof ArrayBuffer
          ? event.data
          : (event.data as Blob).arrayBuffer()

        if (!rawData) {
          console.error('[WebSocketClient] No data received')
          return
        }

        const buffer = new Uint8Array(rawData)
        const message = this.decodeMessage(buffer)

        if (message) {
          console.log('[WebSocketClient] Received:', message)
          this.emit('message', message)
        }
      } catch (error) {
        console.error('[WebSocketClient] Failed to parse message:', error)
      }
    }

    this.ws.onclose = (event: CloseEvent) => {
      console.log('[WebSocketClient] Disconnected:', event.code, event.reason)
      this.status = 'disconnected'
      this.emit('disconnected', { code: event.code, reason: event.reason })

      // 如果不是主动关闭，尝试重连
      if (!event.wasClean) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = (error: Event) => {
      console.error('[WebSocketClient] Error:', error)
      this.emit('error', { error })
    }
  }

  /**
   * 编码消息为二进制格式
   * 格式: [msg_type: 1字节] [length: 2字节大端序] [json_data]
   */
  private encodeMessage(msgType: number, data: any): Uint8Array {
    // 将数据转换为 JSON
    const jsonData = typeof data === 'object' ? data : { data }
    const jsonString = JSON.stringify(jsonData)
    const jsonBytes = new TextEncoder().encode(jsonString)
    const jsonLen = jsonBytes.length

    // 创建消息缓冲区
    const buffer = new Uint8Array(3 + jsonLen)
    buffer[0] = msgType
    buffer[1] = (jsonLen >> 8) & 0xFF // 高字节
    buffer[2] = jsonLen & 0xFF         // 低字节
    buffer.set(jsonBytes, 3)

    return buffer
  }

  /**
   * 解码二进制消息
   * 格式: [msg_type: 1字节] [length: 2字节大端序] [json_data]
   */
  private decodeMessage(rawData: Uint8Array): { type: number; data: any } | null {
    if (rawData.length < 3) {
      console.error('Message too short:', rawData.length)
      return null
    }

    // 解析消息头
    const msgType = rawData[0]
    const jsonLen = (rawData[1] << 8) | rawData[2]

    // 检查长度
    if (rawData.length < 3 + jsonLen) {
      console.error(`Message incomplete: expected ${3 + jsonLen}, got ${rawData.length}`)
      return null
    }

    // 解析 JSON 数据
    const jsonBytes = rawData.slice(3, 3 + jsonLen)
    try {
      const jsonString = new TextDecoder().decode(jsonBytes)
      const data = JSON.parse(jsonString)
      return { type: msgType, data }
    } catch (error) {
      console.error('Failed to decode message:', error)
      return null
    }
  }

  send(type: number, data: any): boolean {
    const message = this.encodeMessage(type, data)

    // 如果未连接，加入队列
    if (this.status !== 'connected') {
      console.warn('[WebSocketClient] Not connected, queuing message:', type)
      this.messageQueue.push({ type, data })
      return false
    }

    if (!this.ws) {
      console.error('[WebSocketClient] WebSocket is null')
      return false
    }

    try {
      this.ws.send(message)
      console.log('[WebSocketClient] Sent:', { type, data })
      return true
    } catch (error) {
      console.error('[WebSocketClient] Send error:', error)
      return false
    }
  }

  private flushMessageQueue(): void {
    if (this.messageQueue.length === 0) return

    console.log(`[WebSocketClient] Flushing ${this.messageQueue.length} queued messages`)

    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()
      if (message) {
        this.send(message.type, message.data)
      }
    }
  }

  disconnect(): void {
    console.log('[WebSocketClient] Disconnecting')

    // 清除重连定时器
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    // 关闭 WebSocket
    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting')
      this.ws = null
    }

    this.status = 'disconnected'
    this.reconnectAttempts = 0
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocketClient] Max reconnect attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectInterval * Math.min(this.reconnectAttempts, 5)

    console.log(`[WebSocketClient] Scheduling reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  on(event: string, handler: Function): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set())
    }
    this.eventHandlers.get(event)!.add(handler)
  }

  off(event: string, handler: Function): void {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.delete(handler)
    }
  }

  private emit(event: string, data?: any): void {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data)
        } catch (error) {
          console.error(`[WebSocketClient] Error in event handler for "${event}":`, error)
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

// 全局 WebSocket 客户端实例管理
// 支持多标签页独立连接
const wsClients = new Map<string, WebSocketClient>()

export function getWebSocketClient(url?: string): WebSocketClient {
  const clientUrl = url || '/ws'
  
  if (!wsClients.has(clientUrl)) {
    wsClients.set(clientUrl, new WebSocketClient(clientUrl))
  }
  
  return wsClients.get(clientUrl)!
}

// 为每个标签页创建独立连接
export function createWebSocketClient(url: string): WebSocketClient {
  return new WebSocketClient(url)
}

// 清理指定 URL 的连接
export function closeWebSocketClient(url: string): void {
  const client = wsClients.get(url)
  if (client) {
    client.disconnect()
    wsClients.delete(url)
  }
}
