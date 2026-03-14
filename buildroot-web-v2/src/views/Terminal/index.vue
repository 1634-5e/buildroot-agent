<script setup lang="ts">
/**
 * 终端组件 - xterm.js + WebSocket
 * 用于远程设备 PTY 会话
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { getWebSocketClient, MessageType } from '@/api/websocket'
import { twinApi } from '@/api'

interface Device {
  device_id: string
  name?: string
  is_online: boolean
}

const route = useRoute()
const router = useRouter()

// Refs
const terminalWrapper = ref<HTMLElement>()
const terminalElement = ref<HTMLElement>()
const terminal = ref<Terminal | null>(null)
const fitAddon = ref<FitAddon | null>(null)
const selectedDeviceId = ref<string>('')
const sessionId = ref<number | null>(null)
const connectionStatus = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
const error = ref('')
const devices = ref<Device[]>([])
const wsConnected = ref(false)

// Computed
const onlineDevices = computed(() =>
  devices.value.filter(d => d.is_online)
)
const connected = computed(() => connectionStatus.value === 'connected')
const canConnect = computed(() => {
  const device = devices.value.find(d => d.device_id === selectedDeviceId.value)
  const result = selectedDeviceId.value && device?.is_online && !connected.value
  console.log('[Terminal] canConnect:', result, 'selectedDeviceId:', selectedDeviceId.value, 'device:', device)
  return result
})
const statusText = computed(() => {
  switch (connectionStatus.value) {
    case 'connected': return '已连接'
    case 'connecting': return '连接中...'
    default: return '未连接'
  }
})
const statusSeverity = computed(() => {
  switch (connectionStatus.value) {
    case 'connected': return 'success'
    case 'connecting': return 'warn'
    default: return 'secondary'
  }
})

// WebSocket
let wsClient: ReturnType<typeof getWebSocketClient> | null = null
let messageHandler: ((msg: unknown) => void) | null = null

// 从 Rust API 获取设备列表
const fetchDevices = async () => {
  try {
    const twins = await twinApi.listTwins({ limit: 100 })
    devices.value = twins.map(twin => ({
      device_id: twin.device_id,
      name: twin.tags?.device_name || twin.device_id.slice(0, 12),
      // 设备有 reported 数据且有 system 指标 = 在线（简化判断）
      is_online: !!(twin.reported && Object.keys(twin.reported).length > 0),
    }))
    console.log('[Terminal] 设备列表从 API 获取:', devices.value.length)
  } catch (e) {
    console.error('[Terminal] 获取设备列表失败:', e)
  }
}

// 初始化 WebSocket
const initWebSocket = () => {
  console.log('[Terminal] initWebSocket called')
  const client = getWebSocketClient()
  wsClient = client
  console.log('[Terminal] ws status:', client.getStatus(), 'isConnected:', client.isConnected())

  messageHandler = (msg: unknown) => {
    handleWebSocketMessage(msg)
  }
  client.on('message', messageHandler)

  client.on('connected', () => {
    console.log('[Terminal] WS connected event')
    wsConnected.value = true
  })

  client.on('disconnected', () => {
    wsConnected.value = false
    connectionStatus.value = 'disconnected'
    sessionId.value = null
  })

  // 连接 WebSocket（仅用于 PTY 会话）
  if (!client.isConnected()) {
    console.log('[Terminal] Not connected, calling connect()')
    client.connect()
  } else {
    console.log('[Terminal] Already connected')
    wsConnected.value = true
  }
}

// 初始化终端
const initTerminal = () => {
  if (terminal.value || !terminalElement.value) return

  const term = new Terminal({
    cursorBlink: true,
    cursorStyle: 'block',
    fontSize: 14,
    fontFamily: 'JetBrains Mono, Monaco, Menlo, "Courier New", monospace',
    lineHeight: 1.2,
    theme: {
      background: '#1e1e2e',
      foreground: '#cdd6f4',
      cursor: '#f5e0dc',
      selectionBackground: 'rgba(245, 224, 220, 0.3)',
      black: '#45475a',
      red: '#f38ba8',
      green: '#a6e3a1',
      yellow: '#f9e2af',
      blue: '#89b4fa',
      magenta: '#f5c2e7',
      cyan: '#94e2d5',
      white: '#bac2de',
      brightBlack: '#585b70',
      brightRed: '#f38ba8',
      brightGreen: '#a6e3a1',
      brightYellow: '#f9e2af',
      brightBlue: '#89b4fa',
      brightMagenta: '#f5c2e7',
      brightCyan: '#94e2d5',
      brightWhite: '#a6adc8',
    },
  })

  const addon = new FitAddon()
  term.loadAddon(addon)
  term.loadAddon(new WebLinksAddon())
  term.open(terminalElement.value)

  fitAddon.value = addon
  terminal.value = term

  // 延迟 fit，等待 DOM 渲染
  setTimeout(() => addon.fit(), 100)

  // 用户输入 -> 发送到设备
  term.onData((data) => {
    if (sessionId.value && wsClient) {
      wsClient.send(MessageType.PTY_DATA, {
        session_id: sessionId.value,
        data,
      })
    }
  })

  // 终端大小变化 -> 通知设备
  term.onResize(({ cols, rows }) => {
    if (sessionId.value && wsClient) {
      wsClient.send(MessageType.PTY_RESIZE, {
        session_id: sessionId.value,
        cols,
        rows,
      })
    }
  })

  term.writeln('')
  term.writeln('  Buildroot Agent Terminal')
  term.writeln('  ========================')
  term.writeln('')
  term.writeln('  Select device and click Connect')
  term.writeln('')
}

// 连接设备
const connect = async () => {
  if (!selectedDeviceId.value) return

  const device = devices.value.find(d => d.device_id === selectedDeviceId.value)
  if (!device?.is_online) {
    error.value = '设备离线'
    return
  }

  connectionStatus.value = 'connecting'
  error.value = ''

  initTerminal()

  terminal.value?.writeln(`\x1b[33m连接 ${device.name || selectedDeviceId.value.slice(0, 8)}...\x1b[0m`)

  // 确保 WebSocket 已连接
  if (!wsClient) {
    initWebSocket()
    // 等待连接
    await new Promise(resolve => setTimeout(resolve, 500))
  }

  // 发送 PTY_CREATE 请求
  if (wsClient && terminal.value) {
    const { cols, rows } = terminal.value
    // 生成 session_id (简单递增)
    const newSessionId = Date.now()
    wsClient.send(MessageType.PTY_CREATE, {
      device_id: selectedDeviceId.value,
      session_id: newSessionId,
      cols: cols || 80,
      rows: rows || 24,
    })
    console.log('[Terminal] PTY_CREATE sent, session_id:', newSessionId)
  }
}

// 断开连接
const disconnect = () => {
  if (sessionId.value && wsClient) {
    wsClient.send(MessageType.PTY_CLOSE, {
      session_id: sessionId.value,
    })
  }

  connectionStatus.value = 'disconnected'
  sessionId.value = null
  terminal.value?.writeln('\x1b[33m已断开\x1b[0m')
}

// 清屏
const clearTerminal = () => {
  terminal.value?.clear()
}

// 处理 WebSocket 消息（仅处理 PTY 相关）
const handleWebSocketMessage = (msg: unknown) => {
  const message = msg as { type: number; data: Record<string, unknown> }
  const { type, data } = message
  
  console.log('[Terminal] 收到消息:', type, data)

  // PTY_CREATE 响应
  if (type === MessageType.PTY_CREATE) {
    if (data.session_id) {
      sessionId.value = data.session_id as number
      connectionStatus.value = 'connected'
      terminal.value?.writeln('\x1b[32m连接成功\x1b[0m')
    } else {
      connectionStatus.value = 'disconnected'
      terminal.value?.writeln(`\x1b[31m连接失败: ${data.error || '未知错误'}\x1b[0m`)
      error.value = (data.error as string) || '连接失败'
    }
  }

  // PTY_DATA 输出
  if (type === MessageType.PTY_DATA && data.session_id === sessionId.value) {
    terminal.value?.write(data.data as string)
  }

  // PTY_CLOSE 会话关闭
  if (type === MessageType.PTY_CLOSE && data.session_id === sessionId.value) {
    connectionStatus.value = 'disconnected'
    sessionId.value = null
    terminal.value?.writeln('\x1b[33m会话已关闭\x1b[0m')
  }
}

// 设备选择变化
const onDeviceChange = () => {
  console.log('[Terminal] onDeviceChange, selectedDeviceId:', selectedDeviceId.value)
  if (selectedDeviceId.value) {
    router.replace(`/terminal/${selectedDeviceId.value}`)
  } else {
    router.replace('/terminal')
  }

  if (connected.value) {
    disconnect()
  }
  sessionId.value = null
  error.value = ''
}

// 窗口大小变化时重新 fit
const handleResize = () => {
  if (fitAddon.value) {
    fitAddon.value.fit()
  }
}

// Lifecycle
onMounted(async () => {
  initTerminal()

  // 从 Rust API 获取设备列表
  await fetchDevices()

  // 连接 WebSocket（用于 PTY 会话）
  initWebSocket()

  // 从路由参数获取设备 ID
  const deviceId = route.params.deviceId as string
  if (deviceId) {
    selectedDeviceId.value = deviceId
  }

  window.addEventListener('resize', handleResize)
})

// Watch devices list
watch(devices, (newDevices) => {
  console.log('[Terminal] Devices changed:', newDevices.length, newDevices)
  // 如果只有一个设备，自动选择
  if (newDevices.length === 1 && !selectedDeviceId.value) {
    selectedDeviceId.value = newDevices[0].device_id
    console.log('[Terminal] Auto-selected device:', selectedDeviceId.value)
  }
}, { immediate: true })

onBeforeUnmount(() => {
  if (connected.value) {
    disconnect()
  }

  if (wsClient && messageHandler) {
    wsClient.off('message', messageHandler)
  }

  terminal.value?.dispose()
  window.removeEventListener('resize', handleResize)
})

// 监听路由参数变化
watch(() => route.params.deviceId, (newDeviceId) => {
  if (newDeviceId && typeof newDeviceId === 'string') {
    selectedDeviceId.value = newDeviceId
    if (connected.value) {
      disconnect()
    }
  }
})
</script>

<template>
  <div class="terminal-page">
    <!-- 工具栏 -->
    <div class="terminal-toolbar">
      <div class="toolbar-left">
        <Select
          v-model="selectedDeviceId"
          :options="onlineDevices"
          optionLabel="name"
          optionValue="device_id"
          placeholder="选择设备"
          class="device-select"
          @change="onDeviceChange"
        >
          <template #option="slotProps">
            <div class="flex items-center gap-2">
              <span>{{ slotProps.option.name || slotProps.option.device_id.slice(0, 12) }}</span>
              <Tag v-if="slotProps.option.is_online" value="在线" severity="success" />
            </div>
          </template>
        </Select>

        <Button
          label="连接"
          icon="pi pi-link"
          severity="success"
          :disabled="!canConnect"
          @click="connect"
        />
        <Button
          label="断开"
          icon="pi pi-times"
          severity="danger"
          :disabled="!connected"
          @click="disconnect"
        />
        <Button
          label="清屏"
          icon="pi pi-trash"
          severity="secondary"
          :disabled="!terminal"
          @click="clearTerminal"
        />
      </div>

      <div class="toolbar-right">
        <Tag :value="statusText" :severity="statusSeverity" />
      </div>
    </div>

    <!-- 终端区域 -->
    <div class="terminal-wrapper" ref="terminalWrapper">
      <div ref="terminalElement" class="terminal"></div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="terminal-error">
      <i class="pi pi-exclamation-triangle mr-2"></i>
      {{ error }}
    </div>
  </div>
</template>

<style scoped>
.terminal-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  background: #1e1e2e;
}

.terminal-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #181825;
  border-bottom: 1px solid #313244;
}

.toolbar-left {
  display: flex;
  gap: 8px;
  align-items: center;
}

.device-select {
  width: 200px;
}

.terminal-wrapper {
  flex: 1;
  padding: 8px;
  overflow: hidden;
}

.terminal {
  height: 100%;
}

.terminal-error {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 12px 20px;
  background: #f38ba8;
  color: #1e1e2e;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
}
</style>

<style>
/* xterm.js 全局样式 */
.terminal .xterm-viewport::-webkit-scrollbar {
  width: 8px;
}

.terminal .xterm-viewport::-webkit-scrollbar-track {
  background: #1e1e2e;
}

.terminal .xterm-viewport::-webkit-scrollbar-thumb {
  background: #45475a;
  border-radius: 4px;
}

.terminal .xterm-viewport::-webkit-scrollbar-thumb:hover {
  background: #585b70;
}
</style>