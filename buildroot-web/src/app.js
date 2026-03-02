// ============================================
// Ace Editor - Initialization and Management
// ============================================

import ace from 'ace-builds'
import { showToast, safeGetElement, formatBytes, getFileIcon, isFileEditable, isBinaryFile, loadSettings, escapeHtml } from './utils.js'
import { MSG_TYPES, IMAGE_EXTS, BINARY_EXTS, MONITOR_REFRESH_INTERVAL, STATE_LABELS } from './config.js'
import { sendMessage, isConnected, isReconnecting } from './websocket.js'
// ============================================
// Application State
// ============================================

let devices = []
let currentDevice = null
let currentTab = 'terminal'
let currentPath = '/root'
let paginationState = {
    currentPage: 0,
    pageSize: 20,
    totalCount: 0,
    searchKeyword: '',
    isLoading: false,
    debounceTimer: null
}

// File Tree State
let fileTreeData = {}
let selectedFiles = new Set()
let lastSelectedFile = null
let expandedDirs = new Set(['/'])
let allTreeItems = []
let pendingFilePreview = null
let pendingFileSave = null
let fileListChunks = {}

// Editor State
let isEditorActive = false
let editorCurrentFile = null
let editorWordWrap = false
let editorLastSavedContent = ''
let syntaxHighlightEnabled = true
let aceEditor = null
let aceSession = null
let aceEditorReady = false
let openEditorTabs = new Map()
let activeEditorTabPath = null

// Monitor State
let cachedProcesses = []
let processSortKey = 'cpu'
let statusUpdateThrottle = null
let processSortAsc = false
let processMemTotal = 1
let monitorRefreshInterval = null
let isMonitorAutoRefreshEnabled = true
let downloadChunks = {}

// Ping Monitor State
let pingTargets = []
let pingResults = {}
let isPingAutoRefreshEnabled = true
let pingRefreshInterval = null

// Refresh throttle state
let lastSystemRefreshTime = 0
let lastPingRefreshTime = 0
const REFRESH_COOLDOWN_MS = 2000

// Flag to track manual refresh (for change detection toast)
let isManualSystemRefresh = false
let isManualPingRefresh = false

// Previous data for change detection
let previousSystemStatus = null
let previousPingResults = null

// WebSocket state (re-exported from websocket.js)
// ============================================
// Ace Editor - Initialization and Management
// ============================================
export function initAceEditor() {
    try {
        if (typeof ace === 'undefined') {
            console.error('[Ace Editor] ace is undefined. Check if ace-builds loaded correctly.')
            return
        }
        const container = document.getElementById('aceEditor')
        if (!container) {
            console.error('[Ace Editor] 找不到容器 #aceEditor')
            return
        }

        aceEditor = ace.edit("aceEditor")
        aceSession = aceEditor.getSession()
        aceSession.setUseWorker(false)
        aceEditor.setOptions({
            enableBasicAutocompletion: true,
            enableSnippets: true,
            enableLiveAutocompletion: true,
            fontSize: '13px',
            fontFamily: "'JetBrains Mono', monospace",
            showPrintMargin: false,
            wrap: false,
            indentedSoftWrap: true,
            cursorStyle: 'ace',
        })

        aceEditor.setTheme("ace/theme/monokai")

        aceSession.on("change", handleEditorChange)
        aceEditor.selection.on("changeCursor", function() {
            updateAceCursorInfo()
        })
        aceEditor.selection.on("changeSelection", function() {
            updateAceCursorInfo()
        })

        aceEditor.resize()
        aceEditorReady = true
    } catch (e) {
        console.error('[Ace Editor] 初始化失败:', e)
        aceEditorReady = false
    }
}

export function displayEditorContent(content, readonly = false, retryCount = 0) {
    const preview = document.getElementById('filePreview')
    const editorContainer = document.getElementById('fileEditorContainer')
    if (preview) preview.style.display = 'flex'
    if (editorContainer) editorContainer.style.display = 'flex'

    if (!aceEditorReady || !aceEditor) {
        if (retryCount < 10) {
            setTimeout(() => {
                displayEditorContent(content, readonly, retryCount + 1)
            }, 100)
        } else {
            console.error('[Ace Editor] 初始化超时，无法显示内容')
        }
        return
    }


    aceSession.off("change", handleEditorChange)

    aceEditor.setValue(content, -1)

    aceSession.on("change", handleEditorChange)

    aceEditor.resize()

    aceEditor.setReadOnly(readonly)

    if (editorCurrentFile) {
        const languageMode = getAceLanguageMode(editorCurrentFile.name)
        if (aceSession) {
            aceSession.setMode(languageMode)
        }

        let fileTypeLabel
        if (!editorCurrentFile.editable) {
            const ext = editorCurrentFile.name.split('.').pop().toLowerCase()
            fileTypeLabel = BINARY_TYPE_LABELS[ext] || 'Binary'
        } else {
            fileTypeLabel = getFileTypeLabel(editorCurrentFile.name)
        }

        const fileTypeEl = document.getElementById('editorFileType')
        if (fileTypeEl) {
            fileTypeEl.textContent = fileTypeLabel
        }
    }

    const btnEdit = document.getElementById('btnEditFile')
    const btnSave = document.getElementById('btnSaveFile')
    const btnCancel = document.getElementById('btnCancelEdit')
    if (readonly) {
        if (btnEdit && editorCurrentFile?.editable) {
            btnEdit.style.display = 'inline-flex'
        }
        if (btnSave) btnSave.style.display = 'none'
        if (btnCancel) btnCancel.style.display = 'none'
        isEditorActive = false
    } else {
        if (btnEdit) btnEdit.style.display = 'none'
        if (btnSave) btnSave.style.display = 'inline-flex'
        if (btnCancel) btnCancel.style.display = 'inline-flex'
        isEditorActive = true
    }
}

export function toggleEditor() {
    if (isEditorActive) {
        exitEditor()
    } else {
        enterEditor()
    }
}

export function enterEditor() {
    if (!editorCurrentFile) {
        showToast('没有打开的文件', 'warning')
        return
    }

    const currentContent = aceEditor ? aceEditor.getValue() : ''
    if (!isFileEditable(editorCurrentFile.name, currentContent)) {
        showToast('该文件类型不支持编辑', 'warning')
        return
    }

    if (editorCurrentFile.size > 1024 * 1024) {
        showToast('文件过大，不支持在线编辑 (最大 1MB)', 'warning')
        return
    }

    const tabPath = editorCurrentFile.path
    if (openEditorTabs.has(tabPath)) {
        switchToTab(tabPath)
        return
    }

    let content
    if (aceEditor && aceEditorReady) {
        content = aceEditor.getValue()
    } else {
        return
    }

    const newTab = {
        path: tabPath,
        name: editorCurrentFile.name,
        size: editorCurrentFile.size,
        content: content,
        originalContent: content,
        modified: false,
        editable: editorCurrentFile.editable || true,
        undoStack: [],
        redoStack: [],
        scrollTop: 0,
        cursorStart: 0,
        cursorEnd: 0,
        mtime: editorCurrentFile.mtime || 0
    }
    openEditorTabs.set(tabPath, newTab)

    editorLastSavedContent = content
    activeEditorTabPath = tabPath

    displayEditorContent(content, false)

    resetEditorState()

    const languageMode = getAceLanguageMode(editorCurrentFile.name)
    if (aceSession) {
        aceSession.setMode(languageMode)
    }

    renderEditorTabs()

    showToast('已进入编辑模式', 'info')
}

export function renderEditorTabs() {
    const tabsBar = document.getElementById('editorTabsBar')
    if (!tabsBar) return

    let html = ''
    openEditorTabs.forEach((tab, path) => {
        const isActive = path === activeEditorTabPath
        const icon = getFileIcon(tab.name)
        const displayName = tab.name.length > 25 ? tab.name.substring(0, 22) + '...' : tab.name

        html += `<div class="editor-tab ${isActive ? 'active' : ''}" data-path="${path}" onclick="switchToTab('${path}')">
            <span>${icon}</span>
            <span class="tab-name">${displayName}</span>
            ${tab.modified ? '<span class="tab-modified"></span>' : ''}
            <span class="tab-close" onclick="event.stopPropagation(); closeEditorTab('${path}')">×</span>
        </div>`
    })

    tabsBar.innerHTML = html
}

export function switchToTab(path) {
    if (!openEditorTabs.has(path)) return

    if (activeEditorTabPath && openEditorTabs.has(activeEditorTabPath)) {
        const currentTab = openEditorTabs.get(activeEditorTabPath)
        const textarea = document.getElementById('editorTextarea')
        if (textarea) {
            currentTab.content = textarea.value
            currentTab.scrollTop = textarea.scrollTop
            currentTab.cursorStart = textarea.selectionStart
            currentTab.cursorEnd = textarea.selectionEnd
        }
    }

    activeEditorTabPath = path
    const newTab = openEditorTabs.get(path)

    editorCurrentFile = {
        path: newTab.path,
        name: newTab.name,
        size: newTab.size,
        mtime: newTab.mtime || 0,
        editable: newTab.editable || true
    }

    displayEditorContent(newTab.content, false)

    resetEditorState()
}

export function closeEditorTab(path) {
    if (!openEditorTabs.has(path)) return

    const tab = openEditorTabs.get(path)

    if (tab.modified) {
        if (!confirm(`文件 ${tab.name} 已修改，确定关闭？`)) return
    }

    openEditorTabs.delete(path)

    if (path === activeEditorTabPath) {
        const remainingTabs = Array.from(openEditorTabs.keys())
        if (remainingTabs.length > 0) {
            switchToTab(remainingTabs[0])
        } else {
            exitEditor()
            openEditorTabs.clear()
            activeEditorTabPath = null
            renderEditorTabs()
        }
    } else {
        renderEditorTabs()
    }
}

