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
            <div class="resource-item">
              <div class="resource-header">
                <span class="resource-name">CPU USAGE</span>
                <span class="resource-value">{{ systemStore.stats.resources.avg_cpu.toFixed(1) }}%</span>
              </div>
              <div class="resource-bar">
                <div
                  class="bar-fill"
                  :style="{ width: systemStore.stats.resources.avg_cpu + '%' }"
                  :class="getBarClass(systemStore.stats.resources.avg_cpu)"
                ></div>
              </div>
              <div class="resource-meta">
                <span>Average across {{ systemStore.stats.agents.online }} devices</span>
              </div>
            </div>

            <div class="resource-item">
              <div class="resource-header">
                <span class="resource-name">MEMORY USAGE</span>
                <span class="resource-value">{{ systemStore.stats.resources.avg_memory.toFixed(1) }}%</span>
              </div>
              <div class="resource-bar">
                <div
                  class="bar-fill memory"
                  :style="{ width: systemStore.stats.resources.avg_memory + '%' }"
                  :class="getBarClass(systemStore.stats.resources.avg_memory)"
                ></div>
              </div>
              <div class="resource-meta">
                <span>{{ formatBytes(systemStore.stats.resources.total_memory_used) }} / {{ formatBytes(systemStore.stats.resources.total_memory_total) }}</span>
              </div>
            </div>

            <div class="resource-item">
              <div class="resource-header">
                <span class="resource-name">NETWORK I/O</span>
              </div>
              <div class="network-stats">
                <div class="net-stat">
                  <span class="net-label">TX</span>
                  <span class="net-value">{{ formatBytes(systemStore.stats.resources.total_net_tx) }}/s</span>
                </div>
                <div class="net-stat">
                  <span class="net-label">RX</span>
                  <span class="net-value">{{ formatBytes(systemStore.stats.resources.total_net_rx) }}/s</span>
                </div>
              </div>
            </div>

            <div class="resource-item">
              <div class="resource-header">
                <span class="resource-name">DISK USAGE</span>
                <span class="resource-value">{{ diskPercent.toFixed(1) }}%</span>
              </div>
              <div class="resource-bar">
                <div
                  class="bar-fill disk"
                  :style="{ width: diskPercent + '%' }"
                  :class="getBarClass(diskPercent)"
                ></div>
              </div>
              <div class="resource-meta">
                <span>{{ formatBytes(systemStore.stats.resources.total_disk_used) }} / {{ formatBytes(systemStore.stats.resources.total_disk_total) }}</span>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores/device'
import { useSystemStore } from '@/stores/system'
import SystemStatusCard from '@/components/SystemStatusCard.vue'
import AlertPanel from '@/components/AlertPanel.vue'
import DeviceMiniCard from '@/components/DeviceMiniCard.vue'

const router = useRouter()
const deviceStore = useDeviceStore()
const systemStore = useSystemStore()

const loading = ref(false)
const selectedDevice = ref('')
const refreshInterval = ref<NodeJS.Timeout | null>(null)

const sortedDevices = computed(() => {
  const online = deviceStore.devices.filter(d => d.is_online).sort((a, b) => {
    const cpuA = a.current_status?.cpu_usage || 0
    const cpuB = b.current_status?.cpu_usage || 0
    return cpuB - cpuA
  })
  const offline = deviceStore.devices.filter(d => !d.is_online)
  return [...online, ...offline]
})

const diskPercent = computed(() => {
  const { total_disk_used, total_disk_total } = systemStore.stats.resources
  if (total_disk_total === 0) return 0
  return (total_disk_used / total_disk_total) * 100
})

const refresh = async () => {
  loading.value = true
  await Promise.all([
    deviceStore.fetchDevices(),
    systemStore.refreshAll(),
  ])
  setTimeout(() => loading.value = false, 500)
}

const selectDevice = (deviceId: string) => {
  selectedDevice.value = deviceId
  router.push(`/devicedetail/${deviceId}`)
}

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
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i]
}

onMounted(() => {
  refresh()
  refreshInterval.value = setInterval(refresh, 10000)
})

onUnmounted(() => {
  if (refreshInterval.value) clearInterval(refreshInterval.value)
})
</script>

<style scoped>
.dashboard-container {
  --bg-primary: #0a0a0f;
  --bg-secondary: #111118;
  --bg-tertiary: #16161f;
  --bg-elevated: #1a1a25;
  --border-color: #252530;
  --border-accent: #2f2f3a;
  --text-primary: #e4e4ec;
  --text-secondary: #9898a8;
  --text-muted: #606075;
  --accent-green: #00ff88;
  --accent-green-dim: #00cc6a;
  --accent-red: #ff3366;
  --accent-yellow: #ffcc00;
  --accent-blue: #0099ff;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  --font-sans: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;

  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
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
  background: var(--bg-secondary);
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
  letter-spacing: 0.2em;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.header-subtitle {
  font-size: 10px;
  letter-spacing: 0.15em;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-accent);
  border-radius: 4px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--bg-elevated);
  border-color: var(--accent-green);
  color: var(--accent-green);
}

.refresh-btn:disabled {
  opacity: 0.5;
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

.dashboard-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border-color);
  overflow: hidden;
}

.top-section {
  background: var(--bg-secondary);
  padding: 20px 24px;
}

.status-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.middle-section {
  display: grid;
  grid-template-columns: 320px 1fr;
  background: var(--bg-primary);
  min-height: 300px;
}

.resource-panel {
  background: var(--bg-secondary);
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

.panel-header h2 {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.15em;
  color: var(--text-secondary);
}

.panel-badge {
  font-size: 9px;
  padding: 3px 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-accent);
  border-radius: 3px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  letter-spacing: 0.1em;
}

.resource-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.resource-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.resource-name {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.resource-value {
  font-size: 20px;
  font-weight: 300;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.resource-bar {
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: var(--accent-green);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.bar-fill.memory {
  background: var(--accent-blue);
}

.bar-fill.disk {
  background: var(--accent-yellow);
}

.bar-fill.critical {
  background: var(--accent-red);
}

.bar-fill.warning {
  background: var(--accent-yellow);
}

.resource-meta {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.network-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 8px;
}

.net-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
}

.net-label {
  font-size: 9px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  letter-spacing: 0.1em;
}

.net-value {
  font-size: 14px;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.alert-panel-wrapper {
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.devices-section {
  flex: 1;
  background: var(--bg-secondary);
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

.section-header h2 {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.15em;
  color: var(--text-secondary);
}

.device-stats {
  display: flex;
  gap: 8px;
}

.stat-badge {
  font-size: 9px;
  padding: 4px 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-accent);
  border-radius: 3px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  letter-spacing: 0.05em;
}

.stat-badge.online {
  color: var(--accent-green);
  border-color: var(--accent-green);
  background: rgba(0, 255, 136, 0.1);
}

.stat-badge.offline {
  color: var(--text-muted);
}

.devices-grid {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
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
</style>
