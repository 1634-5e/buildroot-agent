import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Device, DeviceStatus } from '@/types/device'

export const useDeviceStore = defineStore('device', () => {
  const devices = ref<Device[]>([])
  const currentDevice = ref<Device | null>(null)
  const loading = ref(false)

  const onlineDevices = computed(() => devices.value.filter(d => d.status === 'online'))
  const totalDevices = computed(() => devices.value.length)
  const offlineDevices = computed(() => devices.value.filter(d => d.status === 'offline'))
  const deviceStats = computed(() => ({
    total: devices.value.length,
    online: devices.value.filter(d => d.status === 'online').length,
    offline: devices.value.filter(d => d.status === 'offline').length
  }))

  async function fetchDevices() {
    loading.value = true

    try {
      const response = await fetch('/api/devices')

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`)
      }

      const data = await response.json()

      // 转换后端数据格式为前端格式
      devices.value = data.map((d: any) => ({
        id: d.device_id,
        name: d.name || `Device ${d.device_id}`,
        status: d.is_online ? 'online' : 'offline',
        is_online: d.is_online || false,
        lastSeen: d.last_seen_at || new Date().toISOString(),
        ip: d.ip_addr,
        os: d.kernel_version,
        cpu: undefined,
        memory: undefined,
      }))

      loading.value = false
    } catch (err: any) {
      console.error('Failed to fetch devices from API:', err.message)
      devices.value = []
      loading.value = false
    }
  }

  function selectDevice(device: Device) {
    currentDevice.value = device
  }

  function updateDeviceStatus(deviceId: string, status: DeviceStatus) {
    const device = devices.value.find(d => d.id === deviceId)
    if (device) {
      device.status = status
      device.lastSeen = new Date().toISOString()
    }
  }

  function addDevice(device: Device) {
    devices.value.push(device)
  }

  function removeDevice(deviceId: string) {
    const index = devices.value.findIndex(d => d.id === deviceId)
    if (index >= 0) {
      devices.value.splice(index, 1)
    }
    if (currentDevice.value?.id === deviceId) {
      currentDevice.value = null
    }
  }

  return {
    devices,
    currentDevice,
    loading,
    onlineDevices,
    totalDevices,
    offlineDevices,
    deviceStats,
    fetchDevices,
    selectDevice,
    updateDeviceStatus,
    addDevice,
    removeDevice
  }
})
