<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores'
import { twinApi } from '@/api'
import type { TwinOverview, ChangeLog } from '@/types'
import Card from 'primevue/card'
import Button from 'primevue/button'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Tag from 'primevue/tag'
import Timeline from 'primevue/timeline'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const deviceStore = useDeviceStore()

const deviceId = computed(() => route.params.id as string)

// 状态
const twin = ref<TwinOverview | null>(null)
const history = ref<ChangeLog[]>([])
const loading = ref(false)
const saving = ref(false)

// 编辑状态
const editingDesired = ref(false)
const desiredJson = ref('')

// 计算属性
const device = computed(() => 
  deviceStore.devices.find(d => d.id === deviceId.value)
)

const isSynced = computed(() => twin.value?.is_synced ?? true)

const deltaItems = computed(() => {
  if (!twin.value?.delta) return []
  const delta = twin.value.delta as Record<string, unknown>
  return Object.entries(delta).map(([key, value]) => ({ key, value }))
})

// 加载数据
async function loadData() {
  loading.value = true
  try {
    twin.value = await twinApi.getTwin(deviceId.value)
    desiredJson.value = JSON.stringify(twin.value.desired, null, 2)
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: '加载失败',
      detail: error.message,
    })
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  try {
    history.value = await twinApi.getHistory(deviceId.value, 50)
  } catch (error) {
    console.error('加载历史失败:', error)
  }
}

// 保存 desired
async function saveDesired() {
  if (!twin.value) return
  
  try {
    const desired = JSON.parse(desiredJson.value)
    saving.value = true
    
    twin.value = await twinApi.updateDesired(deviceId.value, desired, 'web')
    desiredJson.value = JSON.stringify(twin.value.desired, null, 2)
    editingDesired.value = false
    
    toast.add({
      severity: 'success',
      summary: '保存成功',
      detail: '期望状态已更新并推送到设备',
    })
  } catch (error: any) {
    if (error instanceof SyntaxError) {
      toast.add({
        severity: 'error',
        summary: 'JSON 格式错误',
        detail: error.message,
      })
    } else {
      toast.add({
        severity: 'error',
        summary: '保存失败',
        detail: error.message,
      })
    }
  } finally {
    saving.value = false
  }
}

// 取消编辑
function cancelEdit() {
  if (twin.value) {
    desiredJson.value = JSON.stringify(twin.value.desired, null, 2)
  }
  editingDesired.value = false
}

// 格式化 JSON
function formatJson() {
  try {
    const parsed = JSON.parse(desiredJson.value)
    desiredJson.value = JSON.stringify(parsed, null, 2)
  } catch {
    // ignore
  }
}

// 返回
function goBack() {
  router.push('/devices')
}

// 监听路由变化
watch(deviceId, () => {
  if (deviceId.value) {
    loadData()
    loadHistory()
  }
}, { immediate: true })

onMounted(() => {
  if (!deviceStore.devices.length) {
    deviceStore.fetchDevices()
  }
})
</script>