export function exitEditor() {
    isEditorActive = false

    if (aceEditor && aceEditorReady) {
        aceEditor.setReadOnly(true)

        const btnEdit = document.getElementById('btnEditFile')
        const btnSave = document.getElementById('btnSaveFile')
        const btnCancel = document.getElementById('btnCancelEdit')
        const badge = document.getElementById('editorModifiedBadge')

        if (btnEdit && editorCurrentFile?.editable) {
            btnEdit.style.display = 'inline-flex'
        }
        if (btnSave) btnSave.style.display = 'none'
        if (btnCancel) btnCancel.style.display = 'none'

        if (badge) badge.style.display = 'none'
    }
}

export function cancelEdit() {
    if (isEditorDirty()) {
        if (!confirm('放弃所有修改？')) return
    }
    exitEditor()
}

export function isEditorDirty() {
    if (!aceEditor || !aceSession) return false
    const undoManager = aceSession.getUndoManager()
    return !undoManager.isClean()
}

export function markEditorAsClean() {
    if (!aceEditor || !aceSession) return
    const undoManager = aceSession.getUndoManager()
    undoManager.markClean()
}

export function resetEditorState() {
    if (!aceEditor || !aceSession) return
    const undoManager = aceSession.getUndoManager()
    undoManager.reset()
    markEditorAsClean()

    const badge = document.getElementById('editorModifiedBadge')
    if (badge) badge.style.display = 'none'

    if (activeEditorTabPath && openEditorTabs.has(activeEditorTabPath)) {
        const tab = openEditorTabs.get(activeEditorTabPath)
        tab.modified = false
        renderEditorTabs()
    }
}

export function handleEditorChange(delta) {
    const content = aceEditor.getValue()

    if (activeEditorTabPath && openEditorTabs.has(activeEditorTabPath)) {
        const tab = openEditorTabs.get(activeEditorTabPath)
        tab.content = content
        tab.modified = isEditorDirty()
    }

    const isDirty = isEditorDirty()
    const badge = document.getElementById('editorModifiedBadge')
    if (badge) badge.style.display = isDirty ? 'inline-block' : 'none'

    renderEditorTabs()
}

export function updateAceCursorInfo() {
    const info = document.getElementById('editorLineInfo')
    if (!info || !aceEditor) return

    const cursor = aceEditor.selection.getCursor()
    const selectionRange = aceEditor.getSelectionRange()

    const line = cursor.row + 1
    const col = cursor.column + 1

    const startRow = selectionRange.start.row
    const startCol = selectionRange.start.column
    const endRow = selectionRange.end.row
    const endCol = selectionRange.end.column

    let selLen = 0
    if (startRow !== endRow || startCol !== endCol) {
        if (startRow === endRow) {
            selLen = endCol - startCol
        } else {
            selLen = aceEditor.session.getTextRange(selectionRange).length
        }
    }

    if (selLen > 0) {
        info.textContent = `行 ${line}, 列 ${col} (选中 ${selLen} 字符)`
    } else {
        info.textContent = `行 ${line}, 列 ${col}`
    }
}

export function saveFileToDevice() {
    if (!currentDevice || !editorCurrentFile) {
        showToast('无法保存：没有选中设备或文件', 'warning')
        return
    }

    const content = aceEditor ? aceEditor.getValue() : ''

    if (!isEditorDirty()) {
        showToast('文件没有修改', 'info')
        return
    }

    const btnSave = document.getElementById('btnSaveFile')
    if (btnSave) {
        btnSave.disabled = true
        btnSave.textContent = '⏳ 保存中...'
    }

    pendingFileSave = {
        path: editorCurrentFile.path,
        name: editorCurrentFile.name,
        content: content
    }

    const encoded = btoa(unescape(encodeURIComponent(content)))
    sendMessage(MSG_TYPES.FILE_REQUEST, {
        action: 'write',
        filepath: editorCurrentFile.path,
        content: encoded,
        mtime: editorCurrentFile.mtime || 0,
        force: false,
        encoding: 'utf-8',
        request_id: 'save-' + Date.now()
    })

    setTimeout(() => {
        if (pendingFileSave && pendingFileSave.path === editorCurrentFile?.path) {
            onFileSaveSuccess()
        }
    }, 3000)
}

export function onFileSaveSuccess() {
    pendingFileSave = null

    const btnSave = document.getElementById('btnSaveFile')
    if (btnSave) {
        btnSave.disabled = false
        btnSave.textContent = '💾 保存'
    }

    const content = aceEditor ? aceEditor.getValue() : ''
    editorLastSavedContent = content

    markEditorAsClean()

    if (activeEditorTabPath && openEditorTabs.has(activeEditorTabPath)) {
        const tab = openEditorTabs.get(activeEditorTabPath)
        tab.originalContent = content
        tab.modified = false
        tab.mtime = editorCurrentFile.mtime || 0
        renderEditorTabs()
    }

    exitEditor()

    showToast(`已保存: ${editorCurrentFile?.name || '文件'}`, 'success')
}

export function onFileSaveError(error) {
    pendingFileSave = null

    const btnSave = document.getElementById('btnSaveFile')
    if (btnSave) {
        btnSave.disabled = false
        btnSave.textContent = '💾 保存'
    }

    if (error && error.includes('已被其他用户修改')) {
        showFileConflictDialog(error)
    } else if (error && error.includes('已修改，请重新加载')) {
        showFileConflictDialog(error)
    } else {
        showToast('保存失败: ' + (error || '未知错误'), 'error')
    }
}

export function showFileConflictDialog(error) {
    const overlay = document.getElementById('fileConflictDialog')
    if (overlay) {
        overlay.style.display = 'flex'
        const errorMsg = document.getElementById('fileConflictError')
        if (errorMsg) {
            errorMsg.textContent = error || '文件已被其他用户修改'
        }
    } else {
        const div = document.createElement('div')
        div.id = 'fileConflictDialog'
        div.className = 'modal-overlay'
        div.style.cssText = 'display: flex;'
        div.innerHTML = `
            <div class="modal" style="max-width: 450px;">
                <div class="modal-header">
                    <div class="modal-title">⚠️ 文件冲突</div>
                </div>
                <div class="modal-body">
                    <p id="fileConflictError" style="color: var(--text-primary); margin-bottom: 16px;">${error || '文件已被其他用户修改'}</p>
                    <p style="color: var(--text-muted); font-size: 13px;">选择是否覆盖服务器上的文件？</p>
                </div>
                <div class="modal-footer">
                    <button class="btn" onclick="cancelFileSave()">取消</button>
                    <button class="btn btn-primary" onclick="confirmFileSave(true)">🔄 强制覆盖</button>
                </div>
            </div>
        `
        document.body.appendChild(div)
    }
}

export function cancelFileSave() {
    const overlay = document.getElementById('fileConflictDialog')
    if (overlay) {
        overlay.style.display = 'none'
    }
    showToast('保存已取消', 'info')
}

export function confirmFileSave(force) {
    const overlay = document.getElementById('fileConflictDialog')
    if (overlay) {
        overlay.style.display = 'none'
    }

    if (!force || !editorCurrentFile) return

    const content = aceEditor ? aceEditor.getValue() : ''
    const btnSave = document.getElementById('btnSaveFile')
    if (btnSave) {
        btnSave.disabled = true
        btnSave.textContent = '⏳ 保存中...'
    }

    pendingFileSave = {
        path: editorCurrentFile.path,
        name: editorCurrentFile.name,
        content: content
    }

    const encoded = btoa(unescape(encodeURIComponent(content)))
    sendMessage(MSG_TYPES.FILE_REQUEST, {
        action: 'write',
        filepath: editorCurrentFile.path,
        content: encoded,
        mtime: 0,
        force: true,
        encoding: 'utf-8',
        request_id: 'save-force-' + Date.now()
    })
}

// ============================================
// System Monitor
// ============================================

export function updateSystemStatus(data) {
    // 优化: 渲染节流 - 避免频繁DOM更新
    if (statusUpdateThrottle) {
        clearTimeout(statusUpdateThrottle)
    }
    statusUpdateThrottle = setTimeout(() => {
        _renderSystemStatus(data)
        statusUpdateThrottle = null
    }, 500)
}

