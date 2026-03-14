<template>
  <div class="dashboard-container">
    <div class="dashboard-header">
      <div class="header-title">
        <h1>SYSTEM MONITOR</h1>
        <span class="header-subtitle">DASHBOARD</span>
      </div>
      <button class="refresh-btn" @click="refresh" :disabled="loading">
        <span class="refresh-icon" :class="{ spinning: loading }">↻</span>
        <span>REFRESH</span>
      </button>
    </div>

    <div class="dashboard-content">
      <div class="top-section">
        <div class="status-cards">
          <SystemStatusCard
            type="server"
            :server-status="systemStore.serverStatus"
          />
          <SystemStatusCard
            type="agents"
            :agent-stats="systemStore.agentStats"
          />
          <SystemStatusCard
            type="sessions"
            :session-stats="systemStore.sessionStats"
          />
          <SystemStatusCard
            type="health"
            :health-status="systemStore.healthStatus"
          />
        </div>
      </div>

      <div class="middle-section">
        <aside class="resource-panel">
          <div class="panel-header">
            <h2>AGGREGATE RESOURCES</h2>
            <span class="panel-badge">LIVE</span>
          </div>

          <div class="resource-list">
            <div
              v-for="resource in resourceCards"
              :key="resource.key"
              class="resource-item"
              :class="resource.level"
            >
              <div class="resource-topline">
                <span class="resource-name">{{ resource.name }}</span>
                <span class="resource-trend" :class="resource.trendDirection">
                  <span class="trend-arrow">{{ resource.trendArrow }}</span>
                  <span>{{ resource.trendText }}</span>
                </span>
              </div>

              <div class="resource-header">
                <span class="resource-value">{{ resource.value }}</span>
                <span v-if="resource.context" class="resource-context">{{ resource.context }}</span>
              </div>

              <div v-if="resource.barValue !== null" class="resource-bar">
                <div
                  class="bar-fill"
                  :class="[resource.barTone, resource.level]"
                  :style="{ width: `${resource.barValue}%` }"
                ></div>
              </div>

              <div v-if="resource.networkStats" class="network-stats">
                <div
                  v-for="stat in resource.networkStats"
                  :key="stat.label"
                  class="net-stat"
                >
                  <span class="net-label">{{ stat.label }}</span>
                  <span class="net-value">{{ stat.value }}</span>
                </div>
              </div>

              <div class="resource-meta">
                <span>{{ resource.meta }}</span>
              </div>
            </div>
          </div>
        </aside>

        <aside class="alert-panel-wrapper">
          <AlertPanel
            :alerts="systemStore.alerts"
            :events="systemStore.events"
            @acknowledge="systemStore.acknowledgeAlert"
          />
        </aside>
      </div>

      <section class="devices-section">
        <div class="section-header">
          <h2>DEVICES</h2>
          <div class="device-stats">
            <span class="stat-badge online">{{ deviceStore.onlineDevices.length }} online</span>
            <span class="stat-badge offline">{{ deviceStore.offlineDevices.length }} offline</span>
          </div>
        </div>

        <div class="devices-grid">
          <DeviceMiniCard
            v-for="device in sortedDevices"
            :key="device.id"
            :device="device"
            :selected="selectedDevice === device.id"
            @select="selectDevice"
          />

          <div v-if="deviceStore.devices.length === 0" class="empty-state">
            <div class="empty-icon">◉</div>
            <p class="empty-title">NO DEVICES CONNECTED</p>
            <p class="empty-hint">Start a Buildroot Agent to connect to this server</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AlertPanel from '@/components/AlertPanel.vue'
import DeviceMiniCard from '@/components/DeviceMiniCard.vue'
import SystemStatusCard from '@/components/SystemStatusCard.vue'
import { useDeviceStore } from '@/stores/device'
import { useSystemStore } from '@/stores/system'

interface ResourceSnapshot {
  avg_cpu: number
  avg_memory: number
  total_memory_used: number
  total_memory_total: number
  total_net_tx: number
  total_net_rx: number
  total_disk_used: number
  total_disk_total: number
}

