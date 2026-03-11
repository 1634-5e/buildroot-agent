// ============================================
// Main Entry Point - Vite + ES Modules
// ============================================

// Import Mock API (开发环境启用)
import { startMockAPI } from './mocks/browser.js'

// 启动 Mock API（如果配置了 VITE_USE_MOCK=true）
startMockAPI().catch(console.error)

// Import xterm.js, addons and CSS
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { FitAddon } from '@xterm/addon-fit'
import { SearchAddon } from '@xterm/addon-search'
import { WebLinksAddon } from '@xterm/addon-web-links'

// Import Ace Editor
import ace from 'ace-builds'
import 'ace-builds/src-noconflict/mode-text'
import 'ace-builds/src-noconflict/theme-monokai'
import 'ace-builds/src-noconflict/ext-language_tools'
import 'ace-builds/src-noconflict/ext-modelist'

// Import modules
import { MSG_TYPES, MONITOR_REFRESH_INTERVAL, STATE_LABELS, FILE_ICONS, IMAGE_EXTS, BINARY_EXTS, BINARY_TYPE_LABELS } from './config.js'
import { showToast, formatBytes, formatUptime, getFileIcon, getFileTypeLabel, getAceLanguageMode, isFileEditable, isBinaryFile, safeGetElement, debugFileListChunks } from './utils.js'
import { ws, isConnected, isReconnecting, connectWebSocket, sendMessage, reconnectWebSocket, getWsUrl, updateConnectionStatus } from './websocket.js'
import { 
    term, fitAddon, searchAddon, webLinksAddon, terminalInitialized, ptySessionId,
    initTerminal, connectTerminal, handleTerminalData, handlePtyCreateResponse, handlePtyClose,
    appendTerminalOutput, clearTerminal, reconnectTerminal, updateTerminalStatus,
    terminalSearchToggle, terminalSearchNext, terminalSearchPrev, handleTerminalSearchKey
} from './terminal.js'

// ============================================
// Import state from app.js
// ============================================

import {
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
    getStatusIcon, getStatusClass, getStatusText, togglePingAutoRefresh,
    updateDeviceList, selectDevice, disconnectDevice,
    refreshFileTree, loadTreeItem, renderTreeItem, handleTreeItemClick,
    toggleFileSelection, addFileToSelection, clearFileSelection, selectFileRange,
    updateSelectionInfo, collapseAllFolders, downloadSelectedFiles,
    toggleTreeItem, updateTreeWithFiles, refreshCurrentDir, refreshFiles,
    updateFileList, selectFileItem, selectFileInTree, previewFile, handleFileData,
    closePreview, navigateTo, sendDownloadRequest,
    handleDownloadPackage, queryDeviceList, filterDevices, onSearchKeyDown,
    renderPaginationUI, goToPage, prevPage, nextPage,
    openDeviceEditModal, closeDeviceEditModal, saveDeviceEdit
} from './app.js'

// ============================================
// Export state for websocket module
// ============================================

export { ws, isConnected, isReconnecting, reconnectAttempts, maxReconnectAttempts } from './websocket.js'

// Import the app module which will use these exports
import './app.js'

// ============================================
// Clean up expired chunk data periodically
// ============================================

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
window.showKeyboardShortcuts = () => { document.getElementById('keyboardShortcutsModal').style.display = 'flex' }
window.closeKeyboardShortcuts = () => { document.getElementById('keyboardShortcutsModal').style.display = 'none' }
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
window.terminalSearchToggle = terminalSearchToggle
window.terminalSearchNext = terminalSearchNext
window.terminalSearchPrev = terminalSearchPrev
window.handleTerminalSearchKey = handleTerminalSearchKey
window.clearTerminal = clearTerminal
window.reconnectWebSocket = reconnectWebSocket
window.showView = showView
window.handleMessage = handleMessage
window.cancelFileSave = cancelFileSave
window.confirmFileSave = confirmFileSave
window.navigateTo = navigateTo
window.sendDownloadRequest = sendDownloadRequest