function _renderSystemStatus(data) {
    
    // Update status timestamp display
    const timestamp = data.status_timestamp ? new Date(data.status_timestamp) : new Date()
    const timeEl = safeGetElement('metricStatusTime')
    if (timeEl) {
        const now = new Date()
        const diffMs = now - timestamp
        const diffSecs = Math.floor(diffMs / 1000)
        
        // Format relative time
        let relativeTime
        if (diffSecs < 60) {
            relativeTime = `刚刚`
        } else if (diffSecs < 3600) {
            relativeTime = `${Math.floor(diffSecs / 60)}分钟前`
        } else if (diffSecs < 86400) {
            relativeTime = `${Math.floor(diffSecs / 3600)}小时前`
        } else {
            relativeTime = `${Math.floor(diffSecs / 86400)}天前`
        }
        
        // Format absolute time
        const absoluteTime = timestamp.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        })
        
        timeEl.textContent = `${absoluteTime} (${relativeTime})`
        timeEl.title = `数据更新时间: ${timestamp.toLocaleString('zh-CN')}`
        
        // Add visual indicator for stale data
        if (diffSecs > 300) { // 5 minutes
            timeEl.style.color = 'var(--accent-warning)'
        } else {
            timeEl.style.color = 'var(--text-muted)'
        }
    }

    if (currentDevice && data.device_id === currentDevice.device_id) {
        renderDeviceList()
    }

    if (data.ip_addr && currentDevice) {
        const detailIpEl = safeGetElement('detailDeviceIp')
        const metricIpEl = safeGetElement('metricIp')
        if (detailIpEl) detailIpEl.textContent = data.ip_addr
        if (metricIpEl) metricIpEl.textContent = data.ip_addr
        currentDevice.ip_addr = data.ip_addr
    }

    const cpuUsage = data.cpu_usage || 0
    const metricCpuEl = safeGetElement('metricCpu')
    const metricCpuDetailEl = safeGetElement('metricCpuDetail')
    const metricCpuBarEl = safeGetElement('metricCpuBar')
    const metricCpuUserEl = safeGetElement('metricCpuUser')
    const metricCpuSysEl = safeGetElement('metricCpuSys')

    if (metricCpuEl) metricCpuEl.textContent = cpuUsage.toFixed(1) + '%'
    if (metricCpuDetailEl) metricCpuDetailEl.textContent = `${data.cpu_cores || '--'} 核心`
    if (metricCpuBarEl) {
        metricCpuBarEl.style.width = cpuUsage + '%'
        metricCpuBarEl.className = 'metric-bar-fill ' + (cpuUsage > 80 ? 'high' : cpuUsage > 50 ? 'medium' : 'low')
    }
    if (metricCpuUserEl) metricCpuUserEl.textContent = (data.cpu_user || 0).toFixed(1) + '%'
    if (metricCpuSysEl) metricCpuSysEl.textContent = (data.cpu_system || 0).toFixed(1) + '%'

    const memTotal = data.mem_total || 1
    processMemTotal = memTotal
    const memUsed = data.mem_used || 0
    const memPercent = (memUsed / memTotal) * 100
    const metricMemEl = safeGetElement('metricMem')
    const metricMemDetailEl = safeGetElement('metricMemDetail')
    const metricMemBarEl = safeGetElement('metricMemBar')
    const metricMemUsedEl = safeGetElement('metricMemUsed')
    const metricMemFreeEl = safeGetElement('metricMemFree')

    if (metricMemEl) metricMemEl.textContent = formatBytes(memUsed * 1024 * 1024)
    if (metricMemDetailEl) metricMemDetailEl.textContent = `共 ${formatBytes(memTotal * 1024 * 1024)}`
    if (metricMemBarEl) {
        metricMemBarEl.style.width = memPercent + '%'
        metricMemBarEl.className = 'metric-bar-fill ' + (memPercent > 80 ? 'high' : memPercent > 50 ? 'medium' : 'low')
    }
    if (metricMemUsedEl) metricMemUsedEl.textContent = formatBytes(memUsed * 1024 * 1024)
    if (metricMemFreeEl) metricMemFreeEl.textContent = formatBytes((memTotal - memUsed) * 1024 * 1024)

    const diskTotal = data.disk_total || 1
    const diskUsed = data.disk_used || 0
    const diskPercent = (diskUsed / diskTotal) * 100
    const metricDiskEl = safeGetElement('metricDisk')
    const metricDiskDetailEl = safeGetElement('metricDiskDetail')
    const metricDiskBarEl = safeGetElement('metricDiskBar')
    const metricDiskUsedEl = safeGetElement('metricDiskUsed')
    const metricDiskFreeEl = safeGetElement('metricDiskFree')

    if (metricDiskEl) metricDiskEl.textContent = diskPercent.toFixed(1) + '%'
    if (metricDiskDetailEl) metricDiskDetailEl.textContent = `${formatBytes(diskUsed * 1024 * 1024)} / ${formatBytes(diskTotal * 1024 * 1024)}`
    if (metricDiskBarEl) {
        metricDiskBarEl.style.width = diskPercent + '%'
        metricDiskBarEl.className = 'metric-bar-fill ' + (diskPercent > 80 ? 'high' : diskPercent > 50 ? 'medium' : 'low')
    }
    if (metricDiskUsedEl) metricDiskUsedEl.textContent = formatBytes(diskUsed * 1024 * 1024)
    if (metricDiskFreeEl) metricDiskFreeEl.textContent = formatBytes((diskTotal - diskUsed) * 1024 * 1024)

    const metricLoadEl = safeGetElement('metricLoad')
    const metricLoad1El = safeGetElement('metricLoad1')
    const metricLoad5El = safeGetElement('metricLoad5')
    const metricLoad15El = safeGetElement('metricLoad15')
    const metricUptimeEl = safeGetElement('metricUptime')

    if (metricLoadEl) metricLoadEl.textContent = (data.load_1min || 0).toFixed(2)
    if (metricLoad1El) metricLoad1El.textContent = (data.load_1min || 0).toFixed(2)
    if (metricLoad5El) metricLoad5El.textContent = (data.load_5min || 0).toFixed(2)
    if (metricLoad15El) metricLoad15El.textContent = (data.load_15min || 0).toFixed(2)
    if (metricUptimeEl) metricUptimeEl.textContent = formatUptime(data.uptime || 0)

    const metricMacEl = safeGetElement('metricMac')
    if (metricMacEl) metricMacEl.textContent = data.mac_addr || '--'
    const metricRxEl = safeGetElement('metricRx')
    const metricTxEl = safeGetElement('metricTx')
    if (metricRxEl) metricRxEl.textContent = formatBytes(data.net_rx_bytes || 0)
    if (metricTxEl) metricTxEl.textContent = formatBytes(data.net_tx_bytes || 0)

    if (currentDevice) {
        currentDevice.cpu_usage = data.cpu_usage
        currentDevice.mem_used = data.mem_used
        currentDevice.load_1min = data.load_1min

        const deviceIndex = devices.findIndex(d => d.device_id === data.device_id)
        if (deviceIndex !== -1) {
            devices[deviceIndex].cpu_usage = data.cpu_usage
            devices[deviceIndex].mem_used = data.mem_used
            devices[deviceIndex].load_1min = data.load_1min
        }

        renderDeviceList()
    }

    if (data.processes && Array.isArray(data.processes)) {
        updateProcessList(data.processes, data.proc_total || data.processes.length)
    }
    
    // Check if data has changed (only for manual refresh)
    if (isManualSystemRefresh) {
        const hasChanged = !previousSystemStatus || 
            previousSystemStatus.cpu_usage !== data.cpu_usage ||
            previousSystemStatus.mem_used !== data.mem_used ||
            previousSystemStatus.disk_used !== data.disk_used ||
            previousSystemStatus.load_1min !== data.load_1min
        
        if (!hasChanged) {
            showToast('系统状态数据无变化', 'info')
        }
        isManualSystemRefresh = false  // Reset flag
    }
    
    // Update previous data
    previousSystemStatus = {
        cpu_usage: data.cpu_usage,
        mem_used: data.mem_used,
        disk_used: data.disk_used,
        load_1min: data.load_1min
    }
}

// ============================================
// Process List
// ============================================
export function updateProcessList(processes, totalCount) {
    cachedProcesses = processes || []

    const badge = safeGetElement('processCountBadge')
    if (badge) badge.textContent = totalCount || cachedProcesses.length

    renderProcessList()
}

export function renderProcessList() {
    const container = safeGetElement('processList')
    if (!container) return

    let list = [...cachedProcesses]

    const searchEl = safeGetElement('processSearch')
    const keyword = searchEl ? searchEl.value.trim().toLowerCase() : ''
    if (keyword) {
        list = list.filter(p =>
            (p.name || '').toLowerCase().includes(keyword) ||
            String(p.pid || '').includes(keyword)
        )
    }

    list.sort((a, b) => {
        let va, vb
        switch (processSortKey) {
            case 'pid': va = a.pid || 0; vb = b.pid || 0; break
            case 'name': va = (a.name || '').toLowerCase(); vb = (b.name || '').toLowerCase()
                return processSortAsc ? va.localeCompare(vb) : vb.localeCompare(va)
            case 'cpu': va = a.cpu || 0; vb = b.cpu || 0; break
            case 'mem': va = a.mem || 0; vb = b.mem || 0; break
            case 'state': va = a.state || ''; vb = b.state || ''
                return processSortAsc ? va.localeCompare(vb) : vb.localeCompare(va)
            default: va = a.cpu || 0; vb = b.cpu || 0
        }
        return processSortAsc ? va - vb : vb - va
    })

    const safeKeyword = keyword ? escapeHtml(keyword) : ''
    if (list.length === 0) {
        container.innerHTML = keyword
            ? `<div class="process-empty"><div class="process-empty-icon">🔍</div><div class="process-empty-text">未找到包含 "${safeKeyword}" 的进程</div><div class="process-empty-hint">尝试其他关键词</div></div>`
            : '<div class="process-empty"><div class="process-empty-icon">📊</div><div class="process-empty-text">等待进程数据</div><div class="process-empty-hint">设备连接后将自动采集进程信息</div></div>'
        return
    }

    container.innerHTML = list.map(p => {
        const cpu = p.cpu || 0
        const memKB = p.mem || 0
        const cpuClass = cpu > 50 ? 'high' : cpu > 20 ? 'medium' : ''
        const memPercent = processMemTotal > 0 ? Math.min((memKB / (processMemTotal * 1024)) * 100, 100) : 0
        const memClass = memPercent > 50 ? 'high' : ''
        const state = p.state || 'S'
        const safeName = escapeHtml(p.name || '--')

        return `<div class="process-row">
            <span class="process-pid">${p.pid || '--'}</span>
            <span class="process-name" title="${safeName}">${safeName}</span>
            <span class="process-metric-cell">
                <span class="process-metric-value">${cpu.toFixed(1)}%</span>
                <span class="process-metric-bar"><span class="process-metric-bar-fill cpu-bar ${cpuClass}" style="width:${Math.min(cpu, 100)}%"></span></span>
            </span>
            <span class="process-metric-cell">
                <span class="process-metric-value">${formatBytes(memKB * 1024)}</span>
                <span class="process-metric-bar"><span class="process-metric-bar-fill mem-bar ${memClass}" style="width:${memPercent.toFixed(1)}%"></span></span>
            </span>
            <span class="process-state"><span class="process-state-dot state-${state}"></span><span class="process-state-text">${stateLabel}</span></span>
            <span class="process-time">${p.time || '--'}</span>
        </div>`
    }).join('')
}

