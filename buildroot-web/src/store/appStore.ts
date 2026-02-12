import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Device, SystemStatus, Process, FileInfo } from '@/types';

// Default values from environment variables
const DEFAULT_WS_URL = import.meta.env.VITE_DEFAULT_WS_URL || '';
const DEFAULT_MAX_RECONNECT = parseInt(import.meta.env.VITE_DEFAULT_MAX_RECONNECT || '10');
const DEFAULT_REFRESH_INTERVAL = parseInt(import.meta.env.VITE_DEFAULT_REFRESH_INTERVAL || '5');
const DEFAULT_AUTO_SELECT = import.meta.env.VITE_DEFAULT_AUTO_SELECT !== 'false';

interface AppState {
  // WebSocket
  isConnected: boolean;
  setIsConnected: (connected: boolean) => void;

  // Devices
  devices: Device[];
  setDevices: (devices: Device[]) => void;
  currentDevice: Device | null;
  setCurrentDevice: (device: Device | null) => void;

  // System Status
  systemStatus: SystemStatus | null;
  setSystemStatus: (status: SystemStatus | null) => void;

  // Processes
  processes: Process[];
  setProcesses: (processes: Process[]) => void;

  // Terminal
  ptySessionId: string | null;
  setPtySessionId: (id: string | null) => void;

  // Files
  currentPath: string;
  setCurrentPath: (path: string) => void;
  fileList: FileInfo[];
  setFileList: (files: FileInfo[]) => void;
  fileContent: string | null;
  setFileContent: (content: string | null) => void;
  fileChunks: Map<number, string>;
  setFileChunks: (chunks: Map<number, string>) => void;
  addFileChunk: (offset: number, data: string) => void;
  clearFileChunks: () => void;
  fileListChunks: Map<number, FileInfo[]>;
  setFileListChunks: (chunks: Map<number, FileInfo[]>) => void;
  addFileListChunk: (chunk: number, files: FileInfo[]) => void;
  addFileListChunkAndMaybeSet: (chunk: number, files: FileInfo[], totalChunks: number) => void;
  clearFileListChunks: () => void;
  directoryData: Map<string, FileInfo[]>;
  setDirectoryData: (path: string, files: FileInfo[]) => void;
  clearDirectoryData: () => void;

  // Settings
  wsUrl: string;
  setWsUrl: (url: string) => void;
  authToken: string;
  setAuthToken: (token: string) => void;
  autoSelectFirst: boolean;
  setAutoSelectFirst: (auto: boolean) => void;
  maxReconnectAttempts: number;
  setMaxReconnectAttempts: (max: number) => void;
  refreshInterval: number;
  setRefreshInterval: (interval: number) => void;

  // Reset settings
  resetSettings: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // WebSocket
      isConnected: false,
      setIsConnected: (connected) => set({ isConnected: connected }),

      // Devices
      devices: [],
      setDevices: (devices) => set({ devices }),
      currentDevice: null,
      setCurrentDevice: (device) => set({ currentDevice: device }),

      // System Status
      systemStatus: null,
      setSystemStatus: (status) => set({ systemStatus: status }),

      // Processes
      processes: [],
      setProcesses: (processes) => set({ processes }),

      // Terminal
      ptySessionId: null,
      setPtySessionId: (id) => set({ ptySessionId: id }),

      // Files
      currentPath: '/',
      setCurrentPath: (path) => set({ currentPath: path }),
      fileList: [],
      setFileList: (files) => {
        console.log('store.setFileList: Setting file list with', files?.length || 0, 'files');
        return set({ fileList: files });
      },
      fileContent: null,
      setFileContent: (content) => set({ fileContent: content }),
      fileChunks: new Map(),
      setFileChunks: (chunks) => set({ fileChunks: chunks }),
      addFileChunk: (offset, data) => set((state) => {
        const newChunks = new Map(state.fileChunks);
        newChunks.set(offset, data);
        return { fileChunks: newChunks };
      }),
      clearFileChunks: () => set({ fileChunks: new Map() }),
      fileListChunks: new Map(),
      setFileListChunks: (chunks) => set({ fileListChunks: chunks }),
      addFileListChunk: (chunk, files) => set((state) => {
        const newChunks = new Map(state.fileListChunks);
        newChunks.set(chunk, files);
        console.log('store.addFileListChunk: Adding chunk', chunk, 'with', files.length, 'files');
        console.log('store.addFileListChunk: Current chunks:', Array.from(newChunks.keys()));
        return { fileListChunks: newChunks };
      }),
      addFileListChunkAndMaybeSet: (chunk, files, totalChunks) => set((state) => {
        const newChunks = new Map(state.fileListChunks);
        newChunks.set(chunk, files);
        console.log('store.addFileListChunkAndMaybeSet: Adding chunk', chunk, 'with', files.length, 'files');
        
        let mergedFiles: FileInfo[] | undefined;
        let clearedChunks = false;
        
        if (chunk + 1 >= totalChunks) {
          mergedFiles = [];
          for (let i = 0; i < totalChunks; i++) {
            if (newChunks.has(i)) {
              const chunkData = newChunks.get(i)!;
              mergedFiles.push(...chunkData);
            }
          }
          clearedChunks = true;
          console.log('store.addFileListChunkAndMaybeSet: Merged', mergedFiles.length, 'files from', totalChunks, 'chunks');
        }
        
        return { 
          fileListChunks: clearedChunks ? new Map() : newChunks,
          fileList: mergedFiles || state.fileList,
        };
      }),
      clearFileListChunks: () => {
        console.log('store.clearFileListChunks: Clearing file list chunks');
        return set({ fileListChunks: new Map() });
      },
      directoryData: new Map(),
      setDirectoryData: (path, files) => set((state) => {
        const newMap = new Map(state.directoryData);
        newMap.set(path, files);
        return { directoryData: newMap };
      }),
      clearDirectoryData: () => set({ directoryData: new Map() }),

      // Settings
      wsUrl: DEFAULT_WS_URL,
      setWsUrl: (url) => set({ wsUrl: url }),
      authToken: '',
      setAuthToken: (token) => set({ authToken: token }),
      autoSelectFirst: DEFAULT_AUTO_SELECT,
      setAutoSelectFirst: (auto) => set({ autoSelectFirst: auto }),
      maxReconnectAttempts: DEFAULT_MAX_RECONNECT,
      setMaxReconnectAttempts: (max) => set({ maxReconnectAttempts: max }),
      refreshInterval: DEFAULT_REFRESH_INTERVAL,
      setRefreshInterval: (interval) => set({ refreshInterval: interval }),

      // Reset settings
      resetSettings: () => set({
        wsUrl: DEFAULT_WS_URL,
        authToken: '',
        autoSelectFirst: DEFAULT_AUTO_SELECT,
        maxReconnectAttempts: DEFAULT_MAX_RECONNECT,
        refreshInterval: DEFAULT_REFRESH_INTERVAL,
      }),
    }),
    {
      name: 'buildroot-web-storage',
      partialize: (state) => ({
        wsUrl: state.wsUrl,
        authToken: state.authToken,
        autoSelectFirst: state.autoSelectFirst,
        maxReconnectAttempts: state.maxReconnectAttempts,
        refreshInterval: state.refreshInterval,
      }),
    }
  )
);
