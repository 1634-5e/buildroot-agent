import { useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '@/store/appStore';
import { MessageType, FileInfo } from '@/types';
import { getDirectoryCallback, getRegisteredPaths } from '@/utils/callbackRegistry';

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const messageQueueRef = useRef<ArrayBuffer[]>([]);
  const isConnectingRef = useRef(false);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isCleanupRef = useRef(false);

  const store = useAppStore();

  const handleDeviceList = useCallback((data: any) => {
    if (data?.devices && Array.isArray(data.devices)) {
      const mappedDevices = data.devices.map((d: any) => ({
        id: d.device_id || d.id || '',
        device_id: d.device_id,
        name: d.name || d.device_id || 'Unknown Device',
        ip: d.ip || d.remote_addr || '',
        remote_addr: d.remote_addr,
        mac: d.mac || '',
        status: d.status === 'online' ? 'online' : 'offline',
        cpu: d.cpu,
        memory: d.memory,
        disk: d.disk,
        uptime: d.uptime,
        connected_time: d.connected_time,
      }));
      store.setDevices(mappedDevices);
    }
  }, [store]);

  const handleSystemStatus = useCallback((data: any) => {
    const memTotal = data.mem_total ?? 0;
    const memUsed = data.mem_used ?? 0;
    const diskTotal = data.disk_total ?? 0;
    const diskUsed = data.disk_used ?? 0;
    const deviceId = data.device_id || data.deviceId;

    const systemStatus = {
      cpu: {
        usage: data.cpu_usage ?? 0,
        cores: data.cpu_cores ?? 0,
        user: data.cpu_user ?? 0,
        sys: data.cpu_system ?? 0,
      },
      memory: {
        total: memTotal * 1024 * 1024,
        used: memUsed * 1024 * 1024,
        free: Math.max(0, memTotal - memUsed) * 1024 * 1024,
      },
      disk: {
        total: diskTotal * 1024 * 1024,
        used: diskUsed * 1024 * 1024,
        free: Math.max(0, diskTotal - diskUsed) * 1024 * 1024,
      },
      load: {
        '1m': data.load_1min ?? 0,
        '5m': data.load_5min ?? 0,
        '15m': data.load_15min ?? 0,
      },
      uptime: data.uptime ?? 0,
      network: {
        rx: data.net_rx_bytes ?? 0,
        tx: data.net_tx_bytes ?? 0,
      },
      ip: data.ip_addr || '',
      mac: data.mac_addr || '',
    };
    
    store.setSystemStatus(systemStatus);
    
    if (data.processes && Array.isArray(data.processes)) {
      store.setProcesses(data.processes);
    }

    const updatedDevices = store.devices.map(d => {
      const dId = d.device_id || d.id;
      if (dId === deviceId) {
        return {
          ...d,
          cpu: data.cpu_usage,
          memory: memTotal > 0 ? (memUsed / memTotal) * 100 : undefined,
          disk: diskTotal > 0 ? (diskUsed / diskTotal) * 100 : undefined,
          ip: data.ip_addr || d.ip,
          mac: data.mac_addr || d.mac,
          uptime: data.uptime || d.uptime,
        };
      }
      return d;
    });
    store.setDevices(updatedDevices);
  }, [store]);

  const handleFileList = useCallback((data: any) => {
    console.log('handleFileList called with:', data);
    
    if (!data || !Array.isArray(data.files)) {
      console.warn('Invalid file list data:', data);
      return;
    }

    const path = data.path;
    const chunk = data.chunk ?? 0;
    const totalChunks = data.total_chunks ?? 1;

    console.log(`File list chunk ${chunk + 1}/${totalChunks} for path: ${path}`);

    const fileList: FileInfo[] = data.files.map((file: any) => ({
      path: file.path || file.name || '',
      name: file.name || file.path || '',
      size: file.size || 0,
      isDirectory: file.is_dir || file.isDirectory || file.type === 'directory',
      modified: file.modified || file.mtime || undefined,
      children: file.children || undefined,
    }));

    console.log('Mapped file list:', fileList);

    if (path === '/') {
      store.addFileListChunkAndMaybeSet(chunk, fileList, totalChunks);
    } else {
      console.log(`Handling subdirectory: ${path}`);
      const callback = getDirectoryCallback(path);
      if (callback) {
        console.log(`Calling callback for ${path}`);
        callback(chunk, totalChunks, fileList);
      } else {
        console.warn(`No callback found for path: ${path}`);
        console.warn('Available callbacks:', getRegisteredPaths());
        console.warn('Requested path:', path);
      }
    }
  }, [store]);

  const handleFileData = useCallback((data: any) => {
    if (!data) return;

    const chunkData = data.chunk_data || data.content || data.data;
    
    if (!chunkData) return;

    try {
      const decoded = atob(chunkData);
      store.addFileChunk(data.offset || 0, decoded);

      const chunks = store.fileChunks;
      const sortedChunks = Array.from(chunks.entries())
        .sort((a: [number, string], b: [number, string]) => a[0] - b[0]);

      const combined = sortedChunks.map(([_, data]) => data).join('');
      store.setFileContent(combined);
    } catch (e) {
      console.error('Error decoding base64 file data:', e);
    }
  }, [store]);

  const handleMessage = useCallback((msgType: number, data: any) => {
    switch (msgType) {
      case MessageType.DEVICE_LIST:
        handleDeviceList(data);
        break;
      case MessageType.SYSTEM_STATUS:
        handleSystemStatus(data);
        break;
      case MessageType.FILE_LIST_RESPONSE:
        handleFileList(data);
        break;
      case MessageType.FILE_DATA:
        handleFileData(data);
        break;

      case MessageType.AUTH_RESULT:
        if (data && data.success === false) {
          console.error('Authentication failed:', data.message);
        }
        break;
    }
  }, [handleDeviceList, handleSystemStatus, handleFileList, handleFileData]);

  const sendBinary = useCallback((msgType: number, data: any = {}) => {
    const dataStr = JSON.stringify(data);
    const encoder = new TextEncoder();
    const dataBytes = encoder.encode(dataStr);
    const buffer = new Uint8Array(1 + dataBytes.length);
    buffer[0] = msgType;
    buffer.set(dataBytes, 1);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(buffer);
    } else {
      messageQueueRef.current.push(buffer.buffer);
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN && !isCleanupRef.current) {
        sendBinary(MessageType.HEARTBEAT, {});
      }
    }, 30000);
  }, [sendBinary]);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  const processMessage = useCallback(async (event: MessageEvent) => {
    try {
      if (event.data instanceof ArrayBuffer) {
        const bytes = new Uint8Array(event.data);
        if (bytes.length === 0) return;

        const msgType = bytes[0];
        const dataStr = new TextDecoder().decode(bytes.slice(1));
        let data;

        try {
          data = dataStr ? JSON.parse(dataStr) : {};
        } catch (parseErr) {
          console.error('Error parsing message data:', parseErr);
          return;
        }

        handleMessage(msgType, data);
        return;
      }

      if (event.data instanceof Blob) {
        const buffer = await event.data.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        if (bytes.length === 0) return;

        const msgType = bytes[0];
        const dataStr = new TextDecoder().decode(bytes.slice(1));
        let data;

        try {
          data = dataStr ? JSON.parse(dataStr) : {};
        } catch (parseErr) {
          console.error('Error parsing message data:', parseErr);
          return;
        }

        handleMessage(msgType, data);
        return;
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }, [handleMessage]);

  const cleanupConnection = useCallback(() => {
    if (isCleanupRef.current) return;
    
    stopHeartbeat();

    if (wsRef.current) {
      try {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        
        if (wsRef.current.readyState === WebSocket.OPEN ||
            wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close();
        }
      } catch (e) {
        console.warn('Error closing WebSocket:', e);
      }
      wsRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    isConnectingRef.current = false;
    store.setIsConnected(false);
  }, [stopHeartbeat, store]);

  const connect = useCallback((urlOverride?: string) => {
    if (isConnectingRef.current) return;
    if (isCleanupRef.current) return;

    cleanupConnection();

    isConnectingRef.current = true;

    let url = urlOverride || store.wsUrl;

    if (!url) {
      url = 'ws://localhost:8765';
    }

    try {
      new URL(url);
    } catch (e) {
      console.error('Invalid WebSocket URL:', url, e);
      store.setIsConnected(false);
      isConnectingRef.current = false;
      return;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isCleanupRef.current) return;
        
        console.log('WebSocket connected');
        isConnectingRef.current = false;
        reconnectAttemptsRef.current = 0;
        store.setIsConnected(true);
        startHeartbeat();

        while (messageQueueRef.current.length > 0) {
          const message = messageQueueRef.current.shift();
          if (message && wsRef.current?.readyState === WebSocket.OPEN) {
            try {
              wsRef.current.send(message);
            } catch (e) {
              console.error('Error sending queued message:', e);
            }
          }
        }

        sendBinary(MessageType.DEVICE_LIST, { action: 'get_list' });
      };

      ws.onmessage = processMessage;

      ws.onclose = (event: CloseEvent) => {
        if (isCleanupRef.current) return;
        
        console.log('WebSocket disconnected', { code: event.code, reason: event.reason });
        isConnectingRef.current = false;
        store.setIsConnected(false);
        stopHeartbeat();

        if (event.code === 1000) return;

        const maxAttempts = store.maxReconnectAttempts;

        if (event.code === 1005) return;

        if (reconnectAttemptsRef.current < maxAttempts) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttemptsRef.current),
            30000
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            if (!isCleanupRef.current) {
              reconnectAttemptsRef.current++;
              connect(url);
            }
          }, delay);
        }
      };

      ws.onerror = (error: Event) => {
        if (isCleanupRef.current) return;
        
        console.error('WebSocket error:', {
          type: error.type,
          readyState: (error.target as WebSocket)?.readyState,
          url: (error.target as WebSocket)?.url,
        });
        isConnectingRef.current = false;
        stopHeartbeat();
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      store.setIsConnected(false);
      isConnectingRef.current = false;
    }
  }, [cleanupConnection, store, startHeartbeat, stopHeartbeat, sendBinary, processMessage]);

  const disconnect = useCallback(() => {
    isCleanupRef.current = true;
    cleanupConnection();
  }, [cleanupConnection]);

  const send = useCallback((msgType: number, data: any = {}) => {
    sendBinary(msgType, data);
  }, [sendBinary]);

  useEffect(() => {
    isCleanupRef.current = false;
    connect();

    return () => {
      disconnect();
    };
  }, [store.wsUrl]);

  useEffect(() => {
    (window as any).currentWebSocket = wsRef.current;
  });

  return { send, sendBinary, connect, disconnect, wsRef };
}
