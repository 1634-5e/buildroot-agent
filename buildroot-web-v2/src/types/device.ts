/**
 * 设备类型定义
 */

export interface DeviceStatus {
  cpu_usage: number
  mem_usage_percent: number
  mem_used: number
  mem_total: number
  disk_usage_percent: number
  disk_used: number
  disk_total: number
  net_tx_bytes: number
  net_rx_bytes: number
  uptime: number
  load_avg: number[]
  hostname?: string
  kernel?: string
  ip_addr?: string
}

export interface Device {
  id: string
  name: string
  type?: string
  status: 'online' | 'offline'
  is_online: boolean
  last_seen_at?: string
  version?: string
  firmware_version?: string
  hardware_version?: string
  ip_addr?: string
  current_status?: DeviceStatus
  tags?: Record<string, unknown>
  created_at?: string
}

export interface DeviceListParams {
  limit?: number
  offset?: number
  status?: 'online' | 'offline'
  type?: string
  search?: string
}