// Terminal Component - Debug Version
// 添加更详细的日志和错误处理

<template>
  <div class="terminal">
    <header class="terminal-header">
      <h2>终端控制台（调试版）</h2>
      <div class="terminal-status">
        <span class="status-dot" :class="statusClass"></span>
        <span class="status-text">{{ statusText }}</span>
      </div>
      <div class="terminal-actions">
        <button @click="connect" :disabled="isConnected || isConnecting">
          {{ isConnecting ? '连接中...' : '连接' }}
        </button>
        <button @click="disconnect" :disabled="!isConnected">
          断开
        </button>
        <button @click="clearTerminal" :disabled="!isConnected">
          清屏
        </button>
      </div>
    </header>

    <div class="terminal-debug" v-if="debugInfo">
      <h3>调试信息</h3>
      <div><strong>WebSocket 状态:</strong> {{ wsStatus }}</div>
      <div><strong>Session ID:</strong> {{ sessionId }}</div>
      <div><strong>设备 ID:</strong> {{ selectedDeviceId }}</div>
      <div><strong>终端尺寸:</strong> {{ terminalSize.cols }}x{{ terminalSize.rows }}</div>
      <h4>消息日志</h4>
      <div class="message-log">
        <div v-for="(msg, index) in messageLog" :key="index" class="log-entry">
          [{{ msg.time }}] {{ msg.type }}: {{ msg.data }}
        </div>
      </div>
    </div>

    <div class="terminal-container" ref="terminalContainer">
      <div id="terminal" ref="terminalRef"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { SearchAddon } from '@xterm/addon-search'
import { WebLinksAddon } from '@xterm/addon-web-links'
import {
  sendWebSocketMessage,
  onWebSocketConnected,
  onWebSocketDisconnected,
  onWebSocketMessage,
  MessageType,
  connectWebSocket,
  disconnectWebSocket,
  isWebSocketConnected,
} from '@/api/websocket'

type TerminalStatus = 'disconnected' | 'connecting' | 'connected'

const terminalRef = ref<HTMLDivElement>()
const terminalContainer = ref<HTMLDivElement>()
const terminalInstance = ref<Terminal | null>(null)
const fitAddon = ref<FitAddon | null>(null)
const status = ref<TerminalStatus>('disconnected')
const sessionId = ref<number | null>(null)
const selectedDeviceId = ref<string | null>(null)
const resizeHandler = ref<(() => void) | null>(null)

// 调试信息
const debugInfo = ref(true)
const wsStatus = ref('disconnected')
const terminalSize = ref({ cols: 80, rows: 24 })
const messageLog = ref<Array<{ time: string; type: string; data: string }>>([])

const isConnected = computed(() => status.value === 'connected')
const isConnecting = computed(() => status.value === 'connecting')

const statusClass = computed(() => ({
  'connected': status.value === 'connected',
  'connecting': status.value === 'connecting'
}))

const statusText = computed(() => {
  switch (status.value) {
    case 'connected':
      return `已连接 (${selectedDeviceId.value || '未选择设备'})`
    case 'connecting':
      return '连接中...'
    default:
      return '未连接'
  }
})

// 添加日志
const addLog = (type: string, data: any) => {
  const time = new Date().toLocaleTimeString()
  messageLog.value.push({ time, type, data: JSON.stringify(data) })
  // 只保留最近 20 条
  if (messageLog.value.length > 20) {
    messageLog.value.shift()
  }
  console.log(`[${time}] ${type}:`, data)
}

