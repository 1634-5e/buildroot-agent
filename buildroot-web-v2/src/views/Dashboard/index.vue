<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDeviceStore, useSystemStore } from '@/stores'
import Card from 'primevue/card'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'

const router = useRouter()
const deviceStore = useDeviceStore()
const systemStore = useSystemStore()

// 统计数据
const stats = computed(() => ({
  total: deviceStore.devices.length,
  online: deviceStore.onlineDevices.length,
  offline: deviceStore.offlineDevices.length,
  unsynced: deviceStore.unsyncedDevices.length,
}))

const resources = computed(() => systemStore.stats.resources)

// 定时刷新
let refreshInterval: ReturnType<typeof setInterval> | null = null

async function refresh() {
  await Promise.all([
    deviceStore.fetchDevices(),
    systemStore.fetchStats(),
  ])
}

function goToDevices() {
  router.push('/devices')
}

function goToRegister() {
  router.push('/devices/register')
}

onMounted(() => {
  refresh()
  refreshInterval = setInterval(refresh, 10000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="dashboard space-y-6">
    <!-- 顶部统计卡片 -->
    <div class="grid grid-cols-4 gap-4">
      <Card class="stat-card">
        <template #content>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-secondary text-sm">设备总数</p>
              <p class="text-3xl font-semibold mt-1">{{ stats.total }}</p>
            </div>
            <div class="w-12 h-12 rounded-full bg-primary-500/10 flex items-center justify-center">
              <i class="pi pi-desktop text-primary-400 text-xl"></i>
            </div>
          </div>
        </template>
      </Card>

      <Card class="stat-card">
        <template #content>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-secondary text-sm">在线设备</p>
              <p class="text-3xl font-semibold mt-1 text-success">{{ stats.online }}</p>
            </div>
            <div class="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center">
              <i class="pi pi-check-circle text-success text-xl"></i>
            </div>
          </div>
        </template>
      </Card>

      <Card class="stat-card">
        <template #content>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-secondary text-sm">离线设备</p>
              <p class="text-3xl font-semibold mt-1 text-danger">{{ stats.offline }}</p>
            </div>
            <div class="w-12 h-12 rounded-full bg-danger/10 flex items-center justify-center">
              <i class="pi pi-times-circle text-danger text-xl"></i>
            </div>
          </div>
        </template>
      </Card>

      <Card class="stat-card">
        <template #content>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-secondary text-sm">待同步</p>
              <p class="text-3xl font-semibold mt-1 text-warning">{{ stats.unsynced }}</p>
            </div>
            <div class="w-12 h-12 rounded-full bg-warning/10 flex items-center justify-center">
              <i class="pi pi-sync text-warning text-xl"></i>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <!-- 资源监控 -->
    <div class="grid grid-cols-2 gap-4">
      <Card>
        <template #title>
          <span class="text-surface-200">资源使用</span>
        </template>
        <template #content>
          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-sm mb-2">
                <span class="text-secondary">CPU 使用率</span>
                <span class="font-mono">{{ resources.avg_cpu.toFixed(1) }}%</span>
              </div>
              <ProgressBar :value="resources.avg_cpu" :showValue="false" 
                :pt="{ value: { class: resources.avg_cpu > 80 ? 'bg-danger' : 'bg-success' } }" />
            </div>
            <div>
              <div class="flex justify-between text-sm mb-2">
                <span class="text-secondary">内存使用率</span>
                <span class="font-mono">{{ resources.avg_memory.toFixed(1) }}%</span>
              </div>
              <ProgressBar :value="resources.avg_memory" :showValue="false" 
                :pt="{ value: { class: resources.avg_memory > 80 ? 'bg-danger' : 'bg-primary-400' } }" />
            </div>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>
          <span class="text-surface-200">快速操作</span>
        </template>
        <template #content>
          <div class="flex gap-3">
            <Button label="设备管理" icon="pi pi-desktop" @click="goToDevices" />
            <Button label="注册设备" icon="pi pi-plus" severity="secondary" @click="goToRegister" />
          </div>
        </template>
      </Card>
    </div>

    <!-- 设备列表预览 -->
    <Card>
      <template #title>
        <div class="flex items-center justify-between">
          <span class="text-surface-200">设备概览</span>
          <Button label="查看全部" link size="small" @click="goToDevices" />
        </div>
      </template>
      <template #content>
        <div v-if="deviceStore.loading" class="text-center py-8 text-secondary">
          加载中...
        </div>
        <div v-else-if="deviceStore.devices.length === 0" class="text-center py-8 text-secondary">
          暂无设备，点击"注册设备"添加第一个设备
        </div>
        <div v-else class="grid grid-cols-4 gap-3">
          <div 
            v-for="device in deviceStore.devices.slice(0, 8)" 
            :key="device.id"
            class="device-mini-card p-3 bg-surface-800/50 rounded-lg border border-surface-700 hover:border-primary-500 cursor-pointer transition-colors"
            @click="router.push(`/devices/${device.id}`)"
          >
            <div class="flex items-center gap-2">
              <span class="status-dot" :class="device.is_online ? 'status-dot--online' : 'status-dot--offline'"></span>
              <span class="text-sm font-medium truncate">{{ device.name || device.id.slice(0, 8) }}</span>
            </div>
            <p class="text-xs text-secondary mt-1">
              {{ device.type || '未分类' }}
            </p>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.stat-card :deep(.p-card-body) {
  padding: 1rem;
}
</style>