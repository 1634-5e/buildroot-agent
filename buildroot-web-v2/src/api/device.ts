/**
 * 设备 API
 */
import apiClient from './client'
import type { Device, DeviceListParams } from '@/types/device'

export const deviceApi = {
  /**
   * 获取设备列表
   */
  async list(params?: DeviceListParams): Promise<Device[]> {
    const { data } = await apiClient.get<Device[]>('/devices', { params })
    return data
  },

  /**
   * 获取设备详情
   */
  async get(deviceId: string): Promise<Device> {
    const { data } = await apiClient.get<Device>(`/devices/${deviceId}`)
    return data
  },

  /**
   * 删除设备
   */
  async delete(deviceId: string): Promise<void> {
    await apiClient.delete(`/devices/${deviceId}`)
  },
}

export default deviceApi