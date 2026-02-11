export enum MessageType {
  HEARTBEAT = 0x01,
  SYSTEM_STATUS = 0x02,
  LOG_UPLOAD = 0x03,
  SCRIPT_RECV = 0x04,
  SCRIPT_RESULT = 0x05,
  PTY_CREATE = 0x10,
  PTY_DATA = 0x11,
  PTY_RESIZE = 0x12,
  PTY_CLOSE = 0x13,
  FILE_REQUEST = 0x20,
  FILE_DATA = 0x21,
  FILE_LIST_REQUEST = 0x22,
  FILE_LIST_RESPONSE = 0x23,
  DOWNLOAD_PACKAGE = 0x24,
  CMD_REQUEST = 0x30,
  CMD_RESPONSE = 0x31,
  FILE_UPLOAD_START = 0x40,
  FILE_UPLOAD_DATA = 0x41,
  FILE_UPLOAD_ACK = 0x42,
  FILE_UPLOAD_COMPLETE = 0x43,
  FILE_DOWNLOAD_START = 0x44,
  FILE_DOWNLOAD_DATA = 0x45,
  FILE_DOWNLOAD_ACK = 0x46,
  FILE_TRANSFER_STATUS = 0x47,
  DEVICE_LIST = 0x50,
  AUTH = 0xF0,
  AUTH_RESULT = 0xF1,
}

export interface Device {
  id: string;
  device_id?: string;
  name: string;
  ip?: string;
  remote_addr?: string;
  mac?: string;
  status: 'online' | 'offline';
  cpu?: number;
  memory?: number;
  disk?: number;
  uptime?: number;
  connected_time?: string;
}

export interface SystemStatus {
  cpu: {
    usage: number;
    cores: number;
    user: number;
    sys: number;
  };
  memory: {
    total: number;
    used: number;
    free: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
  };
  load: {
    '1m': number;
    '5m': number;
    '15m': number;
  };
  uptime: number;
  network: {
    rx: number;
    tx: number;
  };
}

export interface Process {
  pid: number;
  name: string;
  state: string;
  cpu: number;
  mem: number;
  time?: string;
  command?: string;
}

export interface FileInfo {
  path: string;
  name: string;
  size: number;
  isDirectory: boolean;
  modified?: number;
  children?: FileInfo[];
}

export interface WebSocketMessage {
  type: MessageType;
  deviceId?: string;
  data?: any;
}
