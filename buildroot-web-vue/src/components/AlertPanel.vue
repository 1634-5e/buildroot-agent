<template>
  <div class="alert-panel">
    <div class="panel-header">
      <h2>ALERTS & EVENTS</h2>
      <span class="panel-badge">LIVE</span>
    </div>

    <div class="alert-list">
      <div 
        v-for="(item, index) in combinedItems" 
        :key="index"
        class="alert-item"
        :class="`alert-${item.type}`"
        @click="handleItemClick(item)"
      >
        <div class="alert-icon">{{ getAlertIcon(item.type) }}</div>
        <div class="alert-content">
          <div class="alert-message">{{ item.message }}</div>
          <div class="alert-time">{{ formatTime(item.timestamp) }}</div>
        </div>
        <div v-if="item.deviceId" class="alert-device">{{ item.deviceId.slice(0, 8) }}</div>
      </div>

      <div v-if="combinedItems.length === 0" class="empty-alerts">
        <div class="empty-icon">✓</div>
        <p class="empty-text">No active alerts</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Alert, Event } from '@/types/system'

interface Props {
  alerts?: Alert[]
  events?: Event[]
}

const props = withDefaults(defineProps<Props>(), {
  alerts: () => [],
  events: () => []
})

const emit = defineEmits<{
  acknowledge: [alertId: string]
}>()

interface CombinedItem {
  id: string
  type: 'critical' | 'warning' | 'success' | 'info'
  message: string
  timestamp: number
  deviceId?: string
}

const combinedItems = computed<CombinedItem[]>(() => {
  const alertItems: CombinedItem[] = props.alerts
    .filter(a => !a.acknowledged)
    .map(a => ({
      id: a.id,
      type: a.type as 'critical' | 'warning' | 'success' | 'info',
      message: a.message,
      timestamp: new Date(a.timestamp).getTime(),
      deviceId: a.deviceId
    }))

  const eventItems: CombinedItem[] = props.events.map(e => ({
    id: e.id,
    type: e.type === 'command' ? 'info' : 
          e.type === 'file' ? 'success' : 
          e.type === 'connection' ? 'success' : 'info',
    message: e.message,
    timestamp: new Date(e.timestamp).getTime(),
    deviceId: e.deviceId
  }))

  return [...alertItems, ...eventItems]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 10)
})

const getAlertIcon = (type: string) => {
  const icons = {
    critical: '⚠',
    warning: '⚡',
    success: '✓',
    info: 'ℹ'
  }
  return icons[type as keyof typeof icons] || '•'
}

const formatTime = (timestamp: number) => {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)

  if (hours > 0) {
    return `${hours}h ago`
  }
  if (minutes > 0) {
    return `${minutes}m ago`
  }
  return 'Just now'
}

const handleItemClick = (item: CombinedItem) => {
  const alert = props.alerts.find(a => a.id === item.id)
  if (alert) {
    emit('acknowledge', alert.id)
  }
  if (item.deviceId) {
    console.log('Navigate to device:', item.deviceId)
  }
}
</script>

<style scoped>
.alert-panel {
  display: flex;
  flex-direction: column;
  background: #111118;
  border-left: 1px solid #252530;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #252530;
}

.panel-header h2 {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.15em;
  color: #9898a8;
}

.panel-badge {
  font-size: 9px;
  padding: 3px 8px;
  background: rgba(255, 51, 102, 0.1);
  border: 1px solid #ff3366;
  border-radius: 3px;
  color: #ff3366;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  letter-spacing: 0.1em;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.alert-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #16161f;
  border: 1px solid #252530;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.alert-item:hover {
  border-color: #2f2f3a;
  background: #1a1a25;
}

.alert-item.alert-critical {
  border-left: 3px solid #ff3366;
}

.alert-item.alert-warning {
  border-left: 3px solid #ffcc00;
}

.alert-item.alert-success {
  border-left: 3px solid #00ff88;
}

.alert-item.alert-info {
  border-left: 3px solid #0099ff;
}

.alert-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

.alert-item.alert-critical .alert-icon {
  color: #ff3366;
}

.alert-item.alert-warning .alert-icon {
  color: #ffcc00;
}

.alert-item.alert-success .alert-icon {
  color: #00ff88;
}

.alert-item.alert-info .alert-icon {
  color: #0099ff;
}

.alert-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alert-message {
  font-size: 11px;
  color: #e4e4ec;
  font-weight: 500;
}

.alert-time {
  font-size: 9px;
  color: #606075;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

.alert-device {
  font-size: 9px;
  padding: 4px 8px;
  background: #0a0a0f;
  border: 1px solid #2f2f3a;
  border-radius: 3px;
  color: #9898a8;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  letter-spacing: 0.05em;
}

.empty-alerts {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 32px;
  color: #00ff88;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  margin: 0;
  font-size: 11px;
  color: #606075;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  letter-spacing: 0.1em;
}

.alert-list::-webkit-scrollbar {
  width: 6px;
}

.alert-list::-webkit-scrollbar-track {
  background: #0a0a0f;
}

.alert-list::-webkit-scrollbar-thumb {
  background: #2f2f3a;
  border-radius: 3px;
}

.alert-list::-webkit-scrollbar-thumb:hover {
  background: #606075;
}
</style>
