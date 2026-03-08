<template>
  <div class="status-card" :class="cardClass">
    <div class="card-header">
      <span class="card-title">{{ title }}</span>
      <span v-if="badge" class="card-badge" :class="badgeClass">{{ badge }}</span>
    </div>
    <div class="card-body">
      <div class="main-value">{{ mainValue }}</div>
      <div class="sub-value">{{ subValue }}</div>
    </div>
    <div v-if="metrics.length" class="card-metrics">
      <div v-for="(metric, idx) in metrics" :key="idx" class="metric">
        <span class="metric-label">{{ metric.label }}</span>
        <span class="metric-value" :class="metric.valueClass">{{ metric.value }}</span>
      </div>
    </div>
    <div v-if="icon" class="card-icon" :class="iconClass">{{ icon }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ServerStatus, AgentStats, SessionStats, HealthStatus } from '@/types/system'

interface Metric {
  label: string
  value: string
  valueClass?: string
}

interface Props {
  type: 'server' | 'agents' | 'sessions' | 'health'
  serverStatus?: ServerStatus
  agentStats?: AgentStats
  sessionStats?: SessionStats
  healthStatus?: HealthStatus
}

const props = defineProps<Props>()

const title = computed(() => {
  const titles = {
    server: 'SERVER',
    agents: 'AGENTS',
    sessions: 'SESSIONS',
    health: 'HEALTH'
  }
  return titles[props.type]
})

const mainValue = computed(() => {
  switch (props.type) {
    case 'server':
      return props.serverStatus?.status === 'online' ? '● online' : '○ offline'
    case 'agents':
      return `${props.agentStats?.online || 0}/${props.agentStats?.total || 0}`
    case 'sessions':
      return `${props.sessionStats?.active || 0} active`
    case 'health':
      const score = props.healthStatus?.score || 100
      return `▲ ${score}%`
    default:
      return ''
  }
})

const subValue = computed(() => {
  switch (props.type) {
    case 'server':
      return `cpu ${props.serverStatus?.cpu || 0}% · mem ${props.serverStatus?.memory || 0}%`
    case 'agents':
      return `${props.agentStats?.offline || 0} offline`
    case 'sessions':
      const pending = props.sessionStats?.pending || 0
      const files = props.sessionStats?.file_transfers || 0
      const parts = []
      if (pending > 0) parts.push(`${pending} pending`)
      if (files > 0) parts.push(`${files} files`)
      return parts.join(' · ') || 'no activity'
    case 'health':
      return `${props.healthStatus?.alerts || 0} alert${(props.healthStatus?.alerts || 0) !== 1 ? 's' : ''}`
    default:
      return ''
  }
})

const badge = computed(() => {
  switch (props.type) {
    case 'agents':
      return props.agentStats?.offline ? String(props.agentStats.offline) : ''
    case 'sessions':
      const total = (props.sessionStats?.active || 0) + (props.sessionStats?.file_transfers || 0) + (props.sessionStats?.pending || 0)
      return total > 0 ? String(total) : ''
    case 'health':
      return props.healthStatus?.alerts ? String(props.healthStatus.alerts) : ''
    default:
      return ''
  }
})

const badgeClass = computed(() => {
  switch (props.type) {
    case 'agents':
      return props.agentStats?.offline ? 'warning' : ''
    case 'sessions':
      return 'success'
    case 'health':
      return props.healthStatus?.alerts ? 'error' : 'success'
    default:
      return ''
  }
})

