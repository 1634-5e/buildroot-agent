// Message types from original implementation
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
  DEVICE_LIST = 0x50,
}

export interface Device {
  device_id: string;
  ip_addr?: string;
  cpu_usage?: number;
  mem_used?: number;
  mem_total?: number;
  load_1min?: number;
  load_5min?: number;
  load_15min?: number;
  disk_usage?: number;
  disk_used?: number;
  disk_total?: number;
  uptime?: number;
  rx_bytes?: number;
  tx_bytes?: number;
  mac_addr?: string;
  last_seen?: number;
  status?: 'online' | 'offline' | 'unknown';
}

export interface SystemStatus {
  cpu_usage: number;
  cpu_cores: number;
  cpu_user: number;
  cpu_system: number;
  mem_used: number;
  mem_total: number;
  mem_free: number;
  disk_used: number;
  disk_total: number;
  disk_usage: number;
  load_1min: number;
  load_5min: number;
  load_15min: number;
  uptime: number;
  ip_addr: string;
  mac_addr: string;
  rx_bytes: number;
  tx_bytes: number;
}

export interface ProcessInfo {
  pid: number;
  name: string;
  cpu_percent: number;
  mem_percent: number;
  cpu_time: string;
}

export interface FileItem {
  name: string;
  is_dir: boolean;
  size: number;
  modified: string;
}

export interface ScriptResult {
  exit_code: number;
  stdout: string;
  stderr: string;
}

export interface TerminalData {
  session_id: number;
  data: string;
}

export interface ToastMessage {
  id: string;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
}

export type TabType = 'terminal' | 'files' | 'monitor' | 'scripts';
