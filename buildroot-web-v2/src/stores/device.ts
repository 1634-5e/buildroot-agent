/**
 * Device Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { deviceApi, twinApi } from '@/api'
import type { Device, TwinOverview } from '@/types'

export const useDeviceStore = defineStore('device', () => {
  // State
  const devices = ref<Device[]>([])
  const twins = ref<Map<string, TwinOverview>>(new Map())
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const onlineDevices = computed(() => 
    devices.value.filter(d => d.is_online)
  )
  
  const offlineDevices = computed(() => 
    devices.value.filter(d => !d.is_online)
  )
  
  const syncedDevices = computed(() => 
    devices.value.filter(d => {
      const twin = twins.value.get(d.id)
      return twin?.is_synced ?? true
    })
  )
  
  const unsyncedDevices = computed(() => 
    devices.value.filter(d => {
      const twin = twins.value.get(d.id)
      return twin && !twin.is_synced
    })
  )

  // Actions
  async function fetchDevices() {
    loading.value = true
    error.value = null
    try {
      devices.value = await deviceApi.list()
    } catch (e: any) {
      error.value = e.message || '获取设备列表失败'
      console.error('[DeviceStore] fetchDevices error:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchTwin(deviceId: string) {
    try {
      const twin = await twinApi.getTwin(deviceId)
      twins.value.set(deviceId, twin)
      return twin
    } catch (e: any) {
      console.error('[DeviceStore] fetchTwin error:', e)
      return null
    }
  }

  async function updateDesired(
    deviceId: string, 
    desired: Record<string, unknown>,
    updatedBy?: string
  ) {
    try {
      const twin = await twinApi.updateDesired(deviceId, desired, updatedBy)
      twins.value.set(deviceId, twin)
      return twin
    } catch (e: any) {
      console.error('[DeviceStore] updateDesired error:', e)
      throw e
    }
  }

  function getTwin(deviceId: string): TwinOverview | undefined {
    return twins.value.get(deviceId)
  }

  function $reset() {
    devices.value = []
    twins.value.clear()
    loading.value = false
    error.value = null
  }

  return {
    // State
    devices,
    twins,
    loading,
    error,
    // Computed
    onlineDevices,
    offlineDevices,
    syncedDevices,
    unsyncedDevices,
    // Actions
    fetchDevices,
    fetchTwin,
    updateDesired,
    getTwin,
    $reset,
  }
})