export function sortProcesses(key) {
    if (processSortKey === key) {
        processSortAsc = !processSortAsc
    } else {
        processSortKey = key
        processSortAsc = false
        if (key === 'name' || key === 'pid') processSortAsc = true
    }

    ['Pid', 'Name', 'Cpu', 'Mem', 'State'].forEach(k => {
        const el = safeGetElement('sort' + k)
        const icon = safeGetElement('sortIcon' + k)
        if (el) el.classList.remove('sort-active')
        if (icon) {
            icon.classList.remove('active')
            icon.textContent = '↕'
        }
    })

    const activeKey = key.charAt(0).toUpperCase() + key.slice(1)
    const activeEl = safeGetElement('sort' + activeKey)
    const activeIcon = safeGetElement('sortIcon' + activeKey)
    if (activeEl) activeEl.classList.add('sort-active')
    if (activeIcon) {
        activeIcon.classList.add('active')
        activeIcon.textContent = processSortAsc ? '↑' : '↓'
    }

    renderProcessList()
}

export function filterProcessList() {
    renderProcessList()
}

export function startMonitorAutoRefresh() {
    if (monitorRefreshInterval) {
        clearInterval(monitorRefreshInterval)
    }

    isMonitorAutoRefreshEnabled = true

    if (currentTab === 'monitor') {
        refreshSystemStatus()
        refreshPingStatus()  // 同时刷新 Ping 状态
    }

    monitorRefreshInterval = setInterval(() => {
        if (currentTab === 'monitor' && currentDevice && isMonitorAutoRefreshEnabled) {
            refreshSystemStatus()
            refreshPingStatus()  // 同时刷新 Ping 状态
        }
    }, MONITOR_REFRESH_INTERVAL)

}

export function stopMonitorAutoRefresh() {
    if (monitorRefreshInterval) {
        clearInterval(monitorRefreshInterval)
        monitorRefreshInterval = null
    }
    isMonitorAutoRefreshEnabled = false
}

export function toggleMonitorAutoRefresh() {
    isMonitorAutoRefreshEnabled = !isMonitorAutoRefreshEnabled
    const btn = document.getElementById('autoRefreshBtn')
    if (btn) {
        btn.textContent = isMonitorAutoRefreshEnabled ? '⏸️ 暂停刷新' : '▶️ 自动刷新'
        btn.classList.toggle('btn-primary', isMonitorAutoRefreshEnabled)
    }
    showToast(isMonitorAutoRefreshEnabled ? '自动刷新已开启 (5秒)' : '自动刷新已暂停', 'info')
}

export function refreshSystemStatus() {
    if (!currentDevice) return
    sendMessage(MSG_TYPES.CMD_REQUEST, {
        cmd: 'status',
        request_id: 'status-' + Date.now()
    })
}

export function refreshSystemStatusThrottled() {
    const now = Date.now()
    if (now - lastSystemRefreshTime < REFRESH_COOLDOWN_MS) {
        const remaining = Math.ceil((REFRESH_COOLDOWN_MS - (now - lastSystemRefreshTime)) / 1000)
        showToast(`请等待 ${remaining} 秒后再次刷新`, 'warning')
        return
    }
    lastSystemRefreshTime = now
    isManualSystemRefresh = true  // Mark as manual refresh
    const btn = document.getElementById('systemRefreshBtn')
    if (btn) {
        btn.disabled = true
        btn.textContent = '⏳ 刷新中...'
    }
    refreshSystemStatus()
    setTimeout(() => {
        if (btn) {
            btn.disabled = false
            btn.textContent = '🔄 立即刷新'
        }
    }, 1000)
}

export function refreshPingStatus() {
    if (!currentDevice) return
    sendMessage(MSG_TYPES.CMD_REQUEST, {
        cmd: 'ping',
        request_id: 'ping-' + Date.now()
    })
}

export function refreshPingStatusThrottled() {
    const now = Date.now()
    if (now - lastPingRefreshTime < REFRESH_COOLDOWN_MS) {
        const remaining = Math.ceil((REFRESH_COOLDOWN_MS - (now - lastPingRefreshTime)) / 1000)
        showToast(`请等待 ${remaining} 秒后再次刷新`, 'warning')
        return
    }
    lastPingRefreshTime = now
    isManualPingRefresh = true  // Mark as manual refresh
    const btn = document.getElementById('pingRefreshBtn')
    if (btn) {
        btn.disabled = true
        btn.textContent = '⏳ 刷新中...'
    }
    refreshPingStatus()
    setTimeout(() => {
        if (btn) {
            btn.disabled = false
            btn.textContent = '🔄 立即刷新'
        }
    }, 1000)
}

export function handleCommandResponse(data) {
    if (data.request_id?.startsWith('status')) {
        updateSystemStatus(data)
    } else if (data.request_id?.startsWith('ping')) {
        handlePingStatus(data)
    } else if (data.output) {
        appendTerminalOutput(data.output + '\n')
    }
}

// ============================================
// Scripts
// ============================================

export function runScript() {
    if (!currentDevice) {
        showToast('请先选择设备', 'warning')
        return
    }

    const script = document.getElementById('scriptEditor').value
    if (!script.trim()) {
        showToast('请输入脚本内容', 'warning')
        return
    }

    document.getElementById('scriptModal').classList.add('active')
    document.getElementById('scriptStatusIcon').textContent = '⏳'
    document.getElementById('scriptStatusText').textContent = '执行中...'
    document.getElementById('scriptExitCode').textContent = ''
    document.getElementById('scriptOutput').textContent = '正在执行脚本...'

    sendMessage(0x04, {
        script_id: 'script-' + Date.now(),
        content: script,
        execute: true
    })
}

export function handleScriptResult(data) {
    const modal = safeGetElement('scriptModal')
    const statusIcon = safeGetElement('scriptStatusIcon')
    const statusText = safeGetElement('scriptStatusText')
    const exitCode = safeGetElement('scriptExitCode')
    const output = safeGetElement('scriptOutput')

    if (!modal || !statusIcon || !statusText || !exitCode || !output) {
        console.warn('Script modal elements not found')
        return
    }

    const success = data.success !== false
    const exitCodeVal = data.exit_code || 0

    statusIcon.textContent = success ? '✓' : '✕'
    statusText.textContent = success ? '执行完成' : '执行失败'
    exitCode.textContent = `退出码: ${exitCodeVal}`
    output.textContent = data.output || data.message || '无输出'

    if (statusIcon) statusIcon.style.color = success ? 'var(--accent-success)' : 'var(--accent-error)'
}

export function closeModal() {
    document.getElementById('scriptModal').classList.remove('active')
}

export function copyOutput() {
    const output = document.getElementById('scriptOutput').textContent
    navigator.clipboard.writeText(output).then(() => {
        showToast('已复制到剪贴板', 'success')
    })
}

// ============================================
// Navigation & Settings
// ============================================

export function showView(view) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'))
}

export function switchTab(tab) {
    currentTab = tab

    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'))
    document.querySelector(`[data-tab="${tab}"]`)?.classList.add('active')

    document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'))
    document.getElementById(`tab-${tab}`)?.classList.add('active')

    if (tab === 'terminal') {
        if (!terminalInitialized) {
            setTimeout(() => initTerminal(), 50)
        } else {
            setTimeout(() => {
                if (fitAddon) fitAddon.fit()
                if (term) term.focus()
            }, 50)
        }
    } else if (tab === 'files') {
        // 切换回文件页时不自动刷新，保留文件树的展开状态
    } else if (tab === 'monitor') {
        refreshSystemStatus()
        refreshPingStatus()  // 切换到监控页时立即刷新ping数据
        if (!monitorRefreshInterval && currentDevice) {
            startMonitorAutoRefresh()
        }
    }
}

export function rebootDevice() {
    if (!currentDevice) {
        showToast('请先选择设备', 'warning')
        return
    }

    if (confirm('确定要重启设备吗？')) {
        sendMessage(MSG_TYPES.CMD_REQUEST, { cmd: 'reboot' })
        showToast('重启命令已发送', 'info')
        setTimeout(() => disconnectDevice(), 1000)
    }
}

export function showSettings() {
    loadSettingsToForm()
    document.getElementById('settingsModal').classList.add('active')
}

export function closeSettings() {
    document.getElementById('settingsModal').classList.remove('active')
}

export function loadSettingsToForm() {
    const settings = loadSettings()
    const wsUrlEl = document.getElementById('settingsWsUrl')
    const maxReconnectEl = document.getElementById('settingsMaxReconnect')
    const refreshIntervalEl = document.getElementById('settingsRefreshInterval')
    const autoSelectEl = document.getElementById('settingsAutoSelect')
    if (maxReconnectEl) maxReconnectEl.value = settings.maxReconnectAttempts || 10
    if (refreshIntervalEl) refreshIntervalEl.value = (settings.monitorRefreshInterval || 5000) / 1000
    if (autoSelectEl) autoSelectEl.checked = settings.autoSelectDevice !== false
}

export function saveSettings() {
    const wsUrl = document.getElementById('settingsWsUrl')?.value.trim() || ''
    const maxReconnect = parseInt(document.getElementById('settingsMaxReconnect')?.value) || 10
    const refreshInterval = (parseFloat(document.getElementById('settingsRefreshInterval')?.value) || 5) * 1000
    const autoSelect = document.getElementById('settingsAutoSelect')?.checked !== false
    const settings = {
        wsUrl: wsUrl,
        maxReconnectAttempts: maxReconnect,
        monitorRefreshInterval: refreshInterval,
        autoSelectDevice: autoSelect
    }

    try {
        localStorage.setItem('buildroot-agent-settings', JSON.stringify(settings))
    } catch (e) {
        console.warn('无法保存设置到 localStorage:', e)
    }

    applySettings(settings)

    closeSettings()
    showToast('设置已保存', 'success')

    if (wsUrl !== (loadSettings()._previousWsUrl || '')) {
        reconnectWebSocket()
    }
}

