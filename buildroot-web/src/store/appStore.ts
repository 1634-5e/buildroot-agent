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
      currentPath: '/root',
      setCurrentPath: (path) => set({ currentPath: path }),
      fileList: [],
      setFileList: (files) => set({ fileList: files }),

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
