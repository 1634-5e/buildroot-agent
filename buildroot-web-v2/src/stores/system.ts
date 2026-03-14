/**
 * 系统状态 Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface SystemStats {
  agents: {
    total: number
    online: number
    offline: number
  }
  resources: {
    avg_cpu: number
    avg_memory: number
    total_net_tx: number
    total_net_rx: number
  }
}

export interface Alert {
  id: string
  type: 'critical' | 'warning' | 'info'
  message: string
  deviceId?: string
  deviceName?: string
  timestamp: string
  acknowledged: boolean
}

export const useSystemStore = defineStore('system', () => {
  // State
  const stats = ref<SystemStats>({
    agents: { total: 0, online: 0, offline: 0 },
    resources: { avg_cpu: 0, avg_memory: 0, total_net_tx: 0, total_net_rx: 0 },
  })
  const alerts = ref<Alert[]>([])
  const loading = ref(false)

  // Computed
  const criticalAlerts = computed(() => 
    alerts.value.filter(a => a.type === 'critical' && !a.acknowledged)
  )
  
  const unacknowledgedAlerts = computed(() => 
    alerts.value.filter(a => !a.acknowledged)
  )

  // Actions
  async function fetchStats() {
    // TODO: 对接真实 API
    // 暂时使用模拟数据
    stats.value = {
      agents: { total: 15, online: 12, offline: 3 },
      resources: { 
        avg_cpu: 42, 
        avg_memory: 38, 
        total_net_tx: 2.3 * 1024 * 1024, 
        total_net_rx: 8.1 * 1024 * 1024 
      },
    }
  }

  async function fetchAlerts() {
    // TODO: 对接真实 API
    alerts.value = []
  }

  function acknowledgeAlert(alertId: string) {
    const alert = alerts.value.find(a => a.id === alertId)
    if (alert) {
      alert.acknowledged = true
    }
  }

  async function refreshAll() {
    loading.value = true
    try {
      await Promise.all([fetchStats(), fetchAlerts()])
    } finally {
      loading.value = false
    }
  }

  return {
    stats,
    alerts,
    loading,
    criticalAlerts,
    unacknowledgedAlerts,
    fetchStats,
    fetchAlerts,
    acknowledgeAlert,
    refreshAll,
  }
})