// ============================================
// Message Handler
// ============================================

export function handleMessage(type, data) {
    switch(type) {
        case MSG_TYPES.DEVICE_LIST:
            const { devices: newDevices, total_count, page, page_size } = data
            paginationState.totalCount = total_count
            paginationState.currentPage = page
            paginationState.pageSize = page_size
            paginationState.isLoading = false

            updateDeviceList(newDevices || [])
            renderPaginationUI()
            break
        case MSG_TYPES.DEVICE_DISCONNECT:
            const { device_id: disconnectDeviceId, reason: disconnectReason } = data

            showToast(`设备 ${disconnectDeviceId} 已断开: ${disconnectReason}`, 'warning')

            if (currentDevice && currentDevice.device_id === disconnectDeviceId) {
                disconnectDevice()
            }

            devices = devices.filter(d => d.device_id !== disconnectDeviceId)
            renderDeviceList()
            paginationState.totalCount--
            renderPaginationUI()
            break
        case 0x52:  // DEVICE_UPDATE
            if (data.success) {
                showToast('设备信息已更新', 'success')
                queryDeviceList()
            } else {
                showToast(`更新失败: ${data.message}`, 'error')
            }
            break
        case MSG_TYPES.PING_STATUS:
            handlePingStatus(data)
            break
        case MSG_TYPES.PTY_DATA:
            handleTerminalData(data)
            break
        case MSG_TYPES.PTY_CREATE:
            handlePtyCreateResponse(data)
            break
        case MSG_TYPES.PTY_CLOSE:
            handlePtyClose(data)
            break
        case MSG_TYPES.FILE_LIST_RESPONSE:

            if (data.chunk !== undefined && data.total_chunks) {
                const path = data.path
                const chunk = data.chunk
                const totalChunks = data.total_chunks
                const request_id = data.request_id
                const files = data.files || []


                if (!request_id) {
                    console.error('[FILE_LIST] Missing request_id in chunked response')
                    return
                }

                if (!fileListChunks[request_id]) {
                    fileListChunks[request_id] = {
                        chunks: new Array(totalChunks),
                        totalChunks: totalChunks,
                        receivedChunks: 0,
                        path: path,
                        timestamp: Date.now()
                    }
                } else {
                    fileListChunks[request_id].timestamp = Date.now()
                }

                const chunkData = fileListChunks[request_id]
                if (chunkData.chunks[chunk] !== undefined) {
                    console.warn(`[FILE_LIST] Chunk ${chunk} already received for request ${request_id}, overwriting`)
                }
                chunkData.chunks[chunk] = files
                chunkData.receivedChunks++


                if (chunkData.receivedChunks >= totalChunks) {
                    const allFiles = chunkData.chunks.flat()

                    if (path) {
                        updateTreeWithFiles(path, allFiles)
                    }

                    delete fileListChunks[request_id]
                }
            } else {
                if (data.path) {
                    updateTreeWithFiles(data.path, data.files || [])
                }
            }
            break
        case MSG_TYPES.FILE_DATA:
            handleFileData(data)
            break
        case MSG_TYPES.CMD_RESPONSE:
            handleCommandResponse(data)
            break
        case MSG_TYPES.SCRIPT_RESULT:
            handleScriptResult(data)
            break
        case MSG_TYPES.DOWNLOAD_PACKAGE:
            handleDownloadPackage(data)
            break
        default:
    }
}

// ============================================
// Ping Monitor Functions
// ============================================

export function handlePingStatus(data) {
    const timestamp = data.timestamp || Date.now()
    const results = data.results || []
    
    // Check if ping data has changed (only for manual refresh)
    if (isManualPingRefresh) {
        const newResultsJson = JSON.stringify(results.map(r => ({
            ip: r.ip,
            status: r.status,
            avg_time: r.avg_time,
            packet_loss: r.packet_loss
        })).sort((a, b) => a.ip.localeCompare(b.ip)))
        
        const hasChanged = !previousPingResults || previousPingResults !== newResultsJson
        
        if (!hasChanged) {
            showToast('Ping数据无变化', 'info')
        }
        isManualPingRefresh = false  // Reset flag
        previousPingResults = newResultsJson
    }

    pingResults = {}
    results.forEach(result => {
        pingResults[result.ip] = result
    })

    renderPingResults()
    updatePingStatusTime(timestamp)
}

export function updatePingStatusTime(timestamp) {
    const timeEl = document.getElementById('pingStatusTime')
    if (timeEl) {
        const date = new Date(timestamp)
        const now = new Date()
        const diffMs = now - date
        const diffSecs = Math.floor(diffMs / 1000)
        
        // Format relative time
        let relativeTime
        if (diffSecs < 60) {
            relativeTime = `刚刚`
        } else if (diffSecs < 3600) {
            relativeTime = `${Math.floor(diffSecs / 60)}分钟前`
        } else if (diffSecs < 86400) {
            relativeTime = `${Math.floor(diffSecs / 3600)}小时前`
        } else {
            relativeTime = `${Math.floor(diffSecs / 86400)}天前`
        }
        
        // Format absolute time
        const absoluteTime = date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        })
        
        timeEl.textContent = `${absoluteTime} (${relativeTime})`
        timeEl.title = `数据更新时间: ${date.toLocaleString('zh-CN')}`
        
        // Add visual indicator for stale data
        if (diffSecs > 300) { // 5 minutes
            timeEl.style.color = 'var(--accent-warning)'
        } else {
            timeEl.style.color = 'var(--text-muted)'
        }
    }
}

export function renderPingResults() {
    const grid = document.getElementById('pingResultsGrid')
    if (!grid) return

    const ips = Object.keys(pingResults)

    if (ips.length === 0) {
        grid.innerHTML = `
            <div class="ping-empty">
                <div class="ping-empty-icon">📡</div>
                <div class="ping-empty-text">等待Ping数据</div>
                <div class="ping-empty-hint">Ping监控将显示各目标IP的网络连通性</div>
            </div>
        `
        return
    }

    let html = ''
    ips.forEach(ip => {
        const result = pingResults[ip]
        const statusIcon = getStatusIcon(result.status)
        const statusClass = getStatusClass(result.status)
        const statusText = getStatusText(result.status)

        html += `
            <div class="ping-result-card">
                <div class="ping-result-header">
                    <span class="ping-result-ip">${ip}</span>
                    <span class="ping-result-status ${statusClass}">${statusIcon} ${statusText}</span>
                </div>
                <div class="ping-result-details">
                    <div class="ping-result-detail">
                        <span class="ping-detail-label">平均延迟</span>
                        <span class="ping-detail-value">${result.avg_time.toFixed(2)} ms</span>
                    </div>
                    <div class="ping-result-detail">
                        <span class="ping-detail-label">最小/最大</span>
                        <span class="ping-detail-value">${result.min_time.toFixed(2)} / ${result.max_time.toFixed(2)} ms</span>
                    </div>
                    <div class="ping-result-detail">
                        <span class="ping-detail-label">丢包率</span>
                        <span class="ping-detail-value">${result.packet_loss.toFixed(1)}%</span>
                    </div>
                    <div class="ping-result-detail">
                        <span class="ping-detail-label">收发</span>
                        <span class="ping-detail-value">${result.packets_received} / ${result.packets_sent}</span>
                    </div>
                </div>
            </div>
        `
    })

    grid.innerHTML = html
}

export function getStatusIcon(status) {
    switch(status) {
        case 1: return '✅'
        case 2: return '❌'
        case 3: return '⏱️'
        default: return '❓'
    }
}

export function getStatusClass(status) {
    switch(status) {
        case 1: return 'status-reachable'
        case 2: return 'status-unreachable'
        case 3: return 'status-timeout'
        default: return 'status-unknown'
    }
}

export function getStatusText(status) {
    switch(status) {
        case 1: return '可达'
        case 2: return '不可达'
        case 3: return '超时'
        default: return '未知'
    }
}

export function togglePingAutoRefresh() {
    isPingAutoRefreshEnabled = !isPingAutoRefreshEnabled
    
    const btn = document.getElementById('pingAutoRefreshBtn')
    if (btn) {
        btn.textContent = isPingAutoRefreshEnabled ? '⏸️ 暂停刷新' : '▶️ 自动刷新'
    }
    
    showToast(isPingAutoRefreshEnabled ? 'Ping自动刷新已开启' : 'Ping自动刷新已暂停', 'info')
}

// ============================================
// Expose functions to window for inline event handlers
// ============================================

