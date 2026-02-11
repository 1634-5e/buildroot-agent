import { useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '@/store/appStore';
import { MessageType, FileInfo } from '@/types';

// Global event emitter for PTY data
const ptyDataEmitter = new EventTarget();

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const messageQueueRef = useRef<ArrayBuffer[]>([]);
  const isConnectingRef = useRef(false);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const {
    wsUrl,
    setWsUrl,
    currentDevice,
    setIsConnected,
    setDevices,
    setSystemStatus,
    setProcesses,
    setFileList,
    devices,
  } = useAppStore();

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
      setDevices(mappedDevices);
      console.log('Devices loaded:', mappedDevices);
    }
  }, [setDevices]);

  const handleSystemStatus = useCallback((data: any) => {
    console.log('System status received:', data);
    
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
    
    setSystemStatus(systemStatus);
    
    if (data.processes && Array.isArray(data.processes)) {
      setProcesses(data.processes);
    }

    const updatedDevices = devices.map(d => {
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
    setDevices(updatedDevices);
  }, [setSystemStatus, setProcesses, setDevices, devices]);

  const handleFileList = useCallback((data: any) => {
    console.log('File list received:', data);
    console.log('Type of data:', typeof data);
    console.log('data.files:', data?.files);
    console.log('Is array:', Array.isArray(data?.files));
    
    if (data && Array.isArray(data.files)) {
      const fileList: FileInfo[] = data.files.map((file: any) => ({
        path: file.path || file.name || '',
        name: file.name || file.path || '',
        size: file.size || 0,
        isDirectory: file.isDirectory || file.type === 'directory',
        modified: file.modified || file.mtime || undefined,
        children: file.children || undefined,
      }));
      console.log('Setting file list:', fileList);
      setFileList(fileList);
    } else {
      console.warn('File list data is invalid or missing files array');
    }
  }, [setFileList]);

  const handlePTYData = useCallback((data: any, deviceId: string) => {
    const terminalData = data.data || data;
    if (terminalData) {
      const event = new CustomEvent('ptyData', {
        detail: { deviceId, data: terminalData },
      });
      ptyDataEmitter.dispatchEvent(event);
    }
  }, []);

  const processMessage = useCallback(async (event: MessageEvent) => {
    try {
      if (event.data instanceof ArrayBuffer) {
        const bytes = new Uint8Array(event.data);
        if (bytes.length === 0) {
          console.warn('Received empty message');
          return;
        }

        const msgType = bytes[0];
        const dataStr = new TextDecoder().decode(bytes.slice(1));
        let data;

        try {
          data = dataStr ? JSON.parse(dataStr) : {};
        } catch (parseErr) {
          console.error('Error parsing message data:', parseErr, 'Data:', dataStr);
          return;
        }

        console.log('Received message:', msgType, data);
        handleMessage(msgType, data);
        return;
      }

      if (event.data instanceof Blob) {
        const buffer = await event.data.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        if (bytes.length === 0) {
          console.warn('Received empty message');
          return;
        }

        const msgType = bytes[0];
        const dataStr = new TextDecoder().decode(bytes.slice(1));
        let data;

        try {
          data = dataStr ? JSON.parse(dataStr) : {};
        } catch (parseErr) {
          console.error('Error parsing message data:', parseErr, 'Data:', dataStr);
          return;
        }

        console.log('Received message:', msgType, data);
        handleMessage(msgType, data);
        return;
      }

      if (typeof event.data === 'string') {
        console.warn('Received string message, expected binary:', event.data);
        try {
          const parsed = JSON.parse(event.data);
          handleMessage(parsed.type || 0, parsed.data || {});
        } catch (err) {
          console.error('Failed to parse string message:', err);
        }
        return;
      }

      console.warn('Unknown message type:', typeof event.data, event.data);
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }, []);

  const handleMessage = useCallback((msgType: number, data: any) => {
    console.log('handleMessage called with msgType:', msgType, 'data:', data);
    
    switch (msgType) {
      case MessageType.DEVICE_LIST:
        console.log('Processing DEVICE_LIST');
        handleDeviceList(data);
        break;
      case MessageType.SYSTEM_STATUS:
        console.log('Processing SYSTEM_STATUS');
        handleSystemStatus(data);
        break;
      case MessageType.FILE_LIST_RESPONSE:
        console.log('Processing FILE_LIST_RESPONSE');
        handleFileList(data);
        break;
      case MessageType.AUTH_RESULT:
        console.log('Processing AUTH_RESULT');
        // Handle authentication result from server
        if (data && data.success === false) {
          console.error('Authentication failed:', data.message);
        }
        break;
      case MessageType.PTY_DATA:
        console.log('Processing PTY_DATA');
        if (data && currentDevice) {
          const dataDeviceId = data.device_id || data.deviceId;
          const currentDeviceId = currentDevice.device_id || currentDevice.id;
          if (dataDeviceId === currentDeviceId) {
            handlePTYData(data, currentDeviceId);
          }
        }
        break;
      default:
        console.log('Unhandled message type:', msgType, data);
    }
  }, [handleDeviceList, handleSystemStatus, handleFileList, handlePTYData, currentDevice]);

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
      console.log('Message queued (not connected):', msgType);
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
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

  const setupWebSocketConnection = useCallback((ws: WebSocket) => {
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      isConnectingRef.current = false;
      setIsConnected(true);
      reconnectAttemptsRef.current = 0;
      startHeartbeat();

      while (messageQueueRef.current.length > 0) {
        const message = messageQueueRef.current.shift();
        if (message && wsRef.current?.readyState === WebSocket.OPEN) {
          try {
            wsRef.current.send(message);
            console.log('Sent queued message');
          } catch (e) {
            console.error('Error sending queued message:', e);
          }
        }
      }

      console.log('Requesting device list...');
      sendBinary(MessageType.DEVICE_LIST, { action: 'get_list' });
    };

    ws.onmessage = processMessage;

    ws.onclose = (event: CloseEvent) => {
      console.log('WebSocket disconnected', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      });
      isConnectingRef.current = false;
      setIsConnected(false);
      stopHeartbeat();

      if (event.code === 1000) {
        console.log('WebSocket closed normally, not reconnecting');
        return;
      }

      const maxAttempts = useAppStore.getState().maxReconnectAttempts;

      if (event.code === 1005) {
        console.log('Connection closed by server (1005), waiting for manual reconnect');
        return;
      }

      if (reconnectAttemptsRef.current < maxAttempts) {
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttemptsRef.current),
          30000
        );

        console.log(`Reconnecting in ${delay}ms... (attempt ${reconnectAttemptsRef.current + 1}/${maxAttempts})`);

        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptsRef.current++;
          // Trigger reconnection by changing wsUrl slightly
          const currentUrl = useAppStore.getState().wsUrl;
          const newUrl = currentUrl || '';
          if (!currentUrl) {
            // Force reconnect by setting and clearing wsUrl
            setWsUrl('dummy');
            setTimeout(() => setWsUrl(newUrl), 100);
          }
        }, delay);
      } else {
        console.log(`Max reconnect attempts (${maxAttempts}) reached`);
      }
    };

    ws.onerror = (error: Event) => {
      console.error('WebSocket error:', {
        type: error.type,
        target: (error.target as WebSocket)?.readyState,
        url: (error.target as WebSocket)?.url,
      });
      isConnectingRef.current = false;
      stopHeartbeat();
    };
  }, [processMessage, setIsConnected, startHeartbeat, stopHeartbeat, sendBinary]);

  const connect = useCallback(() => {
    if (isConnectingRef.current) {
      console.log('Connection already in progress, skipping');
      return;
    }

    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN ||
            wsRef.current.readyState === WebSocket.CONNECTING) {
          console.log('Closing existing WebSocket connection');
          wsRef.current.close();
        }
      } catch (e) {
        console.warn('Error closing existing WebSocket:', e);
      }
      wsRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    reconnectAttemptsRef.current = 0;
    isConnectingRef.current = true;

    let url = wsUrl;

    if (!url) {
      const hostname = 'localhost';
      const port = '8765';
      url = `ws://${hostname}:${port}`;
      console.log('Using development WebSocket URL:', url);
    }

    try {
      new URL(url);
    } catch (e) {
      console.error('Invalid WebSocket URL:', url, e);
      setIsConnected(false);
      isConnectingRef.current = false;
      return;
    }

    console.log(`Connecting to WebSocket: ${url}`);

    try {
      const ws = new WebSocket(url);
      setupWebSocketConnection(ws);
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      setIsConnected(false);
      isConnectingRef.current = false;
    }
  }, [wsUrl, setIsConnected, setupWebSocketConnection]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
  }, [setIsConnected]);

  const send = useCallback((msgType: number, data: any = {}) => {
    sendBinary(msgType, data);
  }, [sendBinary]);

  useEffect(() => {
    connect();

    return () => {
      stopHeartbeat();

      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [wsUrl, stopHeartbeat]);

  return { send, sendBinary, connect, disconnect };
}

export function usePTYData(deviceId: string | null, onData: (data: string) => void) {
  useEffect(() => {
    if (!deviceId) return;

    const handler = (event: Event) => {
      const customEvent = event as CustomEvent<{ deviceId: string; data: string }>;
      if (customEvent.detail.deviceId === deviceId) {
        onData(customEvent.detail.data);
      }
    };

    ptyDataEmitter.addEventListener('ptyData', handler);

    return () => {
      ptyDataEmitter.removeEventListener('ptyData', handler);
    };
  }, [deviceId, onData]);
}
