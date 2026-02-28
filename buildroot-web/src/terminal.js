// ============================================
// Terminal Module - xterm.js Implementation
// ============================================

import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { SearchAddon } from '@xterm/addon-search'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { showToast } from './utils.js'
import { MSG_TYPES } from './config.js'
import { sendMessage } from './websocket.js'

export let term = null
export let fitAddon = null
export let searchAddon = null
export let webLinksAddon = null
export let terminalInitialized = false
export let ptySessionId = null

// External references (will be set by main.js)
let currentDevice = null
let currentTab = 'terminal'

export function setTerminalContext(context) {
    currentDevice = context.currentDevice
    currentTab = context.currentTab
}

export function initTerminal() {
    if (terminalInitialized) return

    const terminalContainer = document.getElementById('terminalXtermWrapper')
    if (!terminalContainer) return

    term = new Terminal({
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

    fitAddon = new FitAddon()
    searchAddon = new SearchAddon()
    webLinksAddon = new WebLinksAddon()

    term.loadAddon(fitAddon)
    term.loadAddon(searchAddon)
    term.loadAddon(webLinksAddon)

    term.open(terminalContainer)
    fitAddon.fit()

    term.onData(data => {
        if (!ptySessionId) return
        const base64Data = btoa(data)
        sendMessage(MSG_TYPES.PTY_DATA, {
            session_id: ptySessionId,
            data: base64Data
        })
    })

    term.onResize(size => {
        if (!ptySessionId) return
        sendMessage(MSG_TYPES.PTY_RESIZE, {
            session_id: ptySessionId,
            rows: size.rows,
            cols: size.cols
        })
        const sizeEl = document.getElementById('terminalSize')
        if (sizeEl) sizeEl.textContent = `${size.cols}x${size.rows}`
    })

    window.addEventListener('resize', () => {
        if (currentTab === 'terminal') {
            fitAddon.fit()
        }
    })

    const oldInput = document.getElementById('terminalInput')
    if (oldInput) oldInput.style.display = 'none'

    terminalInitialized = true
    term.writeln('\x1b[1;34mWelcome to Buildroot Agent Terminal\x1b[0m')
    term.writeln('Initializing...')
}

export function connectTerminal() {
    try {
        if (!terminalInitialized) {
            initTerminal()
        }

        if (!currentDevice) {
            showToast('请先选择一个设备', 'warning')
            term.writeln('\x1b[1;33mPlease select a device first.\x1b[0m')
            return
        }

        if (ptySessionId) {
            try {
                sendMessage(MSG_TYPES.PTY_CLOSE, { session_id: ptySessionId })
            } catch (e) {
                console.warn('Error closing existing PTY session:', e)
            }
            ptySessionId = null
        }

        const newSessionId = Math.floor(Math.random() * 1000000000)
        console.log('Creating PTY session:', newSessionId)

        term.reset()
        term.writeln(`\x1b[1;32mConnecting to ${currentDevice.name || currentDevice.device_id}...\x1b[0m`)

        ptySessionId = newSessionId

        const dims = fitAddon.proposeDimensions()
        const rows = dims ? dims.rows : 24
        const cols = dims ? dims.cols : 80

        const success = sendMessage(MSG_TYPES.PTY_CREATE, {
            session_id: newSessionId,
            rows: rows,
            cols: cols
        })

        if (success) {
            updateTerminalStatus('connecting')
            setTimeout(() => {
                if (ptySessionId === newSessionId) {
                console.log('PTY session waiting for response...')
                }
            }, 8000)
        } else {
            term.writeln('\x1b[1;31mFailed to send connection request.\x1b[0m')
            showToast('发送终端连接请求失败', 'error')
            ptySessionId = null
            updateTerminalStatus('disconnected')
        }
    } catch (error) {
        console.error('Error in connectTerminal:', error)
        if (term) term.writeln(`\r\n\x1b[1;31mConnection Error: ${error.message}\x1b[0m`)
        showToast(`终端连接出错: ${error.message}`, 'error')
        ptySessionId = null
        updateTerminalStatus('disconnected')
    }
}

export function handleTerminalData(data) {
    if (data.data && term) {
        try {
            const text = atob(data.data)
            term.write(text)
        } catch (e) {
            console.error('Error decoding terminal data:', e)
        }
    }
}

export function handlePtyCreateResponse(data) {
    console.log('PTY create response:', data)

    if (data.success === true || data.status === 'created' || data.status === 'success') {
        showToast('终端连接成功', 'success')
        updateTerminalStatus('connected')

        const ptyCount = data.pty_count || 0
        const ptyMax = data.pty_max || 8
        term.writeln(`\r\n\x1b[1;36mPTY Sessions: ${ptyCount}/${ptyMax}\x1b[0m\r\n`)

        term.focus()
        fitAddon.fit()
        return
    }

    if (data.success === false || data.error) {
        const errorMsg = data.error || data.message || '终端连接失败'
        term.writeln(`\r\n\x1b[1;31mConnection Failed: ${errorMsg}\x1b[0m`)
        showToast(`终端连接失败: ${errorMsg}`, 'error')
        updateTerminalStatus('disconnected')
        ptySessionId = null
    }
}

export function handlePtyClose(data) {
    console.log('PTY close received:', data)
    const sessionId = data.session_id || data.id
    const reason = data.reason || data.error

    if (ptySessionId && ptySessionId === sessionId) {
        ptySessionId = null
        if (reason === 'session timeout') {
            term.writeln('\r\n\x1b[1;31mTerminal session closed: session timeout (no activity).\x1b[0m')
            showToast('终端会话因长时间无活动已超时关闭', 'warning')
        } else {
            term.writeln('\r\n\x1b[33mTerminal session closed.\x1b[0m')
            showToast('终端会话已关闭', 'info')
        }
        updateTerminalStatus('disconnected')
    }
}

export function appendTerminalOutput(text) {
    if (term) {
        term.write(text)
    } else {
        console.warn('Terminal not initialized, cannot write:', text)
    }
}

export function clearTerminal() {
    if (term) {
        term.clear()
    }
}

export function reconnectTerminal() {
    if (term) term.clear()
    // reconnectWebSocket will be called by importing module
}

export function updateTerminalStatus(status) {
    const dot = document.getElementById('terminalStatusDot')
    const text = document.getElementById('terminalStatusText')
    if (!dot || !text) return

    if (status === 'connected') {
        dot.className = 'terminal-status-dot connected'
        text.textContent = '已连接'
        text.style.color = 'var(--accent-success)'
    } else if (status === 'connecting') {
        dot.className = 'terminal-status-dot'
        dot.style.background = 'var(--accent-warning)'
        dot.style.boxShadow = '0 0 6px var(--accent-warning)'
        text.textContent = '连接中...'
        text.style.color = 'var(--accent-warning)'
    } else {
        dot.className = 'terminal-status-dot'
        dot.style.background = 'var(--text-muted)'
        dot.style.boxShadow = 'none'
        text.textContent = '未连接'
        text.style.color = 'var(--text-muted)'
    }
}

export function terminalSearchToggle() {
    const bar = document.getElementById('terminalSearchBar')
    const input = document.getElementById('terminalSearchInput')
    if (bar) {
        bar.classList.toggle('visible')
        if (bar.classList.contains('visible') && input) {
            input.focus()
        } else if (term) {
            searchAddon.clearDecorations()
            term.focus()
        }
    }
}

export function terminalSearchNext() {
    const input = document.getElementById('terminalSearchInput')
    if (input && searchAddon) {
        searchAddon.findNext(input.value, {
            decorations: {
                matchBackground: '#3d3d5c',
                matchBorder: '#6366f1',
                matchOverviewRuler: '#6366f1',
                activeMatchBackground: '#6366f1',
                activeMatchBorder: '#ffffff',
                activeMatchColorOverviewRuler: '#ffffff'
            }
        })
    }
}

export function terminalSearchPrev() {
    const input = document.getElementById('terminalSearchInput')
    if (input && searchAddon) {
        searchAddon.findPrevious(input.value, {
            decorations: {
                matchBackground: '#3d3d5c',
                matchBorder: '#6366f1',
                matchOverviewRuler: '#6366f1',
                activeMatchBackground: '#6366f1',
                activeMatchBorder: '#ffffff',
                activeMatchColorOverviewRuler: '#ffffff'
            }
        })
    }
}

export function handleTerminalSearchKey(e) {
    if (e.key === 'Enter') {
        if (e.shiftKey) {
            terminalSearchPrev()
        } else {
            terminalSearchNext()
        }
    } else if (e.key === 'Escape') {
        terminalSearchToggle()
    }
}
