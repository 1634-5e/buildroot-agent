/**
 * Device Twin API
 */
import apiClient from './client'
import type {
  TwinOverview,
  TwinUpdateRequest,
  ChangeLog,
  DeviceRegisterRequest,
  DeviceRegisterResponse,
  BatchUpdateRequest,
  BatchUpdateResult,
} from '@/types/twin'

export const twinApi = {
  /**
   * 获取设备 Twin
   */
  async getTwin(deviceId: string): Promise<TwinOverview> {
    const { data } = await apiClient.get<TwinOverview>(`/devices/${deviceId}/twin`)
    return data
  },

  /**
   * 更新设备 desired
   */
  async updateDesired(
    deviceId: string,
    desired: Record<string, unknown>,
    updatedBy: string = 'web'
  ): Promise<TwinOverview> {
    const { data } = await apiClient.patch<TwinOverview>(
      `/devices/${deviceId}/twin`,
      { desired },
      { params: { updated_by: updatedBy } }
    )
    return data
  },

  /**
   * 获取变更历史
   */
  async getHistory(
    deviceId: string,
    limit: number = 100,
    changeType?: string
  ): Promise<ChangeLog[]> {
    const { data } = await apiClient.get<ChangeLog[]>(
      `/devices/${deviceId}/twin/history`,
      { params: { limit, change_type: changeType } }
    )
    return data
  },

  /**
   * 列出所有 Twin
   */
  async listTwins(params?: {
    limit?: number
    offset?: number
    is_synced?: boolean
  }): Promise<TwinOverview[]> {
    const { data } = await apiClient.get<TwinOverview[]>('/twins', { params })
    return data
  },

  /**
   * 批量更新
   */
  async batchUpdate(request: BatchUpdateRequest): Promise<BatchUpdateResult> {
    const { data } = await apiClient.post<BatchUpdateResult>('/twins/batch', request)
    return data
  },

  /**
   * 注册设备
   */
  async registerDevice(request: DeviceRegisterRequest): Promise<DeviceRegisterResponse> {
    const { data } = await apiClient.post<DeviceRegisterResponse>('/register', request)
    return data
  },
}

export default twinApi