const metrics = computed<Metric[]>(() => {
  switch (props.type) {
    case 'server':
      const uptimeHours = Math.floor((props.serverStatus?.uptime || 0) / 3600)
      const uptime = uptimeHours > 24 ? `${Math.floor(uptimeHours / 24)}d` : `${uptimeHours}h`
      return [
        { label: 'UPTIME', value: uptime },
        { label: 'LOAD', value: '0.45', valueClass: 'normal' }
      ]
    case 'agents':
      return [
        { label: 'ACTIVE', value: String(props.agentStats?.online || 0) },
        { label: 'OFFLINE', value: String(props.agentStats?.offline || 0), valueClass: 'warning' }
      ]
    case 'sessions':
      return [
        { label: 'TERM', value: String(props.sessionStats?.active || 0) },
        { label: 'FILES', value: String(props.sessionStats?.file_transfers || 0) }
      ]
    case 'health':
      return [
        { label: 'ALERTS', value: String(props.healthStatus?.alerts || 0), valueClass: props.healthStatus?.alerts ? 'error' : 'normal' },
        { label: 'SCORE', value: String(props.healthStatus?.score || 100), valueClass: props.healthStatus?.score && props.healthStatus.score < 90 ? 'warning' : 'normal' }
      ]
    default:
      return []
  }
})

const icon = computed(() => {
  const icons = {
    server: '◈',
    agents: '◉',
    sessions: '≡',
    health: '⬡'
  }
  return icons[props.type]
})

const iconClass = computed(() => {
  switch (props.type) {
    case 'server':
      return props.serverStatus?.status === 'online' ? 'online' : 'offline'
    case 'agents':
      return props.agentStats?.offline ? 'warning' : 'online'
    case 'sessions':
      return 'online'
    case 'health':
      const score = props.healthStatus?.score || 100
      if (score >= 90) return 'online'
      if (score >= 70) return 'warning'
      return 'error'
    default:
      return ''
  }
})

const cardClass = computed(() => {
  switch (props.type) {
    case 'server':
      return props.serverStatus?.status === 'online' ? 'status-online' : 'status-error'
    case 'agents':
      return props.agentStats?.offline ? 'status-warning' : 'status-online'
    case 'sessions':
      return 'status-online'
    case 'health':
      const score = props.healthStatus?.score || 100
      if (score >= 90) return 'status-online'
      if (score >= 70) return 'status-warning'
      return 'status-error'
    default:
      return 'status-online'
  }
})
</script>

<style scoped>
.status-card {
  position: relative;
  background: #111118;
  border: 1px solid #252530;
  border-radius: 6px;
  padding: 16px;
  transition: all 0.2s;
  overflow: hidden;
}

.status-card:hover {
  border-color: #2f2f3a;
  background: #16161f;
}

.status-card.status-error {
  border-color: #ff3366;
  background: rgba(255, 51, 102, 0.05);
}

.status-card.status-warning {
  border-color: #ffcc00;
  background: rgba(255, 204, 0, 0.05);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.card-title {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.15em;
  color: #9898a8;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

.card-badge {
  font-size: 9px;
  padding: 2px 6px;
  background: #16161f;
  border: 1px solid #2f2f3a;
  border-radius: 3px;
  color: #606075;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  letter-spacing: 0.1em;
}

.card-badge.warning {
  color: #ffcc00;
  border-color: #ffcc00;
  background: rgba(255, 204, 0, 0.1);
}

.card-badge.error {
  color: #ff3366;
  border-color: #ff3366;
  background: rgba(255, 51, 102, 0.1);
}

.card-badge.success {
  color: #00ff88;
  border-color: #00ff88;
  background: rgba(0, 255, 136, 0.1);
}

.card-body {
  margin-bottom: 12px;
}

.main-value {
  font-size: 24px;
  font-weight: 300;
  color: #e4e4ec;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  margin-bottom: 4px;
}

.sub-value {
  font-size: 11px;
  color: #9898a8;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

.card-metrics {
  display: flex;
  gap: 16px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 9px;
  color: #606075;
  letter-spacing: 0.1em;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

.metric-value {
  font-size: 12px;
  color: #e4e4ec;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

.metric-value.warning {
  color: #ffcc00;
}

.metric-value.error {
  color: #ff3366;
}

.card-icon {
  position: absolute;
  right: 12px;
  bottom: 12px;
  font-size: 48px;
  opacity: 0.05;
  color: #e4e4ec;
}

.card-icon.online {
  color: #00ff88;
}

.card-icon.warning {
  color: #ffcc00;
}

.card-icon.error {
  color: #ff3366;
}
</style>