const initTerminal = () => {
  addLog('INIT', 'Initializing terminal...')

  if (terminalInstance.value || !terminalRef.value) {
    addLog('ERROR', 'Terminal already initialized or ref missing')
    return
  }

  const term = new Terminal({
    cursorBlink: true,
    cursorStyle: 'bar',
    fontSize: 14,
    fontFamily: '"JetBrains Mono", "Cascadia Code", "Menlo", "Consolas", "Courier New", monospace',
    theme: {
      background: '#0d0d12',
      foreground: '#f0f0f5',
      cursor: '#6366f1',
      selectionBackground: 'rgba(99, 102, 241, 0.3)',
      black: '#16161e',
      red: '#ef4444',
      green: '#10b981',
      yellow: '#f59e0b',
      blue: '#6366f1',
      magenta: '#8b5cf6',
      cyan: '#06b6d4',
      white: '#f0f0f5',
      brightBlack: '#6e6e80',
      brightRed: '#fca5a5',
      brightGreen: '#6ee7b7',
      brightYellow: '#fcd34d',
      brightBlue: '#a5b4fc',
      brightMagenta: '#c4b5fd',
      brightCyan: '#67e8f9',
      brightWhite: '#ffffff'
    },
    allowProposedApi: true,
    convertEol: true
  })

  const fit = new FitAddon()
  const search = new SearchAddon()
  const webLinks = new WebLinksAddon()

  term.loadAddon(fit)
  term.loadAddon(search)
  term.loadAddon(webLinks)

  term.open(terminalRef.value)
  fit.fit()

  // 获取终端尺寸
  const dims = fit.proposeDimensions()
  terminalSize.value = {
    cols: dims?.cols || 80,
    rows: dims?.rows || 24
  }
  addLog('TERM_SIZE', terminalSize.value)

  term.onData((data: string) => {
    addLog('KEY_INPUT', { char: data, length: data.length })
    if (!sessionId.value) {
      addLog('WARN', 'No active session, ignoring input')
      return
    }
    const base64Data = btoa(data)
    sendWebSocketMessage(MessageType.PTY_DATA, {
      session_id: sessionId.value,
      data: base64Data
    })
  })

  term.onResize((size: { rows: number; cols: number }) => {
    terminalSize.value = { cols: size.cols, rows: size.rows }
    addLog('RESIZE', terminalSize.value)
    if (!sessionId.value) return
    sendWebSocketMessage(MessageType.PTY_RESIZE, {
      session_id: sessionId.value,
      rows: size.rows,
      cols: size.cols
    })
  })

  resizeHandler.value = () => {
    fit.fit()
    const dims = fit.proposeDimensions()
    terminalSize.value = {
      cols: dims?.cols || 80,
      rows: dims?.rows || 24
    }
  }
  window.addEventListener('resize', resizeHandler.value)

  terminalInstance.value = term
  fitAddon.value = fit

  term.writeln('\x1b[1;34mWelcome to Buildroot Agent Terminal (Debug)\x1b[0m')
  term.writeln('Click "连接" to connect to a device.')
  addLog('INIT', 'Terminal initialized')
}

const connect = () => {
  addLog('CONNECT', 'Connecting...')
  selectedDeviceId.value = 'device-001' // 暂时使用固定设备 ID

  try {
    if (!terminalInstance.value) {
      initTerminal()
    }

    if (!terminalInstance.value) {
      addLog('ERROR', 'Failed to initialize terminal')
      console.error('Failed to initialize terminal')
      return
    }

    if (sessionId.value) {
      addLog('INFO', 'Closing existing session')
      disconnect()
    }

    // 如果 WebSocket 未连接，先连接
    if (!isWebSocketConnected()) {
      addLog('WS_CONNECT', 'Connecting WebSocket...')
      connectWebSocket()
    }

    const newSessionId = Math.floor(Math.random() * 1000000000)
    addLog('NEW_SESSION', { sessionId: newSessionId })

    terminalInstance.value.reset()
    terminalInstance.value.writeln('\x1b[1;32mConnecting...\x1b[0m')

    sessionId.value = newSessionId
    status.value = 'connecting'

    const dims = fitAddon.value?.proposeDimensions()
    const rows = dims?.rows || 24
    const cols = dims?.cols || 80

    const ptyCreateData = {
      session_id: newSessionId,
      rows: rows,
      cols: cols
    }
    addLog('SEND_PTY_CREATE', ptyCreateData)

    const sent = sendWebSocketMessage(MessageType.PTY_CREATE, ptyCreateData)
    addLog('SEND_RESULT', { sent, type: 'PTY_CREATE' })

    if (!sent) {
      throw new Error('Failed to send PTY_CREATE message')
    }

    // 8秒超时
    setTimeout(() => {
      if (status.value === 'connecting') {
        addLog('ERROR', 'Connection timeout')
        terminalInstance.value?.writeln('\x1b[1;31mConnection timeout.\x1b[0m')
        status.value = 'disconnected'
        sessionId.value = null
      }
    }, 8000)

  } catch (error) {
    addLog('ERROR', error)
    console.error('Error connecting terminal:', error)
    terminalInstance.value?.writeln(`\r\n\x1b[1;31mConnection Error: ${error}\x1b[0m`)
    status.value = 'disconnected'
    sessionId.value = null
  }
}

const disconnect = () => {
  addLog('DISCONNECT', 'Disconnecting...')
  if (sessionId.value) {
    const closeData = {
      session_id: sessionId.value,
      reason: 'user_closed'
    }
    addLog('SEND_PTY_CLOSE', closeData)
    sendWebSocketMessage(MessageType.PTY_CLOSE, closeData)
  }
  sessionId.value = null
  status.value = 'disconnected'
  terminalInstance.value?.writeln('\r\n\x1b[33mTerminal session closed.\x1b[0m')
}

const clearTerminal = () => {
  addLog('CLEAR', 'Clearing terminal')
  terminalInstance.value?.clear()
}