interface ResourceCard {
  key: string
  name: string
  value: string
  context?: string
  meta: string
  trendArrow: string
  trendText: string
  trendDirection: 'up' | 'down' | 'flat'
  level: 'normal' | 'warning' | 'critical'
  barTone?: 'cpu' | 'memory' | 'disk'
  barValue: number | null
  networkStats?: Array<{ label: string; value: string }>
}

const router = useRouter()
const deviceStore = useDeviceStore()
const systemStore = useSystemStore()

const loading = ref(false)
const selectedDevice = ref('')
const refreshInterval = ref<NodeJS.Timeout | null>(null)
const previousResources = ref<ResourceSnapshot | null>(null)

const sortedDevices = computed(() => {
  const online = deviceStore.devices.filter(d => d.is_online).sort((a, b) => {
    const cpuA = a.current_status?.cpu_usage || 0
    const cpuB = b.current_status?.cpu_usage || 0
    return cpuB - cpuA
  })
  const offline = deviceStore.devices.filter(d => !d.is_online)
  return [...online, ...offline]
})

const resources = computed(() => systemStore.stats.resources)

const diskPercent = computed(() => {
  if (resources.value.total_disk_total === 0) return 0
  return (resources.value.total_disk_used / resources.value.total_disk_total) * 100
})

const getBarClass = (value: number) => {
  if (value > 80) return 'critical'
  if (value > 60) return 'warning'
  return 'normal'
}

const formatBytes = (bytes: number) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

const getTrend = (current: number, previous: number | undefined) => {
  const delta = current - (previous || 0)
  if (!previous && previous !== 0) {
    return { direction: 'flat' as const, arrow: '→', text: 'stable' }
  }
  if (Math.abs(delta) < 0.1) {
    return { direction: 'flat' as const, arrow: '→', text: 'flat' }
  }

  const direction = delta > 0 ? 'up' : 'down'
  const prefix = delta > 0 ? '+' : ''
  return {
    direction,
    arrow: delta > 0 ? '↗' : '↘',
    text: `${prefix}${delta.toFixed(1)}`
  }
}

const resourceCards = computed<ResourceCard[]>(() => {
  const current = resources.value
  const previous = previousResources.value
  const cpuTrend = getTrend(current.avg_cpu, previous?.avg_cpu)
  const memoryTrend = getTrend(current.avg_memory, previous?.avg_memory)
  const diskTrend = getTrend(diskPercent.value, previous && previous.total_disk_total
    ? (previous.total_disk_used / previous.total_disk_total) * 100
    : undefined)
  const throughput = current.total_net_tx + current.total_net_rx
  const previousThroughput = previous ? previous.total_net_tx + previous.total_net_rx : undefined
  const networkTrend = getTrend(throughput, previousThroughput)

  return [
    {
      key: 'cpu',
      name: 'CPU USAGE',
      value: `${current.avg_cpu.toFixed(1)}%`,
      context: `${systemStore.stats.agents.online} devices`,
      meta: `Average load across ${systemStore.stats.agents.online} online agents`,
      trendArrow: cpuTrend.arrow,
      trendText: `${cpuTrend.text}%`,
      trendDirection: cpuTrend.direction,
      level: getBarClass(current.avg_cpu),
      barTone: 'cpu',
      barValue: current.avg_cpu
    },
    {
      key: 'memory',
      name: 'MEMORY USAGE',
      value: `${current.avg_memory.toFixed(1)}%`,
      context: `${formatBytes(current.total_memory_used)} used`,
      meta: `${formatBytes(current.total_memory_used)} / ${formatBytes(current.total_memory_total)}`,
      trendArrow: memoryTrend.arrow,
      trendText: `${memoryTrend.text}%`,
      trendDirection: memoryTrend.direction,
      level: getBarClass(current.avg_memory),
      barTone: 'memory',
      barValue: current.avg_memory
    },
    {
      key: 'network',
      name: 'NETWORK I/O',
      value: `${formatBytes(throughput)}/s`,
      context: 'aggregate',
      meta: 'Total uplink and downlink throughput',
      trendArrow: networkTrend.arrow,
      trendText: `${networkTrend.text} B/s`,
      trendDirection: networkTrend.direction,
      level: 'normal',
      barValue: null,
      networkStats: [
        { label: 'TX', value: `${formatBytes(current.total_net_tx)}/s` },
        { label: 'RX', value: `${formatBytes(current.total_net_rx)}/s` }
      ]
    },
    {
      key: 'disk',
      name: 'DISK USAGE',
      value: `${diskPercent.value.toFixed(1)}%`,
      context: `${formatBytes(current.total_disk_used)} used`,
      meta: `${formatBytes(current.total_disk_used)} / ${formatBytes(current.total_disk_total)}`,
      trendArrow: diskTrend.arrow,
      trendText: `${diskTrend.text}%`,
      trendDirection: diskTrend.direction,
      level: getBarClass(diskPercent.value),
      barTone: 'disk',
      barValue: diskPercent.value
    }
  ]
})

