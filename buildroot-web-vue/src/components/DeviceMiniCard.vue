<template>
  <div 
    class="device-mini-card"
    :class="{ 
      online: device.is_online, 
      offline: !device.is_online,
      critical: isCritical,
      selected: selected
    }"
    @click="$emit('select', device.id)"
  >
    <div class="mini-status" :class="{ online: device.is_online, offline: !device.is_online }"></div>
    <div class="mini-info">
      <div class="mini-name">{{ shortName }}</div>
      <div class="mini-cpu" :class="{ critical: isCritical }">{{ cpuValue }}</div>
    </div>
    <div v-if="isCritical" class="mini-warning">⚠</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Device } from '@/types/device'

interface Props {
  device: Device
  selected?: boolean
}

const props = defineProps<Props>()
defineEmits<{
  select: [id: string]
}>()

const shortName = computed(() => {
  const name = props.device.name || props.device.id
  return name.length > 8 ? name.slice(0, 8) : name
})

const cpuValue = computed(() => {
  if (!props.device.is_online) return 'off'
  const cpu = props.device.current_status?.cpu_usage || 0
  return `${Math.round(cpu)}%`
})

const isCritical = computed(() => {
  if (!props.device.is_online) return false
  const cpu = props.device.current_status?.cpu_usage || 0
  return cpu > 80
})
</script>

<style scoped>
.device-mini-card {
  position: relative;
  background: #111118;
  border: 1px solid #252530;
  border-radius: 4px;
  padding: 8px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
}

.device-mini-card:hover {
  border-color: #2f2f3a;
  background: #16161f;
}

.device-mini-card.selected {
  border-color: #00ff88;
  box-shadow: 0 0 0 2px rgba(0, 255, 136, 0.1);
}

.device-mini-card.online {
  border-left: 2px solid #00ff88;
}

.device-mini-card.offline {
  border-left: 2px solid #606075;
  opacity: 0.5;
}

.device-mini-card.critical {
  border-color: #ff3366;
  background: rgba(255, 51, 102, 0.05);
}

.mini-status {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.mini-status.online {
  background: #00ff88;
  box-shadow: 0 0 6px #00ff88;
}

.mini-status.offline {
  background: #606075;
}

.mini-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mini-name {
  font-size: 11px;
  font-weight: 600;
  color: #e4e4ec;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

.mini-cpu {
  font-size: 14px;
  font-weight: 300;
  color: #e4e4ec;
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

.mini-cpu.critical {
  color: #ff3366;
  font-weight: 500;
}

.mini-warning {
  font-size: 10px;
  flex-shrink: 0;
  color: #ff3366;
}
</style>