// WebSocket 消息处理器
const handleWebSocketMessage = (data: any) => {
  addLog('RECV_PTY_DATA', { sessionId: data.session_id, hasData: !!data.data })

  if (!terminalInstance.value) {
    addLog('WARN', 'No terminal instance')
    return
  }

  // 检查 session_id 是否匹配
  if (data.session_id !== sessionId.value) {
    addLog('WARN', `Session ID mismatch: expected ${sessionId.value}, got ${data.session_id}`)
    return
  }

  if (data.data) {
    try {
      const text = atob(data.data)
      terminalInstance.value.write(text)
    } catch (e) {
      addLog('ERROR', `Failed to decode PTY data: ${e}`)
      console.error('Error decoding terminal data:', e)
    }
  }
}

const handleWebSocketConnected = () => {
  addLog('WS_CONNECTED', 'WebSocket connected!')
  wsStatus.value = 'connected'

  if (status.value === 'connecting' && sessionId.value) {
    addLog('INFO', 'Retrying PTY_CREATE after connection')
    const dims = fitAddon.value?.proposeDimensions()
    const rows = dims?.rows || 24
    const cols = dims?.cols || 80

    const ptyCreateData = {
      session_id: sessionId.value,
      rows: rows,
      cols: cols
    }
    addLog('RETRY_PTY_CREATE', ptyCreateData)
    sendWebSocketMessage(MessageType.PTY_CREATE, ptyCreateData)
  }
}

const handleWebSocketDisconnected = (data: any) => {
  addLog('WS_DISCONNECTED', { reason: data.reason })
  wsStatus.value = 'disconnected'
  status.value = 'disconnected'
  sessionId.value = null
  terminalInstance.value?.write(`\r\n\x1b[1;31mWebSocket 断开连接: ${data.reason || 'Unknown reason'}\x1b[0m\r\n`)
}

onMounted(() => {
  addLog('MOUNT', 'Terminal component mounted')
  initTerminal()

  // 注册 WebSocket 事件处理器
  onWebSocketMessage(MessageType.PTY_DATA, handleWebSocketMessage)
  onWebSocketConnected(handleWebSocketConnected)
  onWebSocketDisconnected(handleWebSocketDisconnected)

  // 自动连接 WebSocket
  addLog('AUTO_CONNECT', 'Auto-connecting WebSocket...')
  connectWebSocket()
})

onBeforeUnmount(() => {
  addLog('UNMOUNT', 'Terminal component unmounting')

  if (resizeHandler.value) {
    window.removeEventListener('resize', resizeHandler.value)
  }

  if (sessionId.value) {
    sendWebSocketMessage(MessageType.PTY_CLOSE, {
      session_id: sessionId.value,
      reason: 'component_unmounted'
    })
  }

  disconnect()
  disconnectWebSocket()

  terminalInstance.value?.dispose()
  terminalInstance.value = null

  addLog('UNMOUNT', 'Cleanup complete')
})
</script>

<style scoped>
.terminal {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0d0d12;
}

.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #1a1a24;
  border-bottom: 1px solid #2a2a3a;
}

.terminal-header h2 {
  margin: 0;
  font-size: 16px;
  color: #f0f0f5;
}

.terminal-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6e6e80;
}

.status-dot.connected {
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}

.status-dot.connecting {
  background: #f59e0b;
  box-shadow: 0 0 6px #f59e0b;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.status-text {
  font-size: 14px;
  color: #6e6e80;
}

.terminal-actions {
  display: flex;
  gap: 8px;
}

.terminal-actions button {
  padding: 6px 16px;
  font-size: 13px;
  color: #f0f0f5;
  background: #2a2a3a;
  border: 1px solid #3a3a4a;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.terminal-actions button:hover:not(:disabled) {
  background: #3a3a4a;
  border-color: #6366f1;
}

.terminal-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.terminal-debug {
  background: #1a1a24;
  border-bottom: 1px solid #2a2a3a;
  padding: 12px 20px;
  font-size: 12px;
  color: #f0f0f5;
}

.terminal-debug h3,
.terminal-debug h4 {
  margin: 8px 0 4px 0;
  color: #6366f1;
}

.terminal-debug h4 {
  margin-top: 12px;
}

.terminal-debug > div {
  margin: 4px 0;
}

.message-log {
  max-height: 200px;
  overflow-y: auto;
  background: #0d0d12;
  padding: 8px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.log-entry {
  margin: 2px 0;
  color: #6e6e80;
}

.log-entry:has-text([WARN]) {
  color: #f59e0b;
}

.log-entry:has-text([ERROR]) {
  color: #ef4444;
}

.terminal-container {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

#terminal {
  height: 100%;
}
</style>
