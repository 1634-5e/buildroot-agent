<template>
  <div class="terminal-container">
    <!-- 工具栏 -->
    <div class="terminal-toolbar">
      <div class="toolbar-left">
        <select v-model="selectedDeviceId" class="device-select" @change="onDeviceChange">
          <option value="">选择设备</option>
          <option 
            v-for="device in devices" 
            :key="device.id" 
            :value="device.id"
          >
            {{ device.name || device.id.slice(0, 8) }} 
            {{ device.is_online ? '(在线)' : '(离线)' }}
          </option>
        </select>
        <button class="toolbar-btn new-tab" @click="openInNewTab" :disabled="!selectedDeviceId">
          新标签页
        </button>
      </div>
      
      <div class="toolbar-center">
        <div class="status-indicator" :class="connectionStatus">
          <span class="status-dot"></span>
          <span class="status-text">{{ statusText }}</span>
        </div>
      </div>
      
      <div class="toolbar-right">
        <button 
          class="toolbar-btn connect" 
          @click="connect"
          :disabled="!canConnect"
        >
          连接
        </button>
        <button 
          class="toolbar-btn disconnect" 
          @click="disconnect"
          :disabled="!connected"
        >
          断开
        </button>
        <button 
          class="toolbar-btn" 
          @click="clearTerminal"
          :disabled="!terminal"
        >
          清屏
        </button>
      </div>
    </div>
    
    <!-- 终端区域 -->
    <div class="terminal-wrapper" ref="terminalWrapper">
      <div ref="terminalElement" class="terminal"></div>
    </div>
    
    <!-- 错误提示 -->
    <div v-if="error" class="terminal-error">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { useDeviceStore } from '@/stores/device'
import { useTabStore } from '@/stores/tabs'
import { getWebSocketClient, MessageType } from '@/api/websocket'

const route = useRoute()
const router = useRouter()
const deviceStore = useDeviceStore()
const tabStore = useTabStore()

// Refs
const terminalWrapper = ref<HTMLElement>()
const terminalElement = ref<HTMLElement>()
const terminal = ref<Terminal | null>(null)
const selectedDeviceId = ref('')
const sessionId = ref<number | null>(null)
const connectionStatus = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
const error = ref('')
const connecting = ref(false)

// Computed
const devices = computed(() => deviceStore.devices)
const connected = computed(() => connectionStatus.value === 'connected')
const canConnect = computed(() => {
  const device = devices.value.find(d => d.id === selectedDeviceId.value)
  return selectedDeviceId.value && device?.is_online && !connected.value && !connecting.value
})
const statusText = computed(() => {
  switch (connectionStatus.value) {
    case 'connected': return '已连接'
    case 'connecting': return '连接中...'
    default: return '未连接'
  }
})

// WebSocket client
let wsClient: ReturnType<typeof getWebSocketClient> | null = null
let messageHandler: ((msg: any) => void) | null = null

// Methods
const initTerminal = () => {
  if (terminal.value || !terminalElement.value) return
  
  const term = new Terminal({
    cursorBlink: true,
    cursorStyle: 'block',
    fontSize: 14,
    fontFamily: 'JetBrains Mono, Monaco, Menlo, monospace',
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
    }
  })
  
  const addon = new FitAddon()
  term.loadAddon(addon)
  term.open(terminalElement.value)
  
  setTimeout(() => addon.fit(), 100)
  
  terminal.value = term
  
  term.onData((data) => {
    if (sessionId.value && wsClient) {
      wsClient.send(MessageType.PTY_DATA, {
        session_id: sessionId.value,
        data: data
      })
    }
  })
  
  term.onResize(({ cols, rows }) => {
    if (sessionId.value && wsClient) {
      wsClient.send(MessageType.PTY_RESIZE, {
        session_id: sessionId.value,
        cols,
        rows
      })
    }
  })
  
  term.writeln('\x1b[36mBuildroot Agent 终端\x1b[0m')
  term.writeln('')
}

const connect = async () => {
  if (!selectedDeviceId.value) return
  
  const device = devices.value.find(d => d.id === selectedDeviceId.value)
  if (!device?.is_online) {
    error.value = '设备离线'
    return
  }
  
  connecting.value = true
  connectionStatus.value = 'connecting'
  error.value = ''
  
  initTerminal()
  
  terminal.value?.writeln(`\x1b[33m连接 ${device.name || selectedDeviceId.value}...\x1b[0m`)
  
  if (!wsClient) {
    wsClient = getWebSocketClient()
    
    messageHandler = (msg: any) => {
      handleWebSocketMessage(msg)
    }
    wsClient.on('message', messageHandler)
    
    wsClient.on('disconnected', () => {
      connectionStatus.value = 'disconnected'
      sessionId.value = null
    })
    
    wsClient.connect()
  }
  
  setTimeout(() => {
    if (wsClient && terminal.value) {
      const { cols, rows } = terminal.value
      wsClient.send(MessageType.PTY_CREATE, {
        device_id: selectedDeviceId.value,
        cols: cols || 80,
        rows: rows || 24
      })
    }
  }, 500)
}