const refresh = async () => {
  loading.value = true
  previousResources.value = { ...resources.value }

  await Promise.all([
    deviceStore.fetchDevices(),
    systemStore.refreshAll()
  ])

  setTimeout(() => {
    loading.value = false
  }, 500)
}

const selectDevice = (deviceId: string) => {
  selectedDevice.value = deviceId
  router.push(`/devicedetail/${deviceId}`)
}

onMounted(() => {
  refresh()
  refreshInterval.value = setInterval(refresh, 10000)
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
</script>

<style scoped>
.dashboard-container {
  --bg-primary: #05070d;
  --bg-secondary: #0b1018;
  --bg-tertiary: #111823;
  --bg-elevated: #172130;
  --border-color: #1e2a3d;
  --border-accent: #2b3b55;
  --panel-shadow: 0 18px 32px rgba(0, 0, 0, 0.25);
  --text-primary: #edf3ff;
  --text-secondary: #9fb0c9;
  --text-muted: #607089;
  --accent-green: #33d17a;
  --accent-green-dim: #1f9a59;
  --accent-red: #ff5c7c;
  --accent-yellow: #f6c945;
  --accent-blue: #39a0ff;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  --font-sans: 'IBM Plex Sans', 'Segoe UI', sans-serif;

  display: flex;
  flex-direction: column;
  height: 100%;
  background:
    radial-gradient(circle at top right, rgba(57, 160, 255, 0.09), transparent 28%),
    radial-gradient(circle at bottom left, rgba(51, 209, 122, 0.07), transparent 26%),
    linear-gradient(180deg, #06090f 0%, #05070d 100%);
  color: var(--text-primary);
  font-family: var(--font-sans);
  overflow: hidden;
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(180deg, rgba(11, 16, 24, 0.98), rgba(11, 16, 24, 0.88));
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.02);
}

.header-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header-title h1 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.24em;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.header-subtitle {
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(180deg, rgba(17, 24, 35, 0.92), rgba(10, 15, 22, 0.92));
  border: 1px solid var(--border-accent);
  border-radius: 6px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn:hover:not(:disabled) {
  background: linear-gradient(180deg, rgba(23, 33, 48, 0.96), rgba(14, 20, 31, 0.96));
  border-color: rgba(51, 209, 122, 0.65);
  box-shadow: 0 0 0 1px rgba(51, 209, 122, 0.1);
  color: var(--accent-green);
}

.refresh-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.refresh-icon {
  display: inline-block;
  transition: transform 0.5s ease;
}

.refresh-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes alertPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 92, 124, 0.2); }
  50% { box-shadow: 0 0 0 10px rgba(255, 92, 124, 0); }
}

.dashboard-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border-color);
  overflow: hidden;
}

.top-section,
.devices-section,
.resource-panel,
.alert-panel-wrapper {
  background: rgba(11, 16, 24, 0.96);
  backdrop-filter: blur(12px);
}

.top-section {
  padding: 20px 24px;
}

.status-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.middle-section {
  display: grid;
  grid-template-columns: 340px 1fr;
  background: var(--bg-primary);
  min-height: 340px;
}