<template>
  <div class="twin-page space-y-4">
    <Toast />
    
    <!-- 顶部信息 -->
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
          
          <div class="flex items-center gap-3">
            <Tag 
              v-if="!isSynced" 
              value="待同步" 
              severity="warn" 
              icon="pi pi-sync"
            />
            <Tag 
              v-else 
              value="已同步" 
              severity="success" 
              icon="pi pi-check"
            />
          </div>
        </div>
      </template>
    </Card>

    <!-- 主内容 -->
    <div v-if="loading" class="text-center py-12 text-secondary">
      <i class="pi pi-spinner pi-spin text-2xl"></i>
      <p class="mt-2">加载中...</p>
    </div>

    <TabView v-else>
      <!-- Twin 状态 -->
      <TabPanel header="Twin 状态">
        <div class="grid grid-cols-2 gap-4 mt-4">
          <!-- Desired -->
          <Card>
            <template #title>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <i class="pi pi-bullseye text-primary-400"></i>
                  <span>Desired (期望状态)</span>
                </div>
                <Tag :value="`v${twin?.desired_version || 0}`" />
              </div>
            </template>
            <template #content>
              <div class="space-y-3">
                <textarea 
                  v-if="editingDesired"
                  v-model="desiredJson"
                  class="w-full h-64 bg-surface-800 border border-surface-700 rounded-lg p-3 font-mono text-sm resize-none focus:border-primary-500 focus:outline-none"
                  spellcheck="false"
                ></textarea>
                <pre v-else class="bg-surface-800 rounded-lg p-3 text-sm font-mono overflow-auto max-h-64">{{ desiredJson || '{}' }}</pre>
                
                <div class="flex gap-2">
                  <template v-if="editingDesired">
                    <Button label="保存" icon="pi pi-check" :loading="saving" @click="saveDesired" />
                    <Button label="格式化" icon="pi pi-align-left" outlined @click="formatJson" />
                    <Button label="取消" severity="secondary" outlined @click="cancelEdit" />
                  </template>
                  <template v-else>
                    <Button label="编辑" icon="pi pi-pencil" outlined @click="editingDesired = true" />
                  </template>
                </div>
              </div>
            </template>
          </Card>

          <!-- Reported -->
          <Card>
            <template #title>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <i class="pi pi-check-circle text-success"></i>
                  <span>Reported (已报告)</span>
                </div>
                <Tag :value="`v${twin?.reported_version || 0}`" />
              </div>
            </template>
            <template #content>
              <pre class="bg-surface-800 rounded-lg p-3 text-sm font-mono overflow-auto max-h-64">{{ JSON.stringify(twin?.reported || {}, null, 2) }}</pre>
              <div class="mt-3">
                <Button label="刷新" icon="pi pi-refresh" outlined @click="loadData" />
              </div>
            </template>
          </Card>
        </div>

        <!-- Delta -->
        <Card v-if="!isSynced && deltaItems.length > 0" class="mt-4">
          <template #title>
            <div class="flex items-center gap-2">
              <i class="pi pi-exclamation-triangle text-warning"></i>
              <span>Delta (待同步差异)</span>
            </div>
          </template>
          <template #content>
            <div class="space-y-2">
              <div 
                v-for="item in deltaItems" 
                :key="item.key"
                class="flex items-center justify-between p-3 bg-surface-800 rounded-lg"
              >
                <span class="font-mono text-sm">{{ item.key }}</span>
                <code class="text-warning text-sm">{{ JSON.stringify(item.value) }}</code>
              </div>
            </div>
          </template>
        </Card>
      </TabPanel>

      <!-- 变更历史 -->
      <TabPanel header="变更历史">
        <div class="mt-4">
          <Timeline :value="history" class="w-full">
            <template #content="slotProps">
              <div class="bg-surface-800 rounded-lg p-3 mb-3">
                <div class="flex items-center gap-2 mb-2">
                  <Tag 
                    :value="slotProps.item.change_type" 
                    :severity="slotProps.item.change_type === 'desired' ? 'info' : 'success'"
                    size="small"
                  />
                  <span class="text-secondary text-xs">
                    {{ new Date(slotProps.item.changed_at).toLocaleString('zh-CN') }}
                  </span>
                  <span v-if="slotProps.item.changed_by" class="text-secondary text-xs">
                    by {{ slotProps.item.changed_by }}
                  </span>
                </div>
                <pre class="text-xs font-mono overflow-auto max-h-32">{{ JSON.stringify(slotProps.item.new_value, null, 2) }}</pre>
              </div>
            </template>
          </Timeline>
          
          <div v-if="history.length === 0" class="text-center py-8 text-secondary">
            暂无变更记录
          </div>
        </div>
      </TabPanel>
    </TabView>
  </div>
</template>

<style scoped>
pre {
  white-space: pre-wrap;
  word-break: break-all;
}
</style>