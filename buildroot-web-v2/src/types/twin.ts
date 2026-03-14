/**
 * Device Twin 类型定义
 */

export interface DeviceTwin {
  device_id: string
  desired: Record<string, unknown>
  desired_version: number
  reported: Record<string, unknown>
  reported_version: number
  tags: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface TwinOverview {
  device_id: string
  desired: Record<string, unknown>
  desired_version: number
  reported: Record<string, unknown>
  reported_version: number
  tags: Record<string, unknown>
  delta: Record<string, unknown>
  is_synced: boolean
  created_at?: string
  updated_at?: string
}

export interface TwinUpdateRequest {
  desired: Record<string, unknown>
}

export interface ChangeLog {
  id: number
  device_id: string
  change_type: 'desired' | 'reported'
  old_value: Record<string, unknown>
  new_value: Record<string, unknown>
  changed_by?: string
  changed_at: string
}

export interface DeviceRegisterRequest {
  device_id?: string
  device_name?: string
  device_type?: string
  firmware_version?: string
  hardware_version?: string
  mac_address?: string
  tags?: Record<string, unknown>
}

export interface DeviceRegisterResponse {
  device_id: string
  mqtt_username: string
  mqtt_password: string
  mqtt_broker: string
  mqtt_port: number
  created: boolean
}

export interface BatchUpdateRequest {
  device_ids?: string[]
  filters?: Record<string, unknown>
  desired: Record<string, unknown>
}

export interface BatchUpdateResult {
  updated: number
  failed: number
  device_ids: string[]
}