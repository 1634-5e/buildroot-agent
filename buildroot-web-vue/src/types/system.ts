export interface SystemStats {
  agents: {
    total: number
    online: number
    offline: number
    connections: number
  }
  resources: {
    avg_cpu: number
    avg_memory: number
    total_memory_used: number
    total_memory_total: number
    total_net_tx: number
    total_net_rx: number
    total_disk_used: number
    total_disk_total: number
  }
  connections: {
    websocket: number
    agents: number
  }
}

export interface ServerStatus {
  status: 'online' | 'offline'
  cpu: number
  memory: number
  uptime: number
}

export interface AgentStats {
  online: number
  total: number
  offline: number
}

export interface SessionStats {
  active: number
  file_transfers: number
  pending: number
}

export interface HealthStatus {
  score: number
  alerts: number
}

export interface Alert {
  id: string
  type: 'critical' | 'warning' | 'info'
  severity: 'high' | 'medium' | 'low'
  message: string
  deviceId: string
  deviceName: string
  timestamp: string
  acknowledged: boolean
}

export interface Event {
  id: string
  type: 'command' | 'file' | 'connection' | 'update'
  message: string
  deviceId?: string
  deviceName?: string
  timestamp: string
}
