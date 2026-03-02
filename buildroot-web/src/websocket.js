// ============================================
// WebSocket Communication Module
// ============================================

import { showToast, safeGetElement, loadSettings } from './utils.js'
import { MSG_TYPES } from './config.js'

export let ws = null
export let isConnected = false
export let isReconnecting = false
export let reconnectAttempts = 0
export let maxReconnectAttempts = 10

let reconnectTimeout = null
const initialReconnectDelay = 1000
const maxReconnectDelay = 30000
let messageQueue = []
let consoleId = null

// External references (will be set by main.js)
let currentDevice = null
let devices = []
let paginationState = {}
let ptySessionId = null

export function setWebSocketContext(context) {
    currentDevice = context.currentDevice
    devices = context.devices
    paginationState = context.paginationState
    ptySessionId = context.ptySessionId
}

export function connectWebSocket() {
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
        reconnectTimeout = null
    }

    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
        ws.close()
        ws = null
    }

    const wsUrl = getWsUrl()

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
        isConnected = true
        isReconnecting = false
        reconnectAttempts = 0
        updateConnectionStatus(true)
        showToast('已连接到服务器', 'success')

        if (!consoleId) {
            consoleId = 'console_' + Math.random().toString(36).substr(2, 8)
        }

        processMessageQueue()

        // Query device list
        sendMessage(MSG_TYPES.DEVICE_LIST, {
            action: "get_list",
            page: 0,
            page_size: 20,
            search_keyword: '',
            sort_by: "device_id",
            sort_order: "asc"
        })
    }

    ws.onclose = () => {
        isConnected = false
        updateConnectionStatus(false)

        if (ptySessionId) {
            ptySessionId = null
            // appendTerminalOutput will be called by importing module
        }

        if (!isReconnecting && reconnectAttempts < maxReconnectAttempts) {
            isReconnecting = true
            reconnectAttempts++

            const delay = Math.min(
                initialReconnectDelay * Math.pow(2, reconnectAttempts - 1),
                maxReconnectDelay
            )


            reconnectTimeout = setTimeout(() => {
                if (isReconnecting) {
                    connectWebSocket()
                }
            }, delay)
        } else if (reconnectAttempts >= maxReconnectAttempts) {
            showToast('已达到最大重连次数，请手动重试', 'error')
        }
    }

    ws.onerror = (err) => {
        console.error('WebSocket error:', err)
        if (reconnectAttempts === 0) {
            showToast('连接错误，尝试重新连接...', 'warning')
        }
    }

    window.addEventListener('beforeunload', (event) => {
        if (ptySessionId && isConnected && currentDevice) {
            const msg = JSON.stringify({ session_id: ptySessionId })
            const blob = new Blob([msg], { type: 'application/json' })
            navigator.sendBeacon(
                `?device_id=${currentDevice}&msg_type=0x13`,
                blob
            )
        }
    })

    ws.onmessage = async (event) => {
        try {
            const buffer = await event.data.arrayBuffer()
            const bytes = new Uint8Array(buffer)
            if (bytes.length === 0) {
                console.warn('Received empty message')
                return
            }
            const msgType = bytes[0]
            const dataStr = new TextDecoder().decode(bytes.slice(3))
            let data
            try {
                data = dataStr ? JSON.parse(dataStr) : {}
            } catch (parseErr) {
                console.error('Error parsing message data:', parseErr, 'Data:', dataStr)
                return
            }
            
            // handleMessage will be called by importing module
            if (window.handleAppMessage) {
                window.handleAppMessage(msgType, data)
            }
        } catch (err) {
            console.error('Error handling message:', err)
            showToast('处理消息时发生错误', 'error')
        }
    }
}

