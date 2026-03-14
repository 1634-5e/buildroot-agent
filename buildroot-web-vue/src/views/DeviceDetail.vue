<template>
  <div class="device-detail">
    <!-- 顶部导航 -->
    <header class="detail-header">
      <button class="back-btn" @click="goBack">
        <span class="back-icon">←</span>
        <span>返回</span>
      </button>
      <div class="device-title">
        <div class="status-indicator" :class="device?.is_online ? 'online' : 'offline'"></div>
        <h1>{{ device?.name || `设备 ${deviceId?.slice(0, 8)}` }}</h1>
      </div>
      <div class="header-actions">
        <button class="action-btn" @click="openTerminal" :disabled="!device?.is_online">
          <span>终端</span>
        </button>
        <button class="action-btn" @click="openFiles" :disabled="!device?.is_online">
          <span>文件</span>
        </button>
      </div>
    </header>

    <!-- 主要内容 -->
    <div class="detail-content">
      <!-- 实时监控 -->
      <section class="monitor-section">
        <div class="section-header">
          <h2>实时监控</h2>
          <span class="update-time">最后更新: {{ lastUpdate }}</span>
        </div>

        <div class="metrics-grid">
          <!-- CPU 使用率 -->
          <div class="metric-card">
            <div class="metric-header">
              <span class="metric-icon">⚡</span>
              <span class="metric-name">CPU 使用率</span>
            </div>
            <div class="metric-value-large">
              {{ currentStatus?.cpu_usage?.toFixed(1) || 0 }}%
            </div>
            <div class="metric-chart">
              <div class="chart-bar">
                <div 
                  class="chart-fill cpu" 
                  :style="{ width: (currentStatus?.cpu_usage || 0) + '%' }"
                ></div>
              </div>
            </div>
            <div class="metric-meta">
              <span>负载: {{ currentStatus?.load_avg?.toFixed(2) || 'N/A' }}</span>
            </div>
          </div>

          <!-- 内存使用 -->
          <div class="metric-card">
            <div class="metric-header">
              <span class="metric-icon">💾</span>
              <span class="metric-name">内存使用</span>
            </div>
            <div class="metric-value-large">
              {{ currentStatus?.mem_usage_percent?.toFixed(1) || 0 }}%
            </div>
            <div class="metric-chart">
              <div class="chart-bar">
                <div 
                  class="chart-fill memory" 
                  :style="{ width: (currentStatus?.mem_usage_percent || 0) + '%' }"
                ></div>
              </div>
            </div>
            <div class="metric-meta">
              <span>{{ formatBytes(currentStatus?.mem_used) }} / {{ formatBytes(currentStatus?.mem_total) }}</span>
            </div>
          </div>

          <!-- 磁盘使用 -->
          <div class="metric-card">
            <div class="metric-header">
              <span class="metric-icon">💿</span>
              <span class="metric-name">磁盘使用</span>
            </div>
            <div class="metric-value-large">
              {{ currentStatus?.disk_usage_percent?.toFixed(1) || 0 }}%
            </div>
            <div class="metric-chart">
              <div class="chart-bar">
                <div 
                  class="chart-fill disk" 
                  :style="{ width: (currentStatus?.disk_usage_percent || 0) + '%' }"
                ></div>
              </div>
            </div>
            <div class="metric-meta">
              <span>{{ formatBytes(currentStatus?.disk_used) }} / {{ formatBytes(currentStatus?.disk_total) }}</span>
            </div>
          </div>

          <!-- 网络流量 -->
          <div class="metric-card">
            <div class="metric-header">
              <span class="metric-icon">🌐</span>
              <span class="metric-name">网络流量</span>
            </div>
            <div class="network-stats">
              <div class="net-stat">
                <span class="net-label">↑ 发送</span>
                <span class="net-value">{{ formatBytes(currentStatus?.net_tx_bytes) }}</span>
              </div>
              <div class="net-stat">
                <span class="net-label">↓ 接收</span>
                <span class="net-value">{{ formatBytes(currentStatus?.net_rx_bytes) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 设备信息 -->
      <section class="info-section">
        <div class="section-header">
          <h2>设备信息</h2>
        </div>

        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">设备 ID</span>
            <span class="info-value mono">{{ device?.id }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">状态</span>
            <span class="info-value" :class="device?.is_online ? 'online' : 'offline'">
              {{ device?.is_online ? '在线' : '离线' }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">版本</span>
            <span class="info-value">{{ device?.version || 'N/A' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">最后上线</span>
            <span class="info-value">{{ formatTime(device?.last_seen_at) }}</span>
          </div>
          <div class="info-item" v-if="currentStatus?.hostname">
            <span class="info-label">主机名</span>
            <span class="info-value">{{ currentStatus?.hostname }}</span>
          </div>
          <div class="info-item" v-if="currentStatus?.kernel">
            <span class="info-label">内核版本</span>
            <span class="info-value mono">{{ currentStatus?.kernel }}</span>
          </div>
          <div class="info-item" v-if="currentStatus?.uptime">
            <span class="info-label">运行时间</span>
            <span class="info-value">{{ formatUptime(currentStatus?.uptime) }}</span>
          </div>
          <div class="info-item" v-if="currentStatus?.ip_addr">
            <span class="info-label">IP 地址</span>
            <span class="info-value mono">{{ currentStatus?.ip_addr }}</span>
          </div>
        </div>
      </section>

      <!-- Ping 监控 -->
      <section class="ping-section" v-if="pingTargets.length > 0">
        <div class="section-header">
          <h2>Ping 监控</h2>
          <span class="ping-count">{{ pingTargets.length }} 个目标</span>
        </div>

        <div class="ping-list">
          <div 
            v-for="target in pingTargets" 
            :key="target.host"
            class="ping-item"
            :class="{ success: target.status === 'success', failed: target.status === 'failed' }"
          >
            <div class="ping-status">
              <span class="ping-dot" :class="target.status"></span>
            </div>
            <div class="ping-info">
              <span class="ping-host">{{ target.host }}</span>
              <span class="ping-meta" v-if="target.status === 'success'">
                {{ target.rtt?.toFixed(1) }} ms
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- 历史数据 -->
      <section class="history-section">
        <div class="section-header">
          <h2>历史数据</h2>
        </div>

        <div class="history-placeholder">
          <span class="placeholder-icon">📊</span>
          <p>历史数据图表功能开发中...</p>
          <p class="placeholder-hint">将显示 CPU、内存、网络的历史趋势</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores/device'

const route = useRoute()
const router = useRouter()
const deviceStore = useDeviceStore()

const deviceId = computed(() => route.params.id as string || route.query.device as string)
const device = computed(() => devices.value.find(d => d.id === deviceId.value))
const devices = computed(() => deviceStore.devices)

const currentStatus = computed(() => device.value?.current_status)
const pingTargets = ref<any[]>([])

const lastUpdate = ref('')
const refreshInterval = ref<NodeJS.Timeout | null>(null)

const goBack = () => {
  router.back()
}

const openTerminal = () => {
  router.push({ path: '/terminal', query: { device: deviceId.value } })
}

const openFiles = () => {
  router.push({ path: '/filemanager', query: { device: deviceId.value } })
}

const formatBytes = (bytes?: number) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i]
}

const formatTime = (timestamp?: string) => {
  if (!timestamp) return 'N/A'
  return new Date(timestamp).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatUptime = (seconds?: number) => {
  if (!seconds) return 'N/A'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) return `${days}天 ${hours}小时`
  if (hours > 0) return `${hours}小时 ${mins}分钟`
  return `${mins}分钟`
}

const updateLastTime = () => {
  lastUpdate.value = new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const refresh = async () => {
  await deviceStore.fetchDevices()
  updateLastTime()
}

watch(deviceId, () => {
  if (deviceId.value) {
    refresh()
  }
})

onMounted(() => {
  refresh()
  updateLastTime()
  refreshInterval.value = setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
</script>

<style scoped>
/* 基础变量 */
.device-detail {
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
  --accent-blue: #0099ff;
  --accent-yellow: #ffcc00;
  --accent-red: #ff3366;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --font-sans: 'SF Pro Display', -apple-system, sans-serif;
  
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-sans);
  overflow: hidden;
}

/* 顶部导航 */
.detail-header {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 24px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  background: var(--bg-tertiary);
  border-color: var(--accent-green);
  color: var(--accent-green);
}

.back-icon {
  font-size: 16px;
}

.device-title {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-indicator.online {
  background: var(--accent-green);
  box-shadow: 0 0 8px var(--accent-green);
}

.status-indicator.offline {
  background: var(--text-muted);
}

.device-title h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 8px 16px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: var(--bg-elevated);
  border-color: var(--accent-green);
  color: var(--accent-green);
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* 主要内容 */
.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

/* 区块样式 */
section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-header h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.update-time {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* 指标网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.metric-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.metric-icon {
  font-size: 18px;
}

.metric-name {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.metric-value-large {
  font-size: 36px;
  font-weight: 300;
  font-family: var(--font-mono);
  color: var(--text-primary);
  margin-bottom: 12px;
}

.metric-chart {
  margin-bottom: 12px;
}

.chart-bar {
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  overflow: hidden;
}

.chart-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.chart-fill.cpu {
  background: linear-gradient(90deg, var(--accent-green), #00cc6a);
}

.chart-fill.memory {
  background: linear-gradient(90deg, var(--accent-blue), #0077cc);
}

.chart-fill.disk {
  background: linear-gradient(90deg, var(--accent-yellow), #cc9900);
}

.metric-meta {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* 网络统计 */
.network-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.net-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.net-label {
  font-size: 12px;
  color: var(--text-muted);
}

.net-value {
  font-size: 14px;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

/* 设备信息 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
}

.info-label {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.info-value {
  font-size: 14px;
  color: var(--text-primary);
}

.info-value.mono {
  font-family: var(--font-mono);
  font-size: 12px;
}

.info-value.online {
  color: var(--accent-green);
}

.info-value.offline {
  color: var(--text-muted);
}

/* Ping 监控 */
.ping-count {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.ping-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.ping-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
}

.ping-item.success {
  border-left: 2px solid var(--accent-green);
}

.ping-item.failed {
  border-left: 2px solid var(--accent-red);
}

.ping-status {
  display: flex;
  align-items: center;
}

.ping-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.ping-dot.success {
  background: var(--accent-green);
  box-shadow: 0 0 6px var(--accent-green);
}

.ping-dot.failed {
  background: var(--accent-red);
}

.ping-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ping-host {
  font-size: 13px;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.ping-meta {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* 历史数据占位符 */
.history-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background: var(--bg-secondary);
  border: 1px dashed var(--border-accent);
  border-radius: 8px;
  text-align: center;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.history-placeholder p {
  margin: 4px 0;
  color: var(--text-secondary);
}

.placeholder-hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* 滚动条样式 */
.detail-content::-webkit-scrollbar {
  width: 6px;
}

.detail-content::-webkit-scrollbar-track {
  background: var(--bg-primary);
}

.detail-content::-webkit-scrollbar-thumb {
  background: var(--border-accent);
  border-radius: 3px;
}

.detail-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
</style>