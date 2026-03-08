<template>
  <div class="dialog-overlay" @click="close">
    <div class="dialog" @click.stop>
      <div class="dialog-header">
        <h3>上传文件</h3>
        <button class="close-btn" @click="close">×</button>
      </div>

      <div class="dialog-body">
        <div class="upload-area" :class="{ 'dragover': isDragOver }"
             @dragover.prevent="isDragOver = true"
             @dragleave.prevent="isDragOver = false"
             @drop.prevent="handleDrop">

          <div v-if="!selectedFile" class="upload-placeholder">
            <div class="icon">📁</div>
            <p>拖拽文件到此处或点击选择</p>
            <input type="file" ref="fileInput" @change="handleFileSelect" style="display: none">
            <button @click="openFileSelect">选择文件</button>
          </div>

          <div v-else class="file-info">
            <div class="icon">📄</div>
            <div class="info">
              <div class="name">{{ selectedFile.name }}</div>
              <div class="size">{{ formatSize(selectedFile.size) }}</div>
            </div>
            <button class="remove-btn" @click="clearFile">×</button>
          </div>
        </div>

        <div class="path-info">
          <span class="label">设备:</span>
          <span class="device">{{ deviceId }}</span>
        </div>

        <div class="path-info">
          <span class="label">上传到:</span>
          <span class="path">{{ currentPath }}</span>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="cancel-btn" @click="close" :disabled="uploading">取消</button>
        <button class="upload-btn" @click="upload" :disabled="!selectedFile || uploading">
          {{ uploading ? '上传中...' : '上传' }}
        </button>
      </div>

      <div v-if="error" class="error-message">
        {{ error }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  requestFileUpload,
  sendFileData,
  onWebSocketMessage,
  MessageType,
} from '@/api/websocket'
import { uploadFile } from '@/api/file-api'

interface Props {
  deviceId: string
  currentPath: string
}

interface Emits {
  (e: 'close'): void
  (e: 'uploaded'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const fileInput = ref<HTMLInputElement>()
const selectedFile = ref<File | null>(null)
const isDragOver = ref(false)
const uploading = ref(false)
const error = ref('')

// 文件选择
const openFileSelect = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0]
  }
}

const handleDrop = (event: DragEvent) => {
  isDragOver.value = false
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    selectedFile.value = event.dataTransfer.files[0]
  }
}

const clearFile = () => {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
  error.value = ''
}

// 上传文件
const upload = async () => {
  if (!selectedFile.value || !props.deviceId) return

  uploading.value = true
  error.value = ''

  const file = selectedFile.value

  // 小文件（<10MB）使用 HTTP 上传
  if (file.size < 10 * 1024 * 1024) {
    await uploadViaHttp(file)
  } else {
    await uploadViaWebSocket(file)
  }
}

// HTTP 上传（小文件）
const uploadViaHttp = async (file: File) => {
  try {
    await uploadFile(props.deviceId, file, props.currentPath)

    uploading.value = false
    emit('uploaded')
  } catch (err: any) {
    error.value = err.message || '上传失败'
    uploading.value = false
  }
}

// WebSocket 上传（大文件）
const uploadViaWebSocket = async (file: File) => {
  const CHUNK_SIZE = 1024 * 512 // 512KB chunks

  try {
    // 1. 发送上传请求
    const success = requestFileUpload(props.deviceId, file.name, file.size)

    if (!success) {
      throw new Error('发送上传请求失败')
    }

    // 2. 分片读取和上传
    const reader = new FileReader()
    let chunkIndex = 0
    let totalChunks = Math.ceil(file.size / CHUNK_SIZE)

    const readNextChunk = (offset: number) => {
      const chunk = file.slice(offset, offset + CHUNK_SIZE)
      reader.readAsDataURL(chunk)
    }

    reader.onload = (e) => {
      const result = e.target?.result as string
      const base64Data = result.split(',')[1] || result

      // 发送分片数据
      const success = sendFileData(props.deviceId, chunkIndex, base64Data)

      if (success) {
        chunkIndex++
        const offset = chunkIndex * CHUNK_SIZE

        // 更新进度（TODO: 显示进度条）
        const progress = Math.round((chunkIndex / totalChunks) * 100)
        console.log(`Upload progress: ${progress}%`)

        if (offset < file.size) {
          // 继续下一分片
          readNextChunk(offset)
        } else {
          // 上传完成
          uploading.value = false
          emit('uploaded')
        }
      } else {
        throw new Error('发送分片数据失败')
      }
    }

    reader.onerror = () => {
      throw new Error('文件读取失败')
    }

    // 开始读取第一个分片
    readNextChunk(0)

  } catch (err: any) {
    error.value = err.message || '上传失败'
    uploading.value = false
  }
}

const close = () => {
  if (!uploading.value) {
    emit('close')
  }
}

const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${units[i]}`
}

// WebSocket 消息处理器（用于上传进度/结果）
const handleWebSocketMessage = (data: any) => {
  // TODO: 处理上传进度和结果
  console.log('Upload message:', data)
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: #242432;
  border: 1px solid #3a3a4a;
  border-radius: 8px;
  min-width: 500px;
  max-width: 90vw;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #3a3a4a;
}

.dialog-header h3 {
  margin: 0;
  font-size: 16px;
  color: #f0f0f5;
}

.close-btn {
  background: none;
  border: none;
  color: #6e6e80;
  font-size: 24px;
  cursor: pointer;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #f0f0f5;
}

.dialog-body {
  padding: 20px;
}

.upload-area {
  border: 2px dashed #3a3a4a;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  transition: all 0.2s;
  cursor: pointer;
}

.upload-area:hover,
.upload-area.dragover {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.05);
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-placeholder .icon {
  font-size: 48px;
}

.upload-placeholder p {
  margin: 0;
  color: #6e6e80;
  font-size: 14px;
}

.upload-placeholder button {
  padding: 8px 20px;
  background: #6366f1;
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.upload-placeholder button:hover {
  background: #818cf8;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #1e1e2a;
  border-radius: 4px;
}

.file-info .icon {
  font-size: 32px;
}

.file-info .info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-info .name {
  font-size: 14px;
  color: #f0f0f5;
  word-break: break-all;
}

.file-info .size {
  font-size: 12px;
  color: #6e6e80;
}

.remove-btn {
  background: none;
  border: none;
  color: #6e6e80;
  font-size: 20px;
  cursor: pointer;
  transition: color 0.2s;
}

.remove-btn:hover {
  color: #ef4444;
}

.path-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
}

.path-info .label {
  color: #6e6e80;
  min-width: 60px;
}

.path-info .device,
.path-info .path {
  color: #f0f0f5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid #3a3a4a;
}

.dialog-footer button {
  padding: 8px 20px;
  font-size: 14px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn {
  background: transparent;
  border: 1px solid #3a3a4a;
  color: #f0f0f5;
}

.cancel-btn:hover:not(:disabled) {
  background: #2a2a3a;
}

.upload-btn {
  background: #6366f1;
  border: 1px solid #6366f1;
  color: white;
}

.upload-btn:hover:not(:disabled) {
  background: #818cf8;
  border-color: #818cf8;
}

.dialog-footer button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.1);
  border-left: 3px solid #ef4444;
  color: #ef4444;
  font-size: 13px;
  margin-top: 16px;
  border-radius: 4px;
}
</style>