window.selectDevice = selectDevice
window.disconnectDevice = disconnectDevice
window.openDeviceEditModal = openDeviceEditModal
window.closeDeviceEditModal = closeDeviceEditModal
window.saveDeviceEdit = saveDeviceEdit
window.filterDevices = filterDevices
window.onSearchKeyDown = onSearchKeyDown
window.goToPage = goToPage
window.prevPage = prevPage
window.nextPage = nextPage
window.refreshFileTree = refreshFileTree
window.collapseAllFolders = collapseAllFolders
window.downloadSelectedFiles = downloadSelectedFiles
window.showNewFileDialog = () => { showToast('新建文件功能待实现', 'info') }
window.createNewFile = () => { showToast('新建文件功能待实现', 'info') }
window.closeNewFileDialog = () => { document.getElementById('newFileDialog').style.display = 'none' }
window.toggleTreeItem = toggleTreeItem
window.handleTreeItemClick = handleTreeItemClick
window.previewFile = previewFile
window.closePreview = closePreview
window.toggleEditor = toggleEditor
window.saveFileToDevice = saveFileToDevice
window.cancelEdit = cancelEdit
window.switchToTab = switchToTab
window.closeEditorTab = closeEditorTab
window.showKeyboardShortcuts = () => { document.getElementById('keyboardShortcutsModal').style.display = 'flex' }
window.closeKeyboardShortcuts = () => { document.getElementById('keyboardShortcutsModal').style.display = 'none' }
window.switchTab = switchTab
window.rebootDevice = rebootDevice
window.showSettings = showSettings
window.closeSettings = closeSettings
window.saveSettings = saveSettings
window.resetSettings = () => { showToast('恢复默认设置', 'info') }
window.runScript = runScript
window.closeModal = closeModal
window.copyOutput = copyOutput
window.refreshSystemStatusThrottled = refreshSystemStatusThrottled
window.toggleMonitorAutoRefresh = toggleMonitorAutoRefresh
window.refreshPingStatusThrottled = refreshPingStatusThrottled
window.togglePingAutoRefresh = togglePingAutoRefresh
window.sortProcesses = sortProcesses
window.filterProcessList = filterProcessList
window.showView = showView
window.handleMessage = handleMessage
window.cancelFileSave = cancelFileSave
window.confirmFileSave = confirmFileSave

// Expose app state for websocket module
window.appState = {
    get currentDevice() { return currentDevice },
    get devices() { return devices },
    get paginationState() { return paginationState },
    get ptySessionId() { return ptySessionId }
}

window.handleAppMessage = handleMessage

// ============================================
// Device Management (Migrated from js/app.js)
// ============================================

export function updateDeviceList(newDevices) {
    devices = Array.isArray(newDevices) ? newDevices : []
    renderDeviceList()

    if (currentDevice) {
        const stillOnline = devices.some(d => d.device_id === currentDevice.device_id)
        if (!stillOnline) {
            showToast(`设备 ${currentDevice.device_id} 已离线`, 'warning')
            disconnectDevice()
        }
    }

    const settings = loadSettings()
    const autoSelect = settings.autoSelectDevice !== false
    if (autoSelect && devices.length > 0 && !currentDevice && isConnected) {
        setTimeout(() => selectDevice(devices[0].device_id), 100)
    }
}

export function renderDeviceList() {
    const list = safeGetElement('deviceList')
    if (!list) {
        console.warn('deviceList element not found, cannot render')
        return
    }

    const searchInput = safeGetElement('deviceSearch')
    const search = searchInput ? searchInput.value.toLowerCase() : ''

    const filtered = devices.filter(d =>
        d.device_id.toLowerCase().includes(search)
    )

    if (filtered.length === 0) {
        list.innerHTML = `
            <div style="padding: 40px; text-align: center; color: var(--text-muted);">
                <div style="font-size: 48px; margin-bottom: 16px;">📡</div>
                <div>暂无设备</div>
            </div>
        `
        return
    }

    list.innerHTML = filtered.map(device => `
        <div class="device-card ${currentDevice?.device_id === device.device_id ? 'active' : ''}"
             onclick="selectDevice('${device.device_id}')">
            <div class="device-card-header">
                <div class="device-avatar">📱</div>
                <div class="device-info">
                    <h4>${device.name || device.device_id}</h4>
                    <div class="device-status">在线</div>
                </div>
                <button class="btn btn-icon" onclick="event.stopPropagation(); openDeviceEditModal('${device.device_id}')" title="编辑设备">✏️</button>
            </div>
            <div class="device-metrics">
                <div class="device-metric">
                    <div class="device-metric-value">${device.cpu_usage?.toFixed(0) || '--'}%</div>
                    <div class="device-metric-label">CPU</div>
                </div>
                <div class="device-metric">
                    <div class="device-metric-value">${((device.mem_used || 0) / 1024).toFixed(1)}G</div>
                    <div class="device-metric-label">内存</div>
                </div>
                <div class="device-metric">
                    <div class="device-metric-value">${device.load_1min?.toFixed(1) || '--'}</div>
                    <div class="device-metric-label">负载</div>
                </div>
            </div>
            ${device.tags && device.tags.length > 0 ? `
                <div class="device-tags" style="margin-top: 8px; display: flex; gap: 4px; flex-wrap: wrap;">
                    ${device.tags.map(tag => `<span class="device-tag" style="font-size: 11px; padding: 2px 6px; background: var(--bg-tertiary); border-radius: 4px; color: var(--text-muted);">${tag}</span>`).join('')}
                </div>
            ` : ''}
        </div>
    `).join('')
}

export function filterDevices() {
    const searchInput = safeGetElement('deviceSearch')
    if (searchInput) {
        queryDeviceList({
            page: 0,
            page_size: paginationState.pageSize,
            search_keyword: searchInput.value.trim()
        })
    }
}

export function onSearchKeyDown(event) {
    if (event.key === 'Enter') {
        filterDevices()
    }
}

export function openDeviceEditModal(deviceId) {
    const device = devices.find(d => d.device_id === deviceId)
    if (!device) {
        showToast('设备不存在', 'error')
        return
    }

    document.getElementById('editDeviceId').value = deviceId
    document.getElementById('editDeviceIdDisplay').value = deviceId
    document.getElementById('editDeviceName').value = device.name || ''
    document.getElementById('editDeviceTags').value = (device.tags || []).join(', ')

    const modal = document.getElementById('deviceEditModal')
    modal.style.display = 'flex'
}

export function closeDeviceEditModal() {
    const modal = document.getElementById('deviceEditModal')
    modal.style.display = 'none'
}

export function saveDeviceEdit() {
    const deviceId = document.getElementById('editDeviceId').value
    const name = document.getElementById('editDeviceName').value.trim()
    const tagsStr = document.getElementById('editDeviceTags').value.trim()
    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : []

    if (!deviceId) {
        showToast('设备ID不能为空', 'error')
        return
    }

    sendMessage(0x52, {  // DEVICE_UPDATE
        device_id: deviceId,
        name: name || null,
        tags: tags.length > 0 ? tags : null
    })

    closeDeviceEditModal()
}

export function queryDeviceList(params = {}) {
    const { page = 0, page_size = 20, search_keyword = '' } = params

    if (paginationState.debounceTimer) {
        clearTimeout(paginationState.debounceTimer)
    }

    paginationState.debounceTimer = setTimeout(() => {
        paginationState.currentPage = page
        paginationState.pageSize = page_size
        paginationState.searchKeyword = search_keyword
        paginationState.isLoading = true

        renderPaginationUI()

        try {
            sendMessage(MSG_TYPES.DEVICE_LIST, {
                action: "get_list",
                page: page,
                page_size: page_size,
                search_keyword: search_keyword,
                sort_by: "device_id",
                sort_order: "asc"
            })
        } catch (error) {
            console.error('查询设备列表失败:', error)
            paginationState.isLoading = false
            renderPaginationUI()
        }
    }, 300)
}

export function renderPaginationUI() {
    const deviceListEl = safeGetElement('deviceList')
    if (!deviceListEl) return

    const totalPages = Math.ceil(paginationState.totalCount / paginationState.pageSize)
    const currentPage = paginationState.currentPage

    if (totalPages <= 1) return

    const pages = generatePageNumbers(currentPage, totalPages)

    const paginationHTML = `
        <div class="pagination">
            <div class="pagination-controls">
                <button class="pagination-btn" onclick="prevPage()" ${currentPage === 0 ? 'disabled' : ''}>◀</button>
                ${pages.map(page => {
                    if (page === '...') {
                        return '<span class="pagination-ellipsis">...</span>'
                    }
                    return `<button class="pagination-page ${page === currentPage ? 'active' : ''}"
                                     onclick="goToPage(${page})">${page + 1}</button>`
                }).join('')}
                <button class="pagination-btn" onclick="nextPage()" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>▶</button>
            </div>
            <div class="pagination-info">
                共 ${paginationState.totalCount} 条 · 第 ${currentPage + 1}/${totalPages} 页
            </div>
        </div>
    `

    const existingPagination = deviceListEl.querySelector('.pagination')
    if (existingPagination) {
        existingPagination.outerHTML = paginationHTML
    } else {
        deviceListEl.innerHTML += paginationHTML
    }
}

function generatePageNumbers(currentPage, totalPages) {
    const pages = []
    const maxVisible = 5

    if (totalPages <= maxVisible) {
        for (let i = 0; i < totalPages; i++) {
            pages.push(i)
        }
    } else {
        pages.push(0)

        let start = Math.max(1, currentPage - 1)
        let end = Math.min(totalPages - 2, currentPage + 1)

        if (currentPage < 3) {
            start = 1
            end = 3
        }

        if (currentPage > totalPages - 4) {
            start = totalPages - 4
            end = totalPages - 2
        }

        if (start > 1) {
            pages.push('...')
        }

        for (let i = start; i <= end; i++) {
            pages.push(i)
        }

        if (end < totalPages - 2) {
            pages.push('...')
        }

        pages.push(totalPages - 1)
    }

    return pages
}

export function goToPage(page) {
    queryDeviceList({
        page: page,
        page_size: paginationState.pageSize,
        search_keyword: paginationState.searchKeyword
    })
}

export function prevPage() {
    if (paginationState.currentPage > 0) {
        queryDeviceList({
            page: paginationState.currentPage - 1,
            page_size: paginationState.pageSize,
            search_keyword: paginationState.searchKeyword
        })
    }
}

export function nextPage() {
    const totalPages = Math.ceil(paginationState.totalCount / paginationState.pageSize)
    if (paginationState.currentPage < totalPages - 1) {
        queryDeviceList({
            page: paginationState.currentPage + 1,
            page_size: paginationState.pageSize,
            search_keyword: paginationState.searchKeyword
        })
    }
}

