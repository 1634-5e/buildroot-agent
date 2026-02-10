import { useEffect, useRef, useCallback } from 'react';
import { useStore } from '../store';
import { MessageType, type Device, type SystemStatus, type FileItem, type ScriptResult } from '../types';

export function useWebSocket() {
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const {
    setConnected,
    setWebSocket,
    setDevices,
    currentDevice,
    setSystemStatus,
    setFileList,
    setFileTreeData,
    setPreviewFile,
    appendTerminalOutput,
    setScriptResult,
    setIsScriptRunning,
    addToast,
    setPtySessionId,
    ptySessionId,
  } = useStore();

  const sendMessage = useCallback((type: MessageType, data: Record<string, unknown>) => {
    const ws = useStore.getState().ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      addToast('未连接到服务器', 'error');
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
  }, [currentDevice, addToast]);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let wsUrl: string;

    // For GitHub Codespaces/GitHub.dev, use same hostname with different port
    if (window.location.hostname.includes('github.dev') || window.location.hostname.includes('app.github.dev')) {
      // Keep the exact same hostname, just change the port
      const currentUrl = new URL(window.location.href);
      wsUrl = `${protocol}//${currentUrl.hostname}:8765/`;
    } else if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      wsUrl = `${protocol}//localhost:8765`;
    } else {
      // Production environment - use same hostname with port 8765
      wsUrl = `${protocol}//${window.location.hostname}:8765`;
    }

    console.log('Connecting to WebSocket:', wsUrl);
    console.log('Current page:', window.location.href);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
      setWebSocket(ws);
      addToast('已连接到服务器', 'success');
      
      // Start heartbeat
      startHeartbeat(ws);
    };

    ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason);
      setConnected(false);
      setWebSocket(null);
      addToast('与服务器断开连接，正在重连...', 'warning');
      
      // Reconnect after 3 seconds
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      addToast('连接错误，请检查服务器状态', 'error');
    };

    ws.onmessage = async (event: MessageEvent) => {
      try {
        const buffer = await event.data.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        const msgType = bytes[0];
        const data = JSON.parse(new TextDecoder().decode(bytes.slice(1)));
        console.log('Received message:', msgType, data);
        handleMessage(msgType, data);
      } catch (err) {
        console.error('Error handling message:', err);
      }
    };
  }, [setConnected, setWebSocket, addToast]);

  const handleMessage = useCallback((type: number, data: unknown) => {
    switch (type) {
      case MessageType.DEVICE_LIST:
        // Handle both formats: { devices: Device[] } and Device[]
        if (data && typeof data === 'object' && 'devices' in data) {
          setDevices((data as { devices: Device[] }).devices || []);
        } else if (Array.isArray(data)) {
          setDevices(data as Device[]);
        }
        break;
      case MessageType.SYSTEM_STATUS:
        setSystemStatus(data as SystemStatus);
        break;
      case MessageType.PTY_DATA:
        handleTerminalData(data as { data: string });
        break;
      case MessageType.FILE_LIST_RESPONSE: {
        const fileData = data as { path: string; files: FileItem[] };
        if (fileData.path) {
          setFileTreeData(fileData.path, fileData.files || []);
        }
        setFileList(fileData.files || []);
        break;
      }
      case MessageType.FILE_DATA:
        handleFileData(data as { name: string; content: string; size: number });
        break;
      case MessageType.SCRIPT_RESULT:
        handleScriptResult(data as ScriptResult);
        break;
      default:
        console.log('Unknown message type:', type, data);
    }
  }, [setDevices, setSystemStatus, setFileList, setFileTreeData, setPreviewFile, appendTerminalOutput, setScriptResult, setIsScriptRunning, setPtySessionId]);

  const handleTerminalData = useCallback((data: { data: string }) => {
    if (data.data) {
      try {
        const text = atob(data.data);
        appendTerminalOutput(text);
      } catch (e) {
        console.error('Error decoding terminal data:', e);
      }
    }
  }, [appendTerminalOutput]);

  const handleFileData = useCallback((data: { name: string; content: string; size: number }) => {
    setPreviewFile(data);
  }, [setPreviewFile]);

  const handleScriptResult = useCallback((data: ScriptResult) => {
    setScriptResult(data);
    setIsScriptRunning(false);
  }, [setScriptResult, setIsScriptRunning]);

  const startHeartbeat = useCallback((ws: WebSocket) => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    
    heartbeatIntervalRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        const heartbeatMsg = new Uint8Array([MessageType.HEARTBEAT]);
        ws.send(heartbeatMsg);
      }
    }, 30000); // Send heartbeat every 30 seconds
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
      const ws = useStore.getState().ws;
      if (ws) {
        if (ptySessionId) {
          sendMessage(MessageType.PTY_CLOSE, { session_id: ptySessionId });
        }
        ws.close();
      }
    };
  }, [connect, sendMessage, ptySessionId]);

  return { sendMessage };
}
