import { create } from 'zustand';
import { toast } from 'sonner';
import type { Device, TabType, SystemStatus, FileItem, ProcessInfo, ScriptResult } from '../types';

interface AppState {
  // Connection state
  isConnected: boolean;
  ws: WebSocket | null;
  
  // Devices
  devices: Device[];
  currentDevice: Device | null;
  
  // UI state
  currentTab: TabType;
  searchQuery: string;
  
  // System status
  systemStatus: SystemStatus | null;
  processes: ProcessInfo[];
  
  // Files
  currentPath: string;
  fileList: FileItem[];
  fileTreeData: Record<string, FileItem[]>;
  selectedFiles: Set<string>;
  expandedDirs: Set<string>;
  previewFile: { name: string; content: string; size: number } | null;
  
  // Terminal
  terminalOutput: string;
  terminalPath: string;
  ptySessionId: number | null;
  
  // Scripts
  scriptEditorContent: string;
  scriptResult: ScriptResult | null;
  isScriptRunning: boolean;
  

  
  // Auto refresh
  monitorAutoRefresh: boolean;
  
  // Actions
  setConnected: (connected: boolean) => void;
  setWebSocket: (ws: WebSocket | null) => void;
  setDevices: (devices: Device[]) => void;
  setCurrentDevice: (device: Device | null) => void;
  setCurrentTab: (tab: TabType) => void;
  setSearchQuery: (query: string) => void;
  setSystemStatus: (status: SystemStatus | null) => void;
  setProcesses: (processes: ProcessInfo[]) => void;
  setCurrentPath: (path: string) => void;
  setFileList: (files: FileItem[]) => void;
  setFileTreeData: (path: string, files: FileItem[]) => void;
  toggleFileSelection: (path: string) => void;
  clearFileSelection: () => void;
  toggleExpandedDir: (path: string) => void;
  setPreviewFile: (file: { name: string; content: string; size: number } | null) => void;
  appendTerminalOutput: (text: string) => void;
  clearTerminal: () => void;
  setTerminalPath: (path: string) => void;
  setPtySessionId: (id: number | null) => void;
  setScriptEditorContent: (content: string) => void;
  setScriptResult: (result: ScriptResult | null) => void;
  setIsScriptRunning: (running: boolean) => void;
  addToast: (message: string, type?: 'success' | 'error' | 'warning' | 'info') => void;
  setMonitorAutoRefresh: (enabled: boolean) => void;
  sendMessage: (type: number, data: Record<string, unknown>) => boolean;
}

export const useStore = create<AppState>((set, get) => ({
  // Initial state
  isConnected: false,
  ws: null,
  devices: [],
  currentDevice: null,
  currentTab: 'terminal',
  searchQuery: '',
  systemStatus: null,
  processes: [],
  currentPath: '/root',
  fileList: [],
  fileTreeData: {},
  selectedFiles: new Set(),
  expandedDirs: new Set(['/']),
  previewFile: null,
  terminalOutput: '',
  terminalPath: '/root',
  ptySessionId: null,
  scriptEditorContent: "#!/bin/bash\n\n# 在此输入脚本代码\necho 'Hello, World!'\nuname -a",
  scriptResult: null,
  isScriptRunning: false,

  monitorAutoRefresh: true,

  // Actions
  setConnected: (connected) => set({ isConnected: connected }),
  setWebSocket: (ws) => set({ ws }),
  setDevices: (devices) => set({ devices }),
  setCurrentDevice: (device) => set({ currentDevice: device }),
  setCurrentTab: (tab) => set({ currentTab: tab }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSystemStatus: (status) => set({ systemStatus: status }),
  setProcesses: (processes) => set({ processes }),
  setCurrentPath: (path) => set({ currentPath: path }),
  setFileList: (files) => set({ fileList: files }),
  setFileTreeData: (path, files) => set((state) => ({
    fileTreeData: { ...state.fileTreeData, [path]: files }
  })),
  toggleFileSelection: (path) => set((state) => {
    const newSelected = new Set(state.selectedFiles);
    if (newSelected.has(path)) {
      newSelected.delete(path);
    } else {
      newSelected.add(path);
    }
    return { selectedFiles: newSelected };
  }),
  clearFileSelection: () => set({ selectedFiles: new Set() }),
  toggleExpandedDir: (path) => set((state) => {
    const newExpanded = new Set(state.expandedDirs);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    return { expandedDirs: newExpanded };
  }),
  setPreviewFile: (file) => set({ previewFile: file }),
  appendTerminalOutput: (text) => set((state) => ({
    terminalOutput: state.terminalOutput + text
  })),
  clearTerminal: () => set({ terminalOutput: '' }),
  setTerminalPath: (path) => set({ terminalPath: path }),
  setPtySessionId: (id) => set({ ptySessionId: id }),
  setScriptEditorContent: (content) => set({ scriptEditorContent: content }),
  setScriptResult: (result) => set({ scriptResult: result }),
  setIsScriptRunning: (running) => set({ isScriptRunning: running }),
  addToast: (message, type = 'info') => {
    switch (type) {
      case 'success':
        toast.success(message);
        break;
      case 'error':
        toast.error(message);
        break;
      case 'warning':
        toast.warning(message);
        break;
      case 'info':
      default:
        toast.info(message);
        break;
    }
  },
  setMonitorAutoRefresh: (enabled) => set({ monitorAutoRefresh: enabled }),
  sendMessage: (type, data) => {
    const ws = get().ws;
    const currentDevice = get().currentDevice;
    
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      get().addToast('未连接到服务器', 'error');
      return false;
    }

    if (currentDevice?.device_id) {
      data.device_id = currentDevice.device_id;
    }

    const json = JSON.stringify(data);
    const bytes = new TextEncoder().encode(json);
    const msg = new Uint8Array(1 + bytes.length);
    msg[0] = type;
    msg.set(bytes, 1);
    ws.send(msg);
    return true;
  },
}));