export function selectDevice(deviceId) {
    const device = devices.find(d => d.device_id === deviceId)
    if (!device) return

    if (!isConnected || isReconnecting) {
        showToast('等待WebSocket连接...', 'warning')
        setTimeout(() => selectDevice(deviceId), 1000)
        return
    }
    if (currentDevice && ptySessionId) {
        sendMessage(MSG_TYPES.PTY_CLOSE, { session_id: ptySessionId })
        ptySessionId = null
    }

    currentDevice = device

    document.querySelectorAll('.device-card').forEach(el => el.classList.remove('active'))
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active')
    }

    document.getElementById('emptyState').style.display = 'none'
    document.getElementById('deviceDetail').classList.add('active')
    document.getElementById('detailDeviceName').textContent = device.device_id
    document.getElementById('detailDeviceIp').textContent = device.ip_addr || 'IP未知'

    setTimeout(() => {
        if (window.connectTerminal) window.connectTerminal()
    }, 100)

    setTimeout(() => {
        refreshFiles()
        refreshFileTree()
    }, 200)

    setTimeout(() => refreshSystemStatus(), 300)

    startMonitorAutoRefresh()

    showToast(`已选择设备: ${deviceId}`, 'success')
}

export function disconnectDevice() {
    stopMonitorAutoRefresh()

    if (ptySessionId) {
        sendMessage(MSG_TYPES.PTY_CLOSE, { session_id: ptySessionId })
        ptySessionId = null
    }
    currentDevice = null
    document.getElementById('deviceDetail').classList.remove('active')
    document.getElementById('emptyState').style.display = 'flex'
    if (window.clearTerminal) window.clearTerminal()
}

// ============================================
// File Management (Migrated from js/app.js)
// ============================================

export function refreshFileTree() {
    if (!currentDevice) return
    const container = safeGetElement('fileTreeRoot')
    if (!container) {
        console.warn('fileTreeRoot element not found, cannot refresh')
        return
    }
    expandedDirs.clear()
    expandedDirs.add('/')
    loadTreeItem('/', container)
}

export function loadTreeItem(path, container) {
    if (container) {
        container.innerHTML = '<div class="tree-loading">加载中...</div>'
    } else {
        console.warn('Invalid container for tree item, path:', path)
        return
    }

    sendMessage(MSG_TYPES.FILE_LIST_REQUEST, {
        path: path,
        request_id: 'tree-' + Date.now()
    })
}

export function renderTreeItem(item, parentPath, index) {
    const fullPath = parentPath === '/' ? '/' + item.name : parentPath + '/' + item.name
    const isExpanded = expandedDirs.has(fullPath)
    const isDir = item.is_dir

    const div = document.createElement('div')
    const isSelected = selectedFiles.has(fullPath)
    div.className = `tree-item ${isExpanded && isDir ? 'expanded' : ''} ${isSelected ? 'selected' : ''}`
    div.dataset.path = fullPath
    div.dataset.isDir = isDir
    div.dataset.index = index

    const toggleHtml = isDir ?
        `<span class="tree-toggle">▶</span>` :
        `<span class="tree-toggle empty"></span>`

    const iconHtml = isDir ?
        (isExpanded ? '📂' : '📁') :
        getFileIcon(item.name)

    div.innerHTML = `
        ${toggleHtml}
        <span class="tree-icon">${iconHtml}</span>
        <span class="tree-label">${item.name}</span>
    `

    if (isDir) {
        const toggle = div.querySelector('.tree-toggle')
        toggle.addEventListener('click', (e) => {
            e.stopPropagation()
            toggleTreeItem(fullPath, div)
        })
    }

    div.addEventListener('click', (e) => {
        handleTreeItemClick(e, fullPath, isDir, item, div)
    })

    return div
}

export function handleTreeItemClick(e, fullPath, isDir, item, div) {
    document.querySelectorAll('.tree-item.focused').forEach(el => el.classList.remove('focused'))
    div.classList.add('focused')

    if (isDir) {
        const isExpanded = expandedDirs.has(fullPath)
        navigateTo(fullPath)
        toggleTreeItem(fullPath, div)
        if (!e.ctrlKey && !e.shiftKey) {
            clearFileSelection()
        }
    } else {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault()
            toggleFileSelection(fullPath, div)
        } else if (e.shiftKey && lastSelectedFile) {
            e.preventDefault()
            selectFileRange(lastSelectedFile, fullPath)
        } else {
            clearFileSelection()
            addFileToSelection(fullPath, div)
            selectFileInTree(fullPath, item)
        }
        lastSelectedFile = fullPath
    }

    updateSelectionInfo()
}

export function toggleFileSelection(path, element) {
    if (selectedFiles.has(path)) {
        selectedFiles.delete(path)
        element.classList.remove('selected')
    } else {
        selectedFiles.add(path)
        element.classList.add('selected')
    }
}

export function addFileToSelection(path, element) {
    selectedFiles.add(path)
    element.classList.add('selected')
}

export function clearFileSelection() {
    selectedFiles.clear()
    document.querySelectorAll('.tree-item.selected').forEach(el => el.classList.remove('selected'))
    lastSelectedFile = null
}

export function selectFileRange(startPath, endPath) {
    const visibleItems = []
    document.querySelectorAll('.tree-item[data-is-dir="false"]').forEach(el => {
        visibleItems.push({
            path: el.dataset.path,
            element: el
        })
    })

    const startIndex = visibleItems.findIndex(i => i.path === startPath)
    const endIndex = visibleItems.findIndex(i => i.path === endPath)

    if (startIndex === -1 || endIndex === -1) return

    const minIndex = Math.min(startIndex, endIndex)
    const maxIndex = Math.max(startIndex, endIndex)

    for (let i = minIndex; i <= maxIndex; i++) {
        const item = visibleItems[i]
        addFileToSelection(item.path, item.element)
    }
}

export function updateSelectionInfo() {
    const infoEl = document.getElementById('fileSelectionInfo')
    const countEl = document.getElementById('selectionCount')

    if (selectedFiles.size > 0) {
        infoEl.style.display = 'block'
        countEl.textContent = selectedFiles.size
    } else {
        infoEl.style.display = 'none'
    }
}

export function collapseAllFolders() {
    expandedDirs.clear()
    expandedDirs.add('/')

    document.querySelectorAll('.tree-item.expanded').forEach(el => {
        el.classList.remove('expanded')
        const icon = el.querySelector('.tree-icon')
        if (icon && el.dataset.isDir === 'true') {
            icon.textContent = '📁'
        }
    })

    document.querySelectorAll('.tree-children').forEach(el => {
        el.style.display = 'none'
    })

    showToast('已折叠所有文件夹', 'info')
}

export function downloadSelectedFiles() {
    if (selectedFiles.size === 0) {
        showToast('请先选择要下载的文件', 'warning')
        return
    }

    const files = Array.from(selectedFiles)

    if (files.length === 1) {
        sendDownloadRequest(files[0])
    } else {
        showToast(`正在打包 ${files.length} 个文件...`, 'info')
        sendMessage(MSG_TYPES.DOWNLOAD_PACKAGE, {
            paths: files,
            format: 'tar'
        })
    }
}

export function toggleTreeItem(path, element) {
    const isExpanded = expandedDirs.has(path)

    if (isExpanded) {
        expandedDirs.delete(path)
        const pathPrefix = path === '/' ? '/' : path + '/'
        expandedDirs.forEach(subPath => {
            if (subPath.startsWith(pathPrefix)) {
                expandedDirs.delete(subPath)
            }
        })
        element.classList.remove('expanded')
        const childrenContainer = element.nextElementSibling
        if (childrenContainer && childrenContainer.classList.contains('tree-children')) {
            childrenContainer.style.display = 'none'
        }
    } else {
        expandedDirs.add(path)
        element.classList.add('expanded')
        let childrenContainer = element.nextElementSibling
        if (!childrenContainer || !childrenContainer.classList.contains('tree-children')) {
            childrenContainer = document.createElement('div')
            childrenContainer.className = 'tree-children'
            element.parentNode.insertBefore(childrenContainer, element.nextSibling)
            loadTreeItem(path, childrenContainer)
        } else {
            childrenContainer.style.display = 'block'
        }
    }

    const icon = element.querySelector('.tree-icon')
    if (icon) {
        icon.textContent = isExpanded ? '📁' : '📂'
    }

}

export function updateTreeWithFiles(path, files) {

    let container
    if (path === '/') {
        container = safeGetElement('fileTreeRoot')
    } else {
        const parentItem = document.querySelector(`.tree-item[data-path="${path}"]`)
        if (parentItem) {
            container = parentItem.nextElementSibling
            if (!container || !container.classList.contains('tree-children')) {
                container = document.createElement('div')
                container.className = 'tree-children'
                parentItem.parentNode?.insertBefore(container, parentItem.nextSibling)
            }
        }
    }

    if (!container) {
        console.error('[TREE] Container not found for path:', path)
        return
    }


    files.sort((a, b) => {
        if (a.is_dir && !b.is_dir) return -1
        if (!a.is_dir && b.is_dir) return 1
        return a.name.localeCompare(b.name)
    })

    container.innerHTML = ''

    if (files.length === 0) {
        const emptyMsg = document.createElement('div')
        emptyMsg.className = 'tree-empty'
        emptyMsg.style.padding = '8px 12px'
        emptyMsg.style.color = 'var(--text-muted)'
        emptyMsg.style.fontSize = '12px'
        emptyMsg.textContent = '(空)'
        container.appendChild(emptyMsg)
        return
    }

    let dirCount = 0
    let fileCount = 0

    files.forEach((item, index) => {
        const treeItem = renderTreeItem(item, path, index)
        container.appendChild(treeItem)
        if (item.is_dir) {
            dirCount++
        } else {
            fileCount++
        }
    })

}

export function refreshCurrentDir() {
    if (!currentDevice) return
    refreshFiles(currentPath)
}

