<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { twinApi } from '@/api'
import type { DeviceRegisterResponse } from '@/types'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Chip from 'primevue/chip'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'

const router = useRouter()
const toast = useToast()

// 表单数据
const form = ref({
  device_name: '',
  device_type: '',
  firmware_version: '',
  hardware_version: '',
  mac_address: '',
})

const deviceTypes = [
  { label: '传感器', value: 'sensor' },
  { label: '网关', value: 'gateway' },
  { label: '终端', value: 'terminal' },
  { label: '控制器', value: 'controller' },
]

// 状态
const loading = ref(false)
const registered = ref(false)
const credentials = ref<DeviceRegisterResponse | null>(null)
const copied = ref(false)

// 是否可以提交
const canSubmit = computed(() => {
  return form.value.device_name.trim().length > 0 && !loading.value
})

// 注册设备
async function handleRegister() {
  loading.value = true
  
  try {
    const response = await twinApi.registerDevice({
      device_name: form.value.device_name,
      device_type: form.value.device_type || undefined,
      firmware_version: form.value.firmware_version || undefined,
      hardware_version: form.value.hardware_version || undefined,
      mac_address: form.value.mac_address || undefined,
    })
    
    credentials.value = response
    registered.value = true
    
    toast.add({
      severity: 'success',
      summary: '注册成功',
      detail: `设备 ${response.device_id} 已创建`,
      life: 5000,
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: '注册失败',
      detail: error.response?.data?.message || error.message || '未知错误',
      life: 5000,
    })
  } finally {
    loading.value = false
  }
}

// 复制凭证
async function copyCredentials() {
  if (!credentials.value) return
  
  const text = `device_id: ${credentials.value.device_id}
mqtt_username: ${credentials.value.mqtt_username}
mqtt_password: ${credentials.value.mqtt_password}
mqtt_broker: ${credentials.value.mqtt_broker}:${credentials.value.mqtt_port}`
  
  await navigator.clipboard.writeText(text)
  copied.value = true
  toast.add({ severity: 'info', summary: '已复制', life: 2000 })
  
  setTimeout(() => {
    copied.value = false
  }, 2000)
}

// 下载配置文件
function downloadConfig() {
  if (!credentials.value) return
  
  const config = `# 设备配置文件
device_id=${credentials.value.device_id}
mqtt_broker=${credentials.value.mqtt_broker}
mqtt_port=${credentials.value.mqtt_port}
mqtt_username=${credentials.value.mqtt_username}
mqtt_password=${credentials.value.mqtt_password}
`
  
  const blob = new Blob([config], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `device-${credentials.value.device_id}.conf`
  a.click()
  URL.revokeObjectURL(url)
}

// 继续注册
function resetForm() {
  form.value = {
    device_name: '',
    device_type: '',
    firmware_version: '',
    hardware_version: '',
    mac_address: '',
  }
  registered.value = false
  credentials.value = null
}

// 返回设备列表
function goBack() {
  router.push('/devices')
}
</script>

<template>
  <div class="register-page max-w-2xl mx-auto">
    <Toast />
    
    <Card>
      <template #title>
        <div class="flex items-center gap-2">
          <i class="pi pi-plus-circle text-primary-400"></i>
          <span>注册新设备</span>
        </div>
      </template>
      <template #content>
        <!-- 注册成功 - 显示凭证 -->
        <div v-if="registered && credentials" class="space-y-4">
          <Message severity="success">
            设备注册成功！请保存以下凭证，设备将使用这些信息连接服务器。
          </Message>
          
          <div class="credentials-box bg-surface-800 rounded-lg p-4 space-y-3">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="text-xs text-secondary block mb-1">设备 ID</label>
                <code class="block bg-surface-900 px-3 py-2 rounded font-mono text-sm">
                  {{ credentials.device_id }}
                </code>
              </div>
              <div>
                <label class="text-xs text-secondary block mb-1">MQTT Broker</label>
                <code class="block bg-surface-900 px-3 py-2 rounded font-mono text-sm">
                  {{ credentials.mqtt_broker }}:{{ credentials.mqtt_port }}
                </code>
              </div>
              <div>
                <label class="text-xs text-secondary block mb-1">MQTT 用户名</label>
                <code class="block bg-surface-900 px-3 py-2 rounded font-mono text-sm">
                  {{ credentials.mqtt_username }}
                </code>
              </div>
              <div>
                <label class="text-xs text-secondary block mb-1">MQTT 密码</label>
                <code class="block bg-surface-900 px-3 py-2 rounded font-mono text-sm">
                  {{ credentials.mqtt_password }}
                </code>
              </div>
            </div>
          </div>
          
          <div class="flex gap-3">
            <Button 
              :icon="copied ? 'pi pi-check' : 'pi pi-copy'" 
              :label="copied ? '已复制' : '复制凭证'"
              @click="copyCredentials"
            />
            <Button icon="pi pi-download" label="下载配置" severity="secondary" @click="downloadConfig" />
            <Button label="继续注册" outlined @click="resetForm" />
            <Button label="返回列表" link @click="goBack" />
          </div>
        </div>
        
        <!-- 注册表单 -->
        <form v-else class="space-y-4" @submit.prevent="handleRegister">
          <div>
            <label class="block text-sm text-secondary mb-2">
              设备名称 <span class="text-danger">*</span>
            </label>
            <InputText 
              v-model="form.device_name" 
              placeholder="例如: sensor-living-room-001"
              class="w-full"
            />
          </div>
          
          <div>
            <label class="block text-sm text-secondary mb-2">设备类型</label>
            <Select 
              v-model="form.device_type" 
              :options="deviceTypes" 
              optionLabel="label"
              optionValue="value"
              placeholder="选择设备类型"
              class="w-full"
            />
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-secondary mb-2">固件版本</label>
              <InputText 
                v-model="form.firmware_version" 
                placeholder="例如: 1.0.0"
                class="w-full"
              />
            </div>
            <div>
              <label class="block text-sm text-secondary mb-2">硬件版本</label>
              <InputText 
                v-model="form.hardware_version" 
                placeholder="例如: v2"
                class="w-full"
              />
            </div>
          </div>
          
          <div>
            <label class="block text-sm text-secondary mb-2">MAC 地址</label>
            <InputText 
              v-model="form.mac_address" 
              placeholder="例如: AA:BB:CC:DD:EE:FF"
              class="w-full"
            />
          </div>
          
          <div class="flex gap-3 pt-4">
            <Button 
              type="submit" 
              label="注册设备" 
              icon="pi pi-check" 
              :loading="loading"
              :disabled="!canSubmit"
            />
            <Button label="取消" severity="secondary" outlined @click="goBack" />
          </div>
        </form>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.credentials-box code {
  word-break: break-all;
}
</style>