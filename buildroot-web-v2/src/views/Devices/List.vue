<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Card from 'primevue/card'

const router = useRouter()
const deviceStore = useDeviceStore()

// 筛选
const searchQuery = ref('')
const statusFilter = ref<string | null>(null)
const typeFilter = ref<string | null>(null)

const statusOptions = [
  { label: '全部状态', value: null },
  { label: '在线', value: 'online' },
  { label: '离线', value: 'offline' },
]

// 过滤后的设备列表
const filteredDevices = computed(() => {
  let result = deviceStore.devices
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(d => 
      d.name.toLowerCase().includes(query) || 
      d.id.toLowerCase().includes(query)
    )
  }
  
  if (statusFilter.value) {
    result = result.filter(d => 
      statusFilter.value === 'online' ? d.is_online : !d.is_online
    )
  }
  
  if (typeFilter.value) {
    result = result.filter(d => d.type === typeFilter.value)
  }
  
  return result
})

// 状态标签
function getStatusSeverity(device: { is_online: boolean }) {
  return device.is_online ? 'success' : 'danger'
}

function getStatusLabel(device: { is_online: boolean }) {
  return device.is_online ? '在线' : '离线'
}

// 导航
function goToDetail(deviceId: string) {
  router.push(`/devices/${deviceId}`)
}

function goToTwin(deviceId: string) {
  router.push(`/devices/${deviceId}/twin`)
}

function goToRegister() {
  router.push('/devices/register')
}

// 初始化
onMounted(() => {
  deviceStore.fetchDevices()
})
</script>

<template>
  <div class="devices-page space-y-4">
    <!-- 工具栏 -->
    <Card>
      <template #content>
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-3 flex-1">
            <span class="p-input-icon-left flex-1 max-w-xs">
              <i class="pi pi-search" />
              <InputText 
                v-model="searchQuery" 
                placeholder="搜索设备..." 
                class="w-full"
              />
            </span>
            <Select 
              v-model="statusFilter" 
              :options="statusOptions" 
              optionLabel="label"
              optionValue="value"
              placeholder="状态筛选"
              class="w-32"
            />
          </div>
          <Button label="注册设备" icon="pi pi-plus" @click="goToRegister" />
        </div>
      </template>
    </Card>

    <!-- 设备表格 -->
    <Card>
      <template #content>
        <DataTable 
          :value="filteredDevices" 
          :loading="deviceStore.loading"
          stripedRows
          paginator
          :rows="10"
          :rowsPerPageOptions="[10, 20, 50]"
          tableStyle="min-width: 50rem"
        >
          <Column field="name" header="名称" sortable>
            <template #body="{ data }">
              <div class="flex items-center gap-2">
                <span class="status-dot" :class="data.is_online ? 'status-dot--online' : 'status-dot--offline'"></span>
                <span class="font-medium">{{ data.name || data.id.slice(0, 12) }}</span>
              </div>
            </template>
          </Column>
          
          <Column field="type" header="类型" sortable>
            <template #body="{ data }">
              <span class="text-secondary">{{ data.type || '-' }}</span>
            </template>
          </Column>
          
          <Column field="status" header="状态" sortable>
            <template #body="{ data }">
              <Tag :value="getStatusLabel(data)" :severity="getStatusSeverity(data)" />
            </template>
          </Column>
          
          <Column field="version" header="版本">
            <template #body="{ data }">
              <code class="text-xs bg-surface-800 px-2 py-1 rounded">{{ data.firmware_version || '-' }}</code>
            </template>
          </Column>
          
          <Column field="ip" header="IP 地址">
            <template #body="{ data }">
              <span class="font-mono text-sm">{{ data.ip_addr || '-' }}</span>
            </template>
          </Column>
          
          <Column header="操作" :exportable="false">
            <template #body="{ data }">
              <div class="flex gap-2">
                <Button icon="pi pi-eye" size="small" outlined @click="goToDetail(data.id)" v-tooltip="'详情'" />
                <Button icon="pi pi-cog" size="small" outlined @click="goToTwin(data.id)" v-tooltip="'Twin'" />
              </div>
            </template>
          </Column>
          
          <template #empty>
            <div class="text-center py-8 text-secondary">
              <i class="pi pi-inbox text-4xl mb-4 block"></i>
              <p>暂无设备</p>
              <Button label="注册设备" icon="pi pi-plus" class="mt-4" @click="goToRegister" />
            </div>
          </template>
        </DataTable>
      </template>
    </Card>
  </div>
</template>