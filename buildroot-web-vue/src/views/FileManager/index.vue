<template>
  <div class="file-manager">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <select v-model="selectedDeviceId" @change="handleDeviceChange" :disabled="loading">
          <option value="">选择设备</option>
          <option v-for="device in availableDevices" :key="device.id" :value="device.id">
            {{ device.name }} ({{ device.is_online ? '在线' : '离线' }})
          </option>
        </select>
        <button class="new-tab-btn" @click="openInNewTab" :disabled="!selectedDeviceId">
          新标签页
        </button>
      </div>
      <div class="toolbar-right">
        <button @click="refresh" :disabled="loading || !selectedDeviceId">
          {{ loading ? '加载中...' : '刷新' }}
        </button>
        <button @click="showUploadDialog = true" :disabled="!currentPath || loading || !selectedDeviceId">
          上传
        </button>
        <button @click="showCreateDirDialog = true" :disabled="!currentPath || loading || !selectedDeviceId">
          新建目录
        </button>
        <button @click="handleDownload" :disabled="!selectedFile || loading || !selectedDeviceId">
          下载
        </button>
        <button @click="handleDelete" :disabled="!selectedFile || loading || !selectedDeviceId" class="danger">
          删除
        </button>
      </div>
    </div>

    <!-- 路径栏 -->
    <div class="path-bar" v-if="selectedDeviceId">
      <span class="label">路径:</span>
      <div class="breadcrumbs">
        <span class="breadcrumb-item" @click="navigateTo('/')">/</span>
        <template v-for="(segment, index) in pathSegments" :key="index">
          <span class="separator">/</span>
          <span class="breadcrumb-item" @click="navigateTo(getPathByIndex(index))">
            {{ segment }}
          </span>
        </template>
      </div>
    </div>

    <!-- 文件列表 -->
    <div class="file-list" v-if="selectedDeviceId">
      <div class="file-list-header">
        <div class="column name">名称</div>
        <div class="column size">大小</div>
        <div class="column type">类型</div>
      </div>

      <div class="file-list-body">
        <div 
          v-for="file in files" 
          :key="file.path"
          class="file-item"
          :class="{ selected: selectedFile?.path === file.path }"
          @click="selectFile(file)"
          @dblclick="handleDoubleClick(file)"
        >
          <div class="column name">
            <span class="icon">{{ file.is_dir ? '📁' : '📄' }}</span>
            <span class="filename">{{ file.name }}</span>
          </div>
          <div class="column size">{{ formatSize(file.size) }}</div>
          <div class="column type">{{ file.is_dir ? '目录' : '文件' }}</div>
        </div>

        <div v-if="files.length === 0 && !loading" class="empty">
          目录为空
        </div>
      </div>
    </div>

    <div v-if="!selectedDeviceId" class="no-device">
      请先选择一个设备
    </div>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <!-- 上传对话框 -->
    <UploadDialog 
      v-if="showUploadDialog"
      :device-id="selectedDeviceId"
      :current-path="currentPath"
      @close="showUploadDialog = false"
      @uploaded="handleUploaded"
    />

    <!-- 新建目录对话框 -->
    <CreateDirDialog
      v-if="showCreateDirDialog"
      :device-id="selectedDeviceId"
      :current-path="currentPath"
      @close="showCreateDirDialog = false"
      @created="handleDirCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores/device'
import { useTabStore } from '@/stores/tabs'
import UploadDialog from './components/UploadDialog.vue'
import CreateDirDialog from './components/CreateDirDialog.vue'

const route = useRoute()
const router = useRouter()
const deviceStore = useDeviceStore()
const tabStore = useTabStore()

// State
const selectedDeviceId = ref('')
const currentPath = ref('/')
const files = ref<any[]>([])
const selectedFile = ref<any>(null)
const loading = ref(false)
const error = ref('')
const showUploadDialog = ref(false)
const showCreateDirDialog = ref(false)

// Computed
const availableDevices = computed(() => 
  deviceStore.devices.filter(d => d.is_online)
)

const pathSegments = computed(() => {
  if (!currentPath.value || currentPath.value === '/') return []
  return currentPath.value.split('/').filter(Boolean)
})

// Methods
function handleDeviceChange() {
  if (selectedDeviceId.value) {
    router.replace(`/filemanager/${selectedDeviceId.value}`)
    
    const device = deviceStore.devices.find(d => d.id === selectedDeviceId.value)
    if (device) {
      tabStore.openTab('filemanager', selectedDeviceId.value, device.name || selectedDeviceId.value.slice(0, 8))
    }
    
    currentPath.value = '/'
    selectedFile.value = null
    error.value = ''
    fetchFileList()
  }
}

function openInNewTab() {
  if (selectedDeviceId.value) {
    const url = `${window.location.origin}/filemanager/${selectedDeviceId.value}`
    window.open(url, '_blank')
  }
}

async function fetchFileList() {
  if (!selectedDeviceId.value || !currentPath.value) return

  loading.value = true
  error.value = ''

  try {
    const response = await fetch(`/api/devices/${selectedDeviceId.value}/files?path=${encodeURIComponent(currentPath.value)}`)
    
    if (!response.ok) {
      throw new Error(`API请求失败: ${response.status}`)
    }

    const data = await response.json()
    files.value = data.files || []
  } catch (err: any) {
    console.error('获取文件列表失败:', err)
    error.value = `获取文件列表失败: ${err.message}`
    files.value = []
  } finally {
    loading.value = false
  }
}

function refresh() {
  fetchFileList()
}

function selectFile(file: any) {
  selectedFile.value = file
}

function handleDoubleClick(file: any) {
  if (file.is_dir) {
    navigateTo(file.path)
  }
}

function navigateTo(path: string) {
  currentPath.value = path
  selectedFile.value = null
  fetchFileList()
}

function getPathByIndex(index: number): string {
  const segments = pathSegments.value.slice(0, index + 1)
  return '/' + segments.join('/')
}

function formatSize(size: number): string {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function handleUploaded() {
  showUploadDialog.value = false
  refresh()
}

function handleDirCreated() {
  showCreateDirDialog.value = false
  refresh()
}

async function handleDownload() {
  if (!selectedFile.value || selectedFile.value.is_dir) return
  console.log('下载文件:', selectedFile.value.path)
}

async function handleDelete() {
  if (!selectedFile.value) return
  if (!confirm(`确定删除 ${selectedFile.value.name}?`)) return
  console.log('删除文件:', selectedFile.value.path)
}

// Lifecycle
onMounted(async () => {
  await deviceStore.fetchDevices()
  
  const deviceId = route.params.deviceId as string
  if (deviceId) {
    selectedDeviceId.value = deviceId
    const device = deviceStore.devices.find(d => d.id === deviceId)
    if (device) {
      tabStore.openTab('filemanager', deviceId, device.name || deviceId.slice(0, 8))
    }
    fetchFileList()
  }
})

watch(() => route.params.deviceId, (newDeviceId) => {
  if (newDeviceId && typeof newDeviceId === 'string') {
    selectedDeviceId.value = newDeviceId
    currentPath.value = '/'
    selectedFile.value = null
    const device = deviceStore.devices.find(d => d.id === newDeviceId)
    if (device) {
      tabStore.openTab('filemanager', newDeviceId, device.name || newDeviceId.slice(0, 8))
    }
    fetchFileList()
  }
})
</script>

<style scoped>
.file-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e2e;
  color: #cdd6f4;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #181825;
  border-bottom: 1px solid #313244;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 8px;
}

.toolbar select {
  padding: 6px 12px;
  background: #1e1e2e;
  border: 1px solid #45475a;
  border-radius: 4px;
  color: #cdd6f4;
  font-size: 13px;
}

.new-tab-btn {
  padding: 6px 12px;
  background: #89b4fa;
  color: #1e1e2e;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}

.new-tab-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar button {
  padding: 6px 12px;
  background: #313244;
  border: 1px solid #45475a;
  border-radius: 4px;
  color: #cdd6f4;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar button:hover:not(:disabled) {
  background: #45475a;
}

.toolbar button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar button.danger {
  background: #f38ba8;
  color: #1e1e2e;
  border-color: #f38ba8;
}

.path-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #181825;
  border-bottom: 1px solid #313244;
  font-size: 13px;
}

.path-bar .label {
  color: #6c7086;
}

.breadcrumbs {
  display: flex;
  align-items: center;
  gap: 4px;
}

.breadcrumb-item {
  color: #89b4fa;
  cursor: pointer;
}

.breadcrumb-item:hover {
  text-decoration: underline;
}

.separator {
  color: #6c7086;
}

.file-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-list-header {
  display: grid;
  grid-template-columns: 1fr 100px 80px;
  padding: 8px 16px;
  background: #181825;
  border-bottom: 1px solid #313244;
  font-size: 12px;
  color: #6c7086;
}

.file-list-body {
  flex: 1;
  overflow-y: auto;
}

.file-item {
  display: grid;
  grid-template-columns: 1fr 100px 80px;
  padding: 10px 16px;
  border-bottom: 1px solid #313244;
  cursor: pointer;
  transition: background 0.15s;
}

.file-item:hover {
  background: #313244;
}

.file-item.selected {
  background: #45475a;
}

.file-item .column.name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-item .icon {
  font-size: 16px;
}

.file-item .filename {
  font-size: 13px;
}

.empty {
  padding: 40px;
  text-align: center;
  color: #6c7086;
}

.no-device {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6c7086;
  font-size: 14px;
}

.error-message {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 12px 20px;
  background: #f38ba8;
  color: #1e1e2e;
  border-radius: 4px;
  font-size: 13px;
}
</style>