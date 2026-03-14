<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'

const route = useRoute()
const router = useRouter()
const deviceStore = useDeviceStore()

const deviceId = computed(() => route.params.id as string)
const device = computed(() => 
  deviceStore.devices.find(d => d.id === deviceId.value)
)

const status = computed(() => device.value?.current_status)

// 格式化字节
function formatBytes(bytes?: number) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

// 格式化运行时间
function formatUptime(seconds?: number) {
  if (!seconds) return 'N/A'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) return `${days}天 ${hours}小时`
  if (hours > 0) return `${hours}小时 ${mins}分钟`
  return `${mins}分钟`
}

function goToTwin() {
  router.push(`/devices/${deviceId.value}/twin`)
}

function goToTerminal() {
  router.push(`/terminal/${deviceId.value}`)
}

function goBack() {
  router.push('/devices')
}

onMounted(() => {
  if (!deviceStore.devices.length) {
    deviceStore.fetchDevices()
  }
})
</script>

<template>
  <div class="device-detail space-y-4">
    <!-- 顶部 -->
    <Card>
      <template #content>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <Button icon="pi pi-arrow-left" outlined @click="goBack" />
            <div>
              <h2 class="text-xl font-semibold">
                {{ device?.name || deviceId.slice(0, 12) }}
              </h2>
              <p class="text-secondary text-sm font-mono">{{ deviceId }}</p>
            </div>
            <Tag 
              :value="device?.is_online ? '在线' : '离线'" 
              :severity="device?.is_online ? 'success' : 'danger'"
            />
          </div>
          
          <div class="flex gap-2">
            <Button label="Twin 管理" icon="pi pi-cog" outlined @click="goToTwin" />
            <Button 
              label="终端" 
              icon="pi pi-terminal" 
              outlined 
              :disabled="!device?.is_online"
              @click="goToTerminal"
            />
          </div>
        </div>
      </template>
    </Card>

    <!-- 资源监控 -->
    <div class="grid grid-cols-3 gap-4">
      <Card>
        <template #title>
          <div class="flex items-center gap-2">
            <i class="pi pi-bolt text-warning"></i>
            <span>CPU</span>
          </div>
        </template>
        <template #content>
          <div class="text-3xl font-light mb-2">
            {{ status?.cpu_usage?.toFixed(1) || 0 }}%
          </div>
          <ProgressBar :value="status?.cpu_usage || 0" :showValue="false" />
          <p class="text-secondary text-sm mt-2">
            负载: {{ status?.load_avg?.join(', ') || 'N/A' }}
          </p>
        </template>
      </Card>

      <Card>
        <template #title>
          <div class="flex items-center gap-2">
            <i class="pi pi-database text-primary-400"></i>
            <span>内存</span>
          </div>
        </template>
        <template #content>
          <div class="text-3xl font-light mb-2">
            {{ status?.mem_usage_percent?.toFixed(1) || 0 }}%
          </div>
          <ProgressBar :value="status?.mem_usage_percent || 0" :showValue="false" />
          <p class="text-secondary text-sm mt-2">
            {{ formatBytes(status?.mem_used) }} / {{ formatBytes(status?.mem_total) }}
          </p>
        </template>
      </Card>

      <Card>
        <template #title>
          <div class="flex items-center gap-2">
            <i class="pi pi-hdd text-success"></i>
            <span>磁盘</span>
          </div>
        </template>
        <template #content>
          <div class="text-3xl font-light mb-2">
            {{ status?.disk_usage_percent?.toFixed(1) || 0 }}%
          </div>
          <ProgressBar :value="status?.disk_usage_percent || 0" :showValue="false" />
          <p class="text-secondary text-sm mt-2">
            {{ formatBytes(status?.disk_used) }} / {{ formatBytes(status?.disk_total) }}
          </p>
        </template>
      </Card>
    </div>

    <!-- 设备信息 -->
    <Card>
      <template #title>设备信息</template>
      <template #content>
        <div class="grid grid-cols-3 gap-4">
          <div>
            <label class="text-xs text-secondary block mb-1">类型</label>
            <span>{{ device?.type || '-' }}</span>
          </div>
          <div>
            <label class="text-xs text-secondary block mb-1">固件版本</label>
            <code class="text-sm">{{ device?.firmware_version || '-' }}</code>
          </div>
          <div>
            <label class="text-xs text-secondary block mb-1">硬件版本</label>
            <code class="text-sm">{{ device?.hardware_version || '-' }}</code>
          </div>
          <div>
            <label class="text-xs text-secondary block mb-1">IP 地址</label>
            <code class="text-sm">{{ status?.ip_addr || device?.ip_addr || '-' }}</code>
          </div>
          <div>
            <label class="text-xs text-secondary block mb-1">主机名</label>
            <span>{{ status?.hostname || '-' }}</span>
          </div>
          <div>
            <label class="text-xs text-secondary block mb-1">内核版本</label>
            <code class="text-sm">{{ status?.kernel || '-' }}</code>
          </div>
          <div>
            <label class="text-xs text-secondary block mb-1">运行时间</label>
            <span>{{ formatUptime(status?.uptime) }}</span>
          </div>
          <div>
            <label class="text-xs text-secondary block mb-1">最后上线</label>
            <span>{{ device?.last_seen_at ? new Date(device.last_seen_at).toLocaleString('zh-CN') : '-' }}</span>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>