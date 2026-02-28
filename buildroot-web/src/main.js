// ============================================
// Main Entry Point - Vite + ES Modules
// ============================================

// Import xterm.js and addons
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { SearchAddon } from '@xterm/addon-search'
import { WebLinksAddon } from '@xterm/addon-web-links'

// Import xterm.css
import '@xterm/xterm/css/xterm.css'

// Import Ace Editor
import ace from 'ace-builds'
import 'ace-builds/src-noconflict/mode-text'
import 'ace-builds/src-noconflict/theme-monokai'
import 'ace-builds/src-noconflict/ext-language_tools'
import 'ace-builds/src-noconflict/ext-modelist'

// Import modules
import { MSG_TYPES, MONITOR_REFRESH_INTERVAL, STATE_LABELS, FILE_ICONS, IMAGE_EXTS, BINARY_EXTS, BINARY_TYPE_LABELS } from './config.js'
import { showToast, formatBytes, formatUptime, getFileIcon, getFileTypeLabel, getAceLanguageMode, isFileEditable, isBinaryFile, safeGetElement, debugFileListChunks, navigateTo, collapseAllFolders, sendDownloadRequest } from './utils.js'
import { ws, isConnected, isReconnecting, connectWebSocket, sendMessage, reconnectWebSocket, getWsUrl, updateConnectionStatus } from './websocket.js'
import { 
    term, fitAddon, searchAddon, webLinksAddon, terminalInitialized, ptySessionId,
    initTerminal, connectTerminal, handleTerminalData, handlePtyCreateResponse, handlePtyClose,
    appendTerminalOutput, clearTerminal, reconnectTerminal, updateTerminalStatus,
    terminalSearchToggle, terminalSearchNext, terminalSearchPrev, handleTerminalSearchKey
} from './terminal.js'

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

// Export necessary variables and functions for other modules
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
    previousSystemStatus, previousPingResults,
    updateDeviceList, selectDevice, disconnectDevice,
    refreshFileTree, loadTreeItem, renderTreeItem, handleTreeItemClick,
    toggleFileSelection, addFileToSelection, clearFileSelection, selectFileRange,
    updateSelectionInfo, collapseAllFolders, downloadSelectedFiles,
    toggleTreeItem, updateTreeWithFiles, refreshCurrentDir, refreshFiles,
    updateFileList, selectFileItem, selectFileInTree, previewFile, handleFileData,
    closePreview, navigateTo, sendDownloadRequest,
    initAceEditor, displayEditorContent, toggleEditor, enterEditor, renderEditorTabs,
    switchToTab, closeEditorTab, exitEditor, cancelEdit, isEditorDirty, markEditorAsClean,
    resetEditorState, handleEditorChange, updateAceCursorInfo, saveFileToDevice,
    onFileSaveSuccess, onFileSaveError, showFileConflictDialog, cancelFileSave, confirmFileSave,
    updateSystemStatus, updateProcessList, renderProcessList, sortProcesses, filterProcessList,
    startMonitorAutoRefresh, stopMonitorAutoRefresh, toggleMonitorAutoRefresh,
    refreshSystemStatus, refreshSystemStatusThrottled, refreshPingStatus, refreshPingStatusThrottled,
    handleCommandResponse, runScript, handleScriptResult, closeModal, copyOutput,
    showView, switchTab, rebootDevice, showSettings, closeSettings,
    loadSettingsToForm, saveSettings, handleMessage,
    handlePingStatus, updatePingStatusTime, renderPingResults,
    getStatusIcon, getStatusClass, getStatusText, togglePingAutoRefresh
}

// Import the app module which will use these exports
import './app.js'

// ============================================
// Clean up expired chunk data periodically
// ============================================

setInterval(() => {
    const now = Date.now()
    const maxAge = 60000
    let cleaned = false
    for (const [request_id, chunkData] of Object.entries(fileListChunks)) {
        if (!chunkData.timestamp || (now - chunkData.timestamp > maxAge)) {
            console.warn(`[FILE_LIST] Cleaning up expired chunk data for request ${request_id} (received ${chunkData.receivedChunks}/${chunkData.totalChunks} chunks)`)
            delete fileListChunks[request_id]
            cleaned = true
        }
    }
    if (cleaned) {
        debugFileListChunks()
    }
}, 15000)

// ============================================
// Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('[App] DOM Content Loaded')
    
    // Initialize Ace Editor
    initAceEditor()
    
    // Connect WebSocket
    connectWebSocket()
    
    // Setup file drag and drop
    const filesTab = document.getElementById('tab-files')
    if (filesTab) {
        filesTab.addEventListener('dragover', (e) => {
            e.preventDefault()
            e.stopPropagation()
            filesTab.style.outline = '2px dashed var(--accent-primary)'
            filesTab.style.outlineOffset = '-4px'
        })
        filesTab.addEventListener('dragleave', (e) => {
            e.preventDefault()
            e.stopPropagation()
            filesTab.style.outline = 'none'
        })
    }
    
    // Setup keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault()
            const searchInput = document.getElementById('deviceSearch')
            if (searchInput) searchInput.focus()
        }
        if (e.key === 'Escape') {
            closeModal()
            closeSettings()
        }
    })
})

window.addEventListener('error', (event) => {
    console.error('Global error:', event.error)
    showToast(`发生未预期的错误: ${event.error?.message || '未知错误'}`, 'error')
    event.preventDefault()
    return false
})

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason)
    showToast(`未处理的Promise错误: ${event.reason?.message || event.reason || '未知错误'}`, 'error')
    event.preventDefault()
    return false
})
