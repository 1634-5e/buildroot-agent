import { useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { SearchAddon } from '@xterm/addon-search';
import { Search, X, RotateCcw } from 'lucide-react';
import '@xterm/xterm/css/xterm.css';
import { useWebSocket, usePTYData } from '@/contexts/WebSocketContext';
import { MessageType } from '@/types';

interface TerminalProps {
  deviceId: string | null;
}

// Base64 decode function for PTY data
function base64Decode(base64: string): string {
  try {
    // Handle URL-safe base64
    const normalized = base64.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = atob(normalized);
    // Convert binary string to Uint8Array, then to text
    const bytes = new Uint8Array(decoded.length);
    for (let i = 0; i < decoded.length; i++) {
      bytes[i] = decoded.charCodeAt(i);
    }
    return new TextDecoder('utf-8').decode(bytes);
  } catch (e) {
    console.error('Base64 decode error:', e);
    return base64; // Return original if decode fails
  }
}

// Base64 encode function for PTY data
function base64Encode(str: string): string {
  try {
    const encoder = new TextEncoder();
    const bytes = encoder.encode(str);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  } catch (e) {
    console.error('Base64 encode error:', e);
    return str; // Return original if encode fails
  }
}

export function Terminal({ deviceId }: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const searchAddonRef = useRef<SearchAddon | null>(null);
  const sessionIdRef = useRef(1);
  const [connected, setConnected] = useState(false);
  const [path] = useState('/root');
  const [showSearch, setShowSearch] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchMatches, setSearchMatches] = useState(0);

  const { send } = useWebSocket();

  // Handle PTY data from WebSocket
  usePTYData(deviceId, (data) => {
    if (termRef.current) {
      // Data may be base64 encoded from agent
      const decoded = base64Decode(data);
      termRef.current.write(decoded);
    }
  });

  useEffect(() => {
    if (!terminalRef.current || !deviceId) return;

    const term = new XTerm({
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: 14,
      cursorBlink: true,
      cursorStyle: 'block',
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    const searchAddon = new SearchAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.loadAddon(searchAddon);

    term.open(terminalRef.current);

    // Delay fit to ensure DOM is ready
    requestAnimationFrame(() => {
      try {
        fitAddon.fit();
      } catch (e) {
        console.warn('Failed to fit terminal:', e);
      }
    });

    termRef.current = term;
    fitAddonRef.current = fitAddon;
    searchAddonRef.current = searchAddon;

    // Request PTY creation with session_id
    console.log('Creating PTY for device:', deviceId);
    send(MessageType.PTY_CREATE, {
      deviceId: deviceId || '',
      sessionId: sessionIdRef.current,
      rows: term.rows,
      cols: term.cols,
    });

    term.onData((data: string) => {
      send(MessageType.PTY_DATA, {
        deviceId: deviceId || '',
        sessionId: sessionIdRef.current,
        data: base64Encode(data),
      });
    });

    term.onResize((size: { rows: number; cols: number }) => {
      send(MessageType.PTY_RESIZE, {
        deviceId: deviceId || '',
        sessionId: sessionIdRef.current,
        rows: size.rows,
        cols: size.cols,
      });
    });

    setConnected(true);

    return () => {
      try {
        term.dispose();
        send(MessageType.PTY_CLOSE, {
          deviceId: deviceId || '',
          sessionId: sessionIdRef.current,
        });
      } catch (e) {
        console.warn('Error disposing terminal:', e);
      }
      setConnected(false);
    };
  }, [deviceId, send]);

  const handleSearch = () => {
    if (!searchAddonRef.current) return;
    const matches = searchAddonRef.current.findNext(searchTerm);
    setSearchMatches(typeof matches === 'number' ? matches : 0);
  };

  const reconnectTerminal = () => {
    if (deviceId && termRef.current && fitAddonRef.current) {
      console.log('Reconnecting PTY for device:', deviceId);
      sessionIdRef.current += 1; // Use new session ID
      send(MessageType.PTY_CREATE, {
        deviceId: deviceId || '',
        sessionId: sessionIdRef.current,
        rows: termRef.current.rows,
        cols: termRef.current.cols,
      });
    }
  };

  const clearTerminal = () => {
    if (termRef.current) {
      termRef.current.clear();
    }
  };

  return (
    <div className="h-full flex flex-col bg-bg-primary rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-bg-secondary border-b border-border flex-shrink-0">
        <div className="flex items-center gap-3 font-mono text-sm">
          <span className="text-text-muted">bash</span>
          <span className="text-text-muted">•</span>
          <span className="text-accent-primary cursor-pointer">{path}</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSearch(!showSearch)}
            className="px-2.5 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated transition-colors"
            title="搜索 (Ctrl+Shift+F)"
          >
            <Search size={14} />
          </button>
          <button
            onClick={clearTerminal}
            className="px-2.5 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated transition-colors"
          >
            清空
          </button>
          <button
            onClick={reconnectTerminal}
            className="px-2.5 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated transition-colors"
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {showSearch && (
        <div className="flex items-center gap-2 px-4 py-1.5 bg-bg-elevated border-b border-border flex-shrink-0">
          <input
            type="text"
            placeholder="搜索终端内容..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1 max-w-[300px] px-2.5 py-1 bg-bg-primary border border-border rounded text-text-primary text-xs font-mono outline-none focus:border-accent-primary"
          />
          <span className="text-xs text-text-muted min-w-[60px]">{searchMatches} 个结果</span>
          <button
            onClick={() => {
              if (searchAddonRef.current) {
                searchAddonRef.current.findPrevious(searchTerm);
              }
            }}
            className="px-2 py-1 bg-bg-tertiary border border-border rounded text-text-secondary text-xs"
          >
            ▲
          </button>
          <button
            onClick={handleSearch}
            className="px-2 py-1 bg-bg-tertiary border border-border rounded text-text-secondary text-xs"
          >
            ▼
          </button>
          <button
            onClick={() => setShowSearch(false)}
            className="px-2 py-1 bg-bg-tertiary border border-border rounded text-text-secondary text-xs"
          >
            <X size={12} />
          </button>
        </div>
      )}

      <div className="flex-1 relative overflow-hidden">
        <div ref={terminalRef} className="h-full" />
      </div>

      <div className="flex items-center justify-between px-4 py-1 bg-bg-secondary border-t border-border text-[11px] text-text-muted font-mono flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-accent-success shadow-[0_0_6px_var(--accent-success)]' : 'bg-text-muted'}`} />
            {connected ? '已连接' : '未连接'}
          </span>
        </div>
        <div>
          {termRef.current && `${termRef.current.cols}×${termRef.current.rows}`}
        </div>
      </div>
    </div>
  );
}
