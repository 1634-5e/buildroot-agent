export interface DeviceStatusData {
  cpu_usage: number
  mem_usage_percent: number
  mem_used_bytes: number
  mem_total_bytes: number
  disk_used_bytes: number
  disk_total_bytes: number
  uptime_seconds: number
  load_avg: number[]
}

export interface Device {
  id: string
  name: string
  status: DeviceStatus
  lastSeen: string
  ip?: string
  os?: string
  cpu?: string
  memory?: string
  disk?: string
  current_status?: DeviceStatusData
  is_online: boolean
  version?: string
}

export type DeviceStatus = 'online' | 'offline' | 'unknown'
