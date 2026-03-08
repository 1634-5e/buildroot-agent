// API: Device Management
import axios from 'axios'

export interface Device {
  id: string
  name: string
  status: 'online' | 'offline'
  lastSeen: string
  ip?: string
  port?: number
}

export interface DeviceListResponse {
  devices: Device[]
}

export interface DeviceStatusResponse {
  id: string
  status: 'online' | 'offline'
}

export const deviceApi = {
  // 获取所有设备
  async list(): Promise<DeviceListResponse> {
    const response = await axios.get<DeviceListResponse>('/api/devices')
    return response.data
  },

  // 更新设备状态
  async updateStatus(deviceId: string, status: 'online' | 'offline'): Promise<DeviceStatusResponse> {
    const response = await axios.post<DeviceStatusResponse>(`/api/devices/${deviceId}/status`, { status })
    return response.data
  },

  // 断开设备连接
  async disconnect(deviceId: string): Promise<{ success: boolean }> {
    const response = await axios.post<{ success: boolean }>(`/api/devices/${deviceId}/disconnect`)
    return response.data
  }
}