export function updateConnectionStatus(connected) {
    const statusEl = safeGetElement('connectionStatusText')
    const reconnectBtn = safeGetElement('reconnectBtn')
    if (!statusEl) {
        console.warn('connectionStatusText element not found')
        return
    }

    if (connected) {
        statusEl.className = 'connection-status online'
        statusEl.innerHTML = '<span class="connection-dot"></span><span>已连接</span>'
        if (reconnectBtn) {
            reconnectBtn.disabled = true
            reconnectBtn.style.opacity = '0.5'
            reconnectBtn.style.cursor = 'not-allowed'
        }
    } else {
        statusEl.className = 'connection-status'
        if (isReconnecting && reconnectAttempts > 0) {
            statusEl.innerHTML = `
                <span class="connection-dot"></span>
                <span>重连中 (${reconnectAttempts}/${maxReconnectAttempts})</span>
                <button onclick="stopAutoReconnect()" style="margin-left: 8px; padding: 2px 6px; font-size: 11px; background: var(--accent-error); border: none; border-radius: 3px; color: white; cursor: pointer;">停止</button>
            `
        } else {
            statusEl.innerHTML = '<span class="connection-dot"></span><span>未连接</span>'
        }
        if (reconnectBtn) {
            reconnectBtn.disabled = false
            reconnectBtn.style.opacity = '1'
            reconnectBtn.style.cursor = 'pointer'
        }
    }
}

export function sendMessage(type, data) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        if (isReconnecting || isConnected) {
            messageQueue.push({ type, data, timestamp: Date.now() })
            return true
        } else {
            showToast('未连接到服务器', 'error')
            return false
        }
    }

    if (currentDevice && currentDevice.device_id) {
        data.device_id = currentDevice.device_id
    }

    if (consoleId) {
        data.console_id = consoleId
    }

    try {
        const json = JSON.stringify(data)
        const bytes = new TextEncoder().encode(json)
        const msg = new Uint8Array(1 + 2 + bytes.length)
        msg[0] = type
        msg[1] = (bytes.length >> 8) & 0xFF
        msg[2] = bytes.length & 0xFF
        msg.set(bytes, 3)

        if (type === MSG_TYPES.FILE_REQUEST) {
        }

        ws.send(msg)
        return true
    } catch (error) {
        console.error('Error sending message:', error)
        if (isReconnecting || isConnected) {
            messageQueue.push({ type, data, timestamp: Date.now() })
            return true
        } else {
            showToast('发送消息失败', 'error')
            return false
        }
    }
}

export function reconnectWebSocket() {
    isReconnecting = false
    reconnectAttempts = 0
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
        reconnectTimeout = null
    }
    showToast('手动重新连接...', 'info')
    connectWebSocket()
}

function processMessageQueue() {
    if (messageQueue.length > 0) {
        const now = Date.now()
        const maxAge = 30000

        const validMessages = messageQueue.filter(msg => now - msg.timestamp < maxAge)

        if (validMessages.length !== messageQueue.length) {
        }

        messageQueue = []

        validMessages.forEach((msg, index) => {
            setTimeout(() => {
                if (currentDevice && currentDevice.device_id) {
                    msg.data.device_id = currentDevice.device_id
                }
                try {
                    const json = JSON.stringify(msg.data)
                    const bytes = new TextEncoder().encode(json)
                    const message = new Uint8Array(1 + 2 + bytes.length)
                    message[0] = msg.type
                    message[1] = (bytes.length >> 8) & 0xFF
                    message[2] = bytes.length & 0xFF
                    message.set(bytes, 3)
                    ws.send(message)
                } catch (error) {
                    console.error('Error sending queued message:', error)
                }
            }, index * 10)
        })
    }
}

export function stopAutoReconnect() {
    isReconnecting = false
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
        reconnectTimeout = null
    }
    showToast('已停止自动重连', 'info')
    updateConnectionStatus(false)
}

export function getWsUrl() {
    const settings = loadSettings()
    if (settings.wsUrl) {
        return settings.wsUrl
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    if (window.location.hostname.includes('github.dev')) {
        const wsHostname = window.location.hostname.replace(/-\d+(\.app\.github\.dev)$/, '-8765$1')
        return `${protocol}//${wsHostname}/`
    } else if (window.location.hostname && window.location.hostname !== '') {
        return `${protocol}//${window.location.hostname}:8765`
    } else {
        return `${protocol}//localhost:8765`
    }
}

// Make stopAutoReconnect available globally for the inline onclick handler
window.stopAutoReconnect = stopAutoReconnect
