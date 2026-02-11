import { createContext, useContext, ReactNode } from 'react';
import { useWebSocket as useWebSocketHook, usePTYData as usePTYDataHook } from '@/hooks/useWebSocket';

interface WebSocketContextValue {
  send: (msgType: number, data?: any) => void;
  connect: () => void;
  disconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { send, connect, disconnect } = useWebSocketHook();

  return (
    <WebSocketContext.Provider value={{ send, connect, disconnect }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
}

export { usePTYDataHook as usePTYData };