export function refreshFiles(path) {
    if (!currentDevice) return
    sendMessage(MSG_TYPES.FILE_LIST_REQUEST, {
        path: path,
        request_id: 'files-' + Date.now()
    })
}

export function updateFileList(files) {
    return
}

export function selectFileItem(path, isDir, name, size) {
    clearFileSelection()
    selectedFiles.add(path)
    event.currentTarget.classList.add('selected')
    updateSelectionInfo()

    if (!isDir) {
        previewFile(path, name, size)
    }
}

export function selectFileInTree(path, item) {
    previewFile(path, item.name, item.size)
}

export function previewFile(path, name, size) {

    if (isEditorActive && isEditorDirty()) {
        if (!confirm('当前文件已修改但未保存，确定切换？')) return
    }
    if (isEditorActive) exitEditor()

    editorCurrentFile = { path, name, size, mtime: 0 }

    const preview = safeGetElement('filePreview')
    const placeholder = safeGetElement('filePreviewPlaceholder')
    const previewName = safeGetElement('previewFilename')
    const previewSize = safeGetElement('previewFilesize')

    if (placeholder) placeholder.style.display = 'none'
    if (preview) preview.style.display = 'flex'
    const previewPanel = document.getElementById('filePreviewPanel')
    if (previewPanel) previewPanel.style.display = 'flex'

    if (previewName) previewName.textContent = name
    if (previewSize) previewSize.textContent = formatBytes(size)

    const ext = name.split('.').pop().toLowerCase()

    if (aceEditor && aceEditorReady) {
        aceSession.off("change", handleEditorChange)
        aceEditor.setValue('', -1)
        aceSession.on("change", handleEditorChange)
        aceEditor.setReadOnly(true)

        if (IMAGE_EXTS.includes(ext)) {
            aceSession.off("change", handleEditorChange)
            aceEditor.setValue(`[图片文件 - ${formatBytes(size)}]\n\n请点击下载按钮查看图片`, -1)
            aceSession.on("change", handleEditorChange)
            pendingFilePreview = { path, name, ext, size }
            sendMessage(MSG_TYPES.FILE_REQUEST, {
                action: 'download',
                filepath: path,
                request_id: 'preview-img-' + Date.now()
            })

            const btnEdit = document.getElementById('btnEditFile')
            if (btnEdit) btnEdit.style.display = 'none'
        } else {
            const readLength = Math.min(size, 32768)
            aceSession.off("change", handleEditorChange)
            aceEditor.setValue('加载中...', -1)
            aceSession.on("change", handleEditorChange)
            pendingFilePreview = { path, name, ext, size }

            sendMessage(MSG_TYPES.FILE_REQUEST, {
                action: 'read',
                filepath: path,
                offset: 0,
                length: readLength,
                request_id: 'read-' + Date.now()
            })

            const btnEdit = document.getElementById('btnEditFile')
            if (btnEdit) btnEdit.style.display = 'none'

            setTimeout(() => {
                if (pendingFilePreview && pendingFilePreview.path === path) {
                    if (aceEditor.getValue() === '加载中...') {
                        aceSession.off("change", handleEditorChange)
                        aceEditor.setValue('加载超时，请重试', -1)
                        aceSession.on("change", handleEditorChange)
                    }
                    pendingFilePreview = null
                }
            }, 10000)
        }
    } else {
        setTimeout(() => previewFile(path, name, size), 100)
    }
}

export function handleFileData(data) {

    if (pendingFileSave && data.filepath && data.filepath === pendingFileSave.path) {
        if (data.success) {
            if (editorCurrentFile) {
                editorCurrentFile.mtime = data.mtime || 0
            }
            onFileSaveSuccess()
        } else if (data.error) {
            onFileSaveError(data.error)
        }
        return
    }

    if (!pendingFilePreview) {
        console.warn('[FILE_DATA] No pending file preview')
        return
    }

    const { path, name, ext, size } = pendingFilePreview

    if (data.filepath && data.filepath !== path) {
        console.warn(`[FILE_DATA] File path mismatch: expected ${path}, got ${data.filepath}`)
        return
    }

    if (data.error) {
        console.error('[FILE_DATA] Error:', data.error)
        aceEditor.setValue(`错误: ${data.error}`, -1)
        pendingFilePreview = null
        return
    }

    let content = ''
    let bytes = null

    if (data.content) {
        const binaryString = atob(data.content)
        bytes = new Uint8Array(binaryString.length)
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
        }
    } else if (data.chunk_data) {
        const binaryString = atob(data.chunk_data)
        bytes = new Uint8Array(binaryString.length)
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
        }
    }

    if (bytes && isBinaryFile(bytes)) {
        const binaryExt = name.split('.').pop().toLowerCase()

        if (BINARY_EXTS.includes(binaryExt)) {
            content = `[二进制文件 - ${binaryExt.toUpperCase()}]\n\n文件大小: ${formatBytes(size)}\n\n此文件不支持在线编辑，请下载后查看`
        } else {
            content = `[二进制文件]\n\n文件大小: ${formatBytes(size)}\n\n此文件不支持在线编辑，请下载后查看`
        }
    } else if (bytes) {
        content = new TextDecoder('utf-8', { fatal: false }).decode(bytes)
    } else {
        aceEditor.setValue('文件内容为空', -1)
        pendingFilePreview = null
        return
    }

    const editable = isFileEditable(name, content)

    editorLastSavedContent = content
    if (editorCurrentFile) {
        editorCurrentFile.mtime = data.mtime || 0
        editorCurrentFile.editable = editable
    }

    displayEditorContent(content, true)

    resetEditorState()

    const btnEdit = document.getElementById('btnEditFile')
    if (btnEdit) {
        btnEdit.style.display = editable ? 'inline-flex' : 'none'
        if (!editable) {
            btnEdit.title = '此文件类型不支持编辑'
        } else {
            btnEdit.title = '编辑文件'
        }
    }

    pendingFilePreview = null
}

export function closePreview() {
    const previewPanel = document.getElementById('filePreviewPanel')
    const placeholder = document.getElementById('filePreviewPlaceholder')
    const preview = document.getElementById('filePreview')

    if (placeholder) placeholder.style.display = 'flex'
    if (preview) preview.style.display = 'none'
    if (previewPanel) previewPanel.style.display = 'none'

    exitEditor()
}

export function navigateTo(path) {
    currentPath = path
    
    clearFileSelection()
    updateSelectionInfo()

    refreshFiles(path)

    document.querySelectorAll('.tree-item').forEach(el => {
        el.classList.remove('selected')
        if (el.dataset.path === path && el.dataset.isDir === 'true') {
            el.classList.add('selected')
        }
    })
}

export function sendDownloadRequest(path) {
    sendMessage(MSG_TYPES.DOWNLOAD_PACKAGE, {
        path: path,
        format: 'tar'
    })
    showToast('开始下载...', 'info')
}

export function handleDownloadPackage(data) {

    if (data.chunk_index !== undefined && data.total_chunks !== undefined) {
        handleChunkedDownload(data)
        return
    }

    if (!data.filename || !data.content || !data.size) {
        console.error('Download package data missing required fields:', data)
        showToast('下载包数据不完整', 'error')
        return
    }

    try {
        downloadFile(data.filename, data.content)
    } catch (error) {
        console.error('Error downloading file:', error)
        showToast('下载失败: ' + error.message, 'error')
    }
}

function handleChunkedDownload(data) {
    const request_id = data.request_id || 'default'
    const chunk_index = data.chunk_index
    const total_chunks = data.total_chunks

    if (!downloadChunks[request_id]) {
        downloadChunks[request_id] = {
            chunks: new Array(total_chunks).fill(null),
            total: total_chunks,
            filename: data.filename,
            size: data.size
        }
    }

    const chunkData = downloadChunks[request_id]
    chunkData.chunks[chunk_index] = data.content


    const isComplete = chunkData.chunks.every(c => c !== null && c !== undefined)

    if (isComplete || data.is_last) {
        const fullContent = chunkData.chunks.join('')

        try {
            downloadFile(chunkData.filename, fullContent)
            showToast(`文件已下载: ${chunkData.filename}`, 'success')
        } catch (error) {
            console.error('Error downloading file:', error)
            showToast('下载失败: ' + error.message, 'error')
        }

        delete downloadChunks[request_id]
    } else {
        const remaining = chunkData.chunks.filter(c => c === undefined || c === null).length
    }
}

function downloadFile(filename, content) {
    const binaryData = atob(content)
    const bytes = new Uint8Array(binaryData.length)
    for (let i = 0; i < binaryData.length; i++) {
        bytes[i] = binaryData.charCodeAt(i)
    }

    const blob = new Blob([bytes], { type: 'application/gzip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}

// ============================================
// Export state variables
// ============================================

export {
    devices, currentDevice, currentTab, currentPath, paginationState,
    fileTreeData, selectedFiles, lastSelectedFile, expandedDirs, allTreeItems,
    pendingFilePreview, pendingFileSave, fileListChunks,
    isEditorActive, editorCurrentFile, editorWordWrap, editorLastSavedContent,
    syntaxHighlightEnabled, aceEditor, aceSession, aceEditorReady,
    openEditorTabs, activeEditorTabPath,
    cachedProcesses, processSortKey, processSortAsc, processMemTotal,
    monitorRefreshInterval, isMonitorAutoRefreshEnabled, downloadChunks,
    pingTargets, pingResults, isPingAutoRefreshEnabled, pingRefreshInterval,
    lastSystemRefreshTime, lastPingRefreshTime, REFRESH_COOLDOWN_MS,
    isManualSystemRefresh, isManualPingRefresh,
    previousSystemStatus, previousPingResults
}

// ============================================
// WebSocket state (re-exported from websocket.js)
// ============================================

export { ws, isConnected, isReconnecting, reconnectAttempts, maxReconnectAttempts } from './websocket.js'