const disconnect = () => {
  if (sessionId.value && wsClient) {
    wsClient.send(MessageType.PTY_CLOSE, {
      session_id: sessionId.value
    })
  }
  
  connectionStatus.value = 'disconnected'
  sessionId.value = null
  terminal.value?.writeln('\x1b[33m已断开\x1b[0m')
}

const clearTerminal = () => {
  terminal.value?.clear()
}

const onDeviceChange = () => {
  if (selectedDeviceId.value) {
    router.replace(`/terminal/${selectedDeviceId.value}`)
    
    const device = devices.value.find(d => d.id === selectedDeviceId.value)
    if (device) {
      tabStore.openTab('terminal', selectedDeviceId.value, device.name || selectedDeviceId.value.slice(0, 8))
    }
  } else {
    router.replace('/terminal')
  }
  
  if (connected.value) {
    disconnect()
  }
  sessionId.value = null
  error.value = ''
}

const openInNewTab = () => {
  if (selectedDeviceId.value) {
    const url = `${window.location.origin}/terminal/${selectedDeviceId.value}`
    window.open(url, '_blank')
  }
}

const handleWebSocketMessage = (msg: any) => {
  const { type, data } = msg
  
  if (type === MessageType.PTY_CREATE) {
    if (data.session_id) {
      sessionId.value = data.session_id
      connecting.value = false
      connectionStatus.value = 'connected'
      terminal.value?.writeln('\x1b[32m连接成功\x1b[0m')
    } else {
      connecting.value = false
      connectionStatus.value = 'disconnected'
      terminal.value?.writeln(`\x1b[31m连接失败: ${data.error || '未知错误'}\x1b[0m`)
      error.value = data.error || '连接失败'
    }
  }
  
  if (type === MessageType.PTY_DATA && data.session_id === sessionId.value) {
    terminal.value?.write(data.data)
  }
  
  if (type === MessageType.PTY_CLOSE && data.session_id === sessionId.value) {
    connectionStatus.value = 'disconnected'
    sessionId.value = null
    terminal.value?.writeln('\x1b[33m会话已关闭\x1b[0m')
  }
}

// Lifecycle
onMounted(async () => {
  await deviceStore.fetchDevices()
  
  initTerminal()
  
  const deviceId = route.params.deviceId as string
  if (deviceId) {
    selectedDeviceId.value = deviceId
    const device = devices.value.find(d => d.id === deviceId)
    if (device) {
      tabStore.openTab('terminal', deviceId, device.name || deviceId.slice(0, 8))
    }
  }
})

onBeforeUnmount(() => {
  if (connected.value) {
    disconnect()
  }
  
  if (wsClient && messageHandler) {
    wsClient.off('message', messageHandler)
  }
  
  terminal.value?.dispose()
})

watch(() => route.params.deviceId, (newDeviceId) => {
  if (newDeviceId && typeof newDeviceId === 'string') {
    selectedDeviceId.value = newDeviceId
    if (connected.value) {
      disconnect()
    }
    const device = devices.value.find(d => d.id === newDeviceId)
    if (device) {
      tabStore.openTab('terminal', newDeviceId, device.name || newDeviceId.slice(0, 8))
    }
  }
})
</script>

<style scoped>
.terminal-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e2e;
}

.terminal-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #181825;
  border-bottom: 1px solid #313244;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 8px;
}

.toolbar-center {
  display: flex;
  align-items: center;
}

.device-select {
  padding: 6px 12px;
  background: #1e1e2e;
  border: 1px solid #45475a;
  border-radius: 4px;
  color: #cdd6f4;
  font-size: 13px;
}

.device-select:focus {
  outline: none;
  border-color: #89b4fa;
}

.toolbar-btn {
  padding: 6px 12px;
  background: #313244;
  border: 1px solid #45475a;
  border-radius: 4px;
  color: #cdd6f4;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover:not(:disabled) {
  background: #45475a;
}

.toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar-btn.connect {
  background: #a6e3a1;
  color: #1e1e2e;
  border-color: #a6e3a1;
}

.toolbar-btn.disconnect {
  background: #f38ba8;
  color: #1e1e2e;
  border-color: #f38ba8;
}

.toolbar-btn.new-tab {
  background: #89b4fa;
  color: #1e1e2e;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: #1e1e2e;
  border-radius: 12px;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f38ba8;
}

.status-indicator.connected .status-dot {
  background: #a6e3a1;
}

.status-indicator.connecting .status-dot {
  background: #f9e2af;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  color: #6c7086;
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
  border-radius: 4px;
  font-size: 13px;
}
</style>