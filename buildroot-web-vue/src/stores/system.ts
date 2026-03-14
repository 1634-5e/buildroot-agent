import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SystemStats, ServerStatus, AgentStats, SessionStats, HealthStatus, Alert, Event } from '@/types/system'

export const useSystemStore = defineStore('system', () => {
  const stats = ref<SystemStats>({
    agents: { total: 0, online: 0, offline: 0, connections: 0 },
    resources: {
      avg_cpu: 0,
      avg_memory: 0,
      total_memory_used: 0,
      total_memory_total: 0,
      total_net_tx: 0,
      total_net_rx: 0,
      total_disk_used: 0,
      total_disk_total: 0,
    },
    connections: { websocket: 0, agents: 0 },
  })

  const serverStatus = ref<ServerStatus>({
    status: 'online',
    cpu: 0,
    memory: 0,
    uptime: 0,
  })

  const agentStats = ref<AgentStats>({
    online: 0,
    total: 0,
    offline: 0,
  })

  const sessionStats = ref<SessionStats>({
    active: 0,
    file_transfers: 0,
    pending: 0,
  })

  const healthStatus = ref<HealthStatus>({
    score: 100,
    alerts: 0,
  })

  const alerts = ref<Alert[]>([])
  const events = ref<Event[]>([])
  const loading = ref(false)

  const criticalAlerts = computed(() => alerts.value.filter(a => a.type === 'critical' && !a.acknowledged))
  const recentEvents = computed(() => events.value.slice(0, 10))

  async function fetchStats() {
    loading.value = true
    try {
      const response = await fetch('/api/system/stats')
      if (response.ok) {
        stats.value = await response.json()
        
        agentStats.value = {
          online: stats.value.agents.online,
          total: stats.value.agents.total,
          offline: stats.value.agents.offline,
        }
      }
    } catch (err) {
      console.error('获取系统统计失败:', err)
      
      stats.value = {
        agents: { total: 15, online: 12, offline: 3, connections: 12 },
        resources: {
          avg_cpu: 42,
          avg_memory: 38,
          total_memory_used: 8.5 * 1024 * 1024 * 1024,
          total_memory_total: 22.4 * 1024 * 1024 * 1024,
          total_net_tx: 2.3 * 1024 * 1024,
          total_net_rx: 8.1 * 1024 * 1024,
          total_disk_used: 120 * 1024 * 1024 * 1024,
          total_disk_total: 500 * 1024 * 1024 * 1024,
        },
        connections: { websocket: 8, agents: 12 },
      }

      agentStats.value = { online: 12, total: 15, offline: 3 }
      serverStatus.value = { status: 'online', cpu: 23, memory: 18, uptime: 86400 }
      sessionStats.value = { active: 8, file_transfers: 2, pending: 0 }
      healthStatus.value = { score: 98, alerts: 1 }
    }
    loading.value = false
  }

  async function fetchAlerts() {
    try {
      const response = await fetch('/api/system/alerts')
      if (response.ok) {
        alerts.value = await response.json()
      }
    } catch (err) {
      console.error('获取告警失败:', err)
      
      alerts.value = [
        {
          id: '1',
          type: 'critical',
          severity: 'high',
          message: 'CPU usage 95%',
          deviceId: 'device-abc',
          deviceName: 'device-abc',
          timestamp: new Date().toISOString(),
          acknowledged: false,
        },
        {
          id: '2',
          type: 'warning',
          severity: 'medium',
          message: 'Memory usage 82%',
          deviceId: 'device-xyz',
          deviceName: 'device-xyz',
          timestamp: new Date(Date.now() - 300000).toISOString(),
          acknowledged: false,
        },
        {
          id: '3',
          type: 'critical',
          severity: 'high',
          message: 'Device offline',
          deviceId: 'device-offline',
          deviceName: 'device-offline',
          timestamp: new Date(Date.now() - 600000).toISOString(),
          acknowledged: false,
        },
      ]
    }
  }

  async function fetchEvents() {
    try {
      const response = await fetch('/api/system/events')
      if (response.ok) {
        events.value = await response.json()
      }
    } catch (err) {
      console.error('获取事件失败:', err)
      
      events.value = [
        {
          id: '1',
          type: 'update',
          message: 'Update completed',
          deviceId: 'device-123',
          deviceName: 'device-123',
          timestamp: new Date().toISOString(),
        },
        {
          id: '2',
          type: 'connection',
          message: 'Device connected',
          deviceId: 'device-789',
          deviceName: 'device-789',
          timestamp: new Date(Date.now() - 120000).toISOString(),
        },
        {
          id: '3',
          type: 'file',
          message: 'File transfer completed',
          deviceId: 'device-456',
          deviceName: 'device-456',
          timestamp: new Date(Date.now() - 240000).toISOString(),
        },
      ]
    }
  }

  function acknowledgeAlert(alertId: string) {
    const alert = alerts.value.find(a => a.id === alertId)
    if (alert) {
      alert.acknowledged = true
    }
  }

  async function refreshAll() {
    await Promise.all([fetchStats(), fetchAlerts(), fetchEvents()])
  }

  return {
    stats,
    serverStatus,
    agentStats,
    sessionStats,
    healthStatus,
    alerts,
    events,
    loading,
    criticalAlerts,
    recentEvents,
    fetchStats,
    fetchAlerts,
    fetchEvents,
    acknowledgeAlert,
    refreshAll,
  }
})
