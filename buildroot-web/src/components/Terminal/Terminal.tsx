import { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { SearchAddon } from '@xterm/addon-search';
import { Search, X, RotateCcw } from 'lucide-react';
import '@xterm/xterm/css/xterm.css';
import { useWebSocket, usePTYData } from '@/hooks/useWebSocket';
import { MessageType } from '@/types';

interface TerminalProps {
  deviceId: string | null;
}

export function Terminal({ deviceId }: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const searchAddonRef = useRef<SearchAddon | null>(null);
  const sessionIdRef = useRef(0);
  const [connected, setConnected] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchMatches, setSearchMatches] = useState(0);
  const ptyInitializedRef = useRef(false);

  const { send } = useWebSocket();

  const initTerminal = useCallback(() => {
    if (!terminalRef.current || termRef.current) return;

    console.log('[Terminal] Initializing xterm.js...');
    
    const term = new XTerm({
      fontFamily: '"JetBrains Mono", "Fira Code", Consolas, monospace',
      fontSize: 14,
      cursorBlink: true,
      cursorStyle: 'block',
      theme: {
        background: '#1e1e2e',
        foreground: '#cdd6f4',
        cursor: '#f5e0dc',
        black: '#45475a',
        red: '#f38ba8',
        green: '#a6e3a1',
        yellow: '#f9e2af',
        blue: '#89b4fa',
        magenta: '#f5c2e7',
        cyan: '#94e2d5',
        white: '#bac2de',
        brightBlack: '#585b70',
        brightRed: '#eba0ac',
        brightGreen: '#a6e3a1',
        brightYellow: '#f9e2af',
        brightBlue: '#89b4fa',
        brightMagenta: '#f5c2e7',
        brightCyan: '#94e2d5',
        brightWhite: '#a6adc8',
      },
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    const searchAddon = new SearchAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.loadAddon(searchAddon);

    term.open(terminalRef.current);

    setTimeout(() => {
      try {
        fitAddon.fit();
      } catch (e) {
        console.warn('[Terminal] Failed to fit terminal:', e);
      }
    }, 100);

    termRef.current = term;
    fitAddonRef.current = fitAddon;
    searchAddonRef.current = searchAddon;

    console.log('[Terminal] xterm.js initialized');
  }, []);

  const sendPTYData = useCallback((data: string) => {
    if (!deviceId || !termRef.current || !ptyInitializedRef.current) return;
    
    try {
      const encoded = btoa(unescape(encodeURIComponent(data)));
      send(MessageType.PTY_DATA, {
        deviceId,
        sessionId: sessionIdRef.current,
        data: encoded,
      });
    } catch (e) {
      console.error('[Terminal] Error encoding PTY data:', e);
    }
  }, [deviceId, send]);

  const createPTYSession = useCallback(() => {
    if (!deviceId || !termRef.current || !fitAddonRef.current) {
      console.warn('[Terminal] Cannot create PTY: missing deviceId or terminal');
      return;
    }

    sessionIdRef.current = Date.now();
    ptyInitializedRef.current = true;
    
    console.log('[Terminal] Creating PTY session:', {
      deviceId,
      sessionId: sessionIdRef.current,
      rows: termRef.current.rows,
      cols: termRef.current.cols,
    });

    send(MessageType.PTY_CREATE, {
      deviceId,
      sessionId: sessionIdRef.current,
      rows: termRef.current.rows,
      cols: termRef.current.cols,
    });
  }, []);

  useEffect(() => {
    initTerminal();
  }, [initTerminal]);

  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (!termRef.current) return;

    const onData = (data: string) => {
      sendPTYData(data);
    };

    const onResize = (size: { rows: number; cols: number }) => {
      if (!deviceId || !ptyInitializedRef.current) return;
      
      console.log('[Terminal] Resizing:', size);
      send(MessageType.PTY_RESIZE, {
        deviceId,
        sessionId: sessionIdRef.current,
        rows: size.rows,
        cols: size.cols,
      });
    };

    termRef.current.onData(onData);
    termRef.current.onResize(onResize);

    return () => {
    };
  }, [deviceId, send]);

  usePTYData(deviceId, (data) => {
    if (termRef.current) {
      termRef.current.write(data);
    }
  });

  useEffect(() => {
    if (!deviceId) {
      ptyInitializedRef.current = false;
      setConnected(false);
      return;
    }

    const timer = setTimeout(() => {
      setConnected(true);
      createPTYSession();
    }, 200);

    return () => {
      clearTimeout(timer);
      if (ptyInitializedRef.current) {
        send(MessageType.PTY_CLOSE, {
          deviceId,
          sessionId: sessionIdRef.current,
        });
      }
    };
  }, [deviceId]);

  const handleSearch = useCallback(() => {
    if (!searchAddonRef.current) return;
    const result = searchAddonRef.current.findNext(searchTerm);
    setSearchMatches(typeof result === 'number' ? result : 0);
  }, []);

  const reconnectTerminal = useCallback(() => {
    ptyInitializedRef.current = false;
    setConnected(false);
    termRef.current?.clear();
    createPTYSession();
  }, []);

  const clearTerminal = useCallback(() => {
    termRef.current?.clear();
  }, []);

  return (
    <div className="h-full flex flex-col bg-bg-primary rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-bg-secondary border-b border-border flex-shrink-0">
        <div className="flex items-center gap-3 font-mono text-sm">
          <span className="text-text-muted">bash</span>
          <span className="text-text-muted">•</span>
          <span className="text-accent-primary cursor-pointer">~</span>
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
            title="重新连接"
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

      <div className="flex-1 relative overflow-hidden bg-[#1e1e2e]">
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
