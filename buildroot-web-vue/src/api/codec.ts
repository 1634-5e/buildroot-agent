// Protocol Codec - Buildroot Agent Binary Protocol
// 编码/解码二进制协议消息

export class MessageCodec {
  /**
   * 编码消息为二进制格式
   * 格式: [msg_type: 1字节] [length: 2字节大端序] [json_data]
   */
  static encode(msgType: number, data: any): Uint8Array {
    // 将数据转换为 JSON
    const jsonData = typeof data === 'object' ? data : { data }
    const jsonString = JSON.stringify(jsonData)
    const jsonBytes = new TextEncoder().encode(jsonString)
    const jsonLen = jsonBytes.length

    // 创建消息缓冲区: [msg_type] [len_hi] [len_lo] [json_data]
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
  static decode(rawData: ArrayBuffer | Uint8Array): { type: number; data: any } | null {
    const buffer = rawData instanceof ArrayBuffer
      ? new Uint8Array(rawData)
      : rawData

    if (buffer.length < 3) {
      console.error('Message too short:', buffer.length)
      return null
    }

    // 解析消息头
    const msgType = buffer[0]
    const jsonLen = (buffer[1] << 8) | buffer[2]

    // 检查长度
    if (buffer.length < 3 + jsonLen) {
      console.error(`Message incomplete: expected ${3 + jsonLen}, got ${buffer.length}`)
      return null
    }

    // 解析 JSON 数据
    const jsonBytes = buffer.slice(3, 3 + jsonLen)
    try {
      const jsonString = new TextDecoder().decode(jsonBytes)
      const data = JSON.parse(jsonString)
      return { type: msgType, data }
    } catch (error) {
      console.error('Failed to decode message:', error)
      return null
    }
  }
}

// 消息类型常量（与后端对应）
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
export const MessageTypeNames: Record<number, string> = {}
for (const [name, value] of Object.entries(MessageType)) {
  MessageTypeNames[value as number] = name
}