.resource-panel {
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.panel-header h2,
.section-header h2 {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.18em;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.panel-badge {
  font-size: 9px;
  padding: 3px 8px;
  background: rgba(57, 160, 255, 0.08);
  border: 1px solid rgba(57, 160, 255, 0.35);
  border-radius: 999px;
  color: var(--accent-blue);
  font-family: var(--font-mono);
  letter-spacing: 0.12em;
}

.resource-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.resource-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(43, 59, 85, 0.75);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(17, 24, 35, 0.98), rgba(10, 14, 21, 0.98)),
    linear-gradient(120deg, rgba(57, 160, 255, 0.08), transparent 40%);
  box-shadow: var(--panel-shadow);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.resource-item:hover {
  transform: translateY(-2px);
  border-color: rgba(57, 160, 255, 0.45);
  box-shadow: 0 20px 36px rgba(0, 0, 0, 0.28);
}

.resource-item.warning {
  border-color: rgba(246, 201, 69, 0.45);
}

.resource-item.critical {
  border-color: rgba(255, 92, 124, 0.65);
  animation: alertPulse 2.4s infinite;
}

.resource-topline,
.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.resource-name,
.resource-meta,
.resource-context,
.net-label,
.stat-badge {
  font-family: var(--font-mono);
}

.resource-name {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--text-muted);
}

.resource-trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-family: var(--font-mono);
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.resource-trend.up {
  color: var(--accent-red);
}

.resource-trend.down {
  color: var(--accent-green);
}

.resource-trend.flat {
  color: var(--text-secondary);
}

.trend-arrow {
  font-size: 12px;
}

.resource-value {
  font-size: 26px;
  font-weight: 350;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.resource-context {
  font-size: 10px;
  color: var(--text-secondary);
}

.resource-bar {
  height: 8px;
  background: rgba(6, 9, 15, 0.95);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(43, 59, 85, 0.6);
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.45s ease, filter 0.3s ease;
  box-shadow: inset 0 0 18px rgba(255, 255, 255, 0.08);
}

.bar-fill.cpu {
  background: linear-gradient(90deg, #1fbf75 0%, #33d17a 45%, #82f7b7 100%);
}

.bar-fill.memory {
  background: linear-gradient(90deg, #2368b5 0%, #39a0ff 45%, #8ed0ff 100%);
}

.bar-fill.disk {
  background: linear-gradient(90deg, #9d7a18 0%, #f6c945 50%, #ffe38a 100%);
}

.bar-fill.warning {
  filter: saturate(1.2);
}

.bar-fill.critical {
  background: linear-gradient(90deg, #7f1830 0%, #ff5c7c 55%, #ff95a9 100%);
}

.resource-meta {
  font-size: 10px;
  color: var(--text-muted);
}

.network-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.net-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: linear-gradient(180deg, rgba(23, 33, 48, 0.9), rgba(12, 18, 27, 0.9));
  border: 1px solid rgba(43, 59, 85, 0.68);
  border-radius: 8px;
}

.net-label {
  font-size: 9px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.net-value {
  font-size: 14px;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.alert-panel-wrapper {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.devices-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
}

.device-stats {
  display: flex;
  gap: 8px;
}

.stat-badge {
  font-size: 9px;
  padding: 4px 9px;
  background: rgba(17, 24, 35, 0.92);
  border: 1px solid var(--border-accent);
  border-radius: 999px;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

.stat-badge.online {
  color: var(--accent-green);
  border-color: rgba(51, 209, 122, 0.45);
  background: rgba(51, 209, 122, 0.08);
}

.stat-badge.offline {
  color: #c39aa8;
  border-color: rgba(255, 92, 124, 0.18);
}

.devices-grid {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
  align-content: start;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.empty-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.empty-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

::-webkit-scrollbar-thumb {
  background: var(--border-accent);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

@media (max-width: 1100px) {
  .status-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .middle-section {
    grid-template-columns: 1fr;
  }

  .resource-panel {
    border-right: 0;
    border-bottom: 1px solid var(--border-color);
  }
}

@media (max-width: 720px) {
  .dashboard-header,
  .top-section,
  .section-header,
  .devices-grid {
    padding-left: 16px;
    padding-right: 16px;
  }

  .status-cards {
    grid-template-columns: 1fr;
  }

  .resource-list {
    padding: 12px;
  }

  .resource-header,
  .resource-topline {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
