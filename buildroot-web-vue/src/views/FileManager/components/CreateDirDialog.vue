<template>
  <div class="dialog-overlay" @click="close">
    <div class="dialog" @click.stop>
      <div class="dialog-header">
        <h3>新建目录</h3>
        <button class="close-btn" @click="close">×</button>
      </div>

      <div class="dialog-body">
        <div class="form-group">
          <label>设备:</label>
          <div class="device-info">{{ deviceId }}</div>
        </div>

        <div class="form-group">
          <label>父目录:</label>
          <div class="path-info">{{ currentPath }}</div>
        </div>

        <div class="form-group">
          <label for="dirname">目录名称:</label>
          <input
            id="dirname"
            v-model="dirname"
            type="text"
            placeholder="输入目录名称"
            @keyup.enter="create"
            :disabled="creating"
            ref="inputRef"
          >
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>
      </div>

      <div class="dialog-footer">
        <button class="cancel-btn" @click="close" :disabled="creating">取消</button>
        <button class="create-btn" @click="create" :disabled="!dirname || creating">
          {{ creating ? '创建中...' : '创建' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { createDirectory } from '@/api/file-api'

interface Props {
  deviceId: string
  currentPath: string
}

interface Emits {
  (e: 'close'): void
  (e: 'created'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const dirname = ref('')
const creating = ref(false)
const error = ref('')
const inputRef = ref<HTMLInputElement>()

const close = () => {
  if (!creating.value) {
    emit('close')
    dirname.value = ''
    error.value = ''
  }
}

const create = async () => {
  if (!props.deviceId || !dirname.value) return

  creating.value = true
  error.value = ''

  try {
    const path = props.currentPath.endsWith('/')
      ? `${props.currentPath}${dirname.value}`
      : `${props.currentPath}/${dirname.value}`

    await createDirectory(props.deviceId, path)

    creating.value = false
    emit('created')
  } catch (err: any) {
    error.value = err.message || '创建目录失败'
    creating.value = false
  }
}

onMounted(() => {
  // 自动聚焦到输入框
  inputRef.value?.focus()
})
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
  min-width: 400px;
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

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.form-group label {
  font-size: 13px;
  color: #6e6e80;
  min-width: 80px;
}

.device-info,
.path-info {
  padding: 8px 12px;
  background: #1e1e2a;
  border-radius: 4px;
  font-size: 13px;
  color: #f0f0f5;
  word-break: break-all;
}

.form-group input {
  padding: 8px 12px;
  background: #1e1e2a;
  border: 1px solid #3a3a4a;
  border-radius: 4px;
  color: #f0f0f5;
  font-size: 14px;
}

.form-group input:focus {
  outline: none;
  border-color: #6366f1;
}

.form-group input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.1);
  border-left: 3px solid #ef4444;
  color: #ef4444;
  font-size: 13px;
  border-radius: 4px;
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

.create-btn {
  background: #6366f1;
  border: 1px solid #6366f1;
  color: white;
}

.create-btn:hover:not(:disabled) {
  background: #818cf8;
  border-color: #818cf8;
}

.dialog-footer button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
