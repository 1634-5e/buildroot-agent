import { useRef, useEffect } from 'react';
import { useStore } from '../store';
import { Button } from '@/components/ui/button';
import { MessageType } from '../types';

export function Terminal() {
  const outputRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { 
    terminalOutput, 
    terminalPath, 
    currentDevice,
    isConnected,
    appendTerminalOutput,
    clearTerminal,
    setPtySessionId,
    ptySessionId,
    addToast,
  } = useStore();

  const { sendMessage } = useStore.getState();

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [terminalOutput]);

  useEffect(() => {
    if (currentDevice && !ptySessionId) {
      connectTerminal();
    }
  }, [currentDevice]);

  const connectTerminal = () => {
    if (!currentDevice) return;
    
    const sessionId = Date.now();
    setPtySessionId(sessionId);
    
    sendMessage(MessageType.PTY_CREATE, {
      session_id: sessionId,
      rows: 24,
      cols: 80,
    });
    
    addToast('正在连接终端...', 'info');
  };

  const handleInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const input = inputRef.current;
      if (!input) return;
      
      const cmd = input.value;
      if (!cmd.trim()) return;
      
      input.value = '';
      appendTerminalOutput(`# ${cmd}\n`);
      
      if (ptySessionId) {
        sendMessage(MessageType.PTY_DATA, {
          session_id: ptySessionId,
          data: btoa(cmd + '\n'),
        });
      }
    }
  };

  const handleReconnect = () => {
    clearTerminal();
    if (ptySessionId) {
      sendMessage(MessageType.PTY_CLOSE, { session_id: ptySessionId });
    }
    setPtySessionId(null);
    connectTerminal();
  };

   return (
     <div className="h-full flex flex-col bg-gradient-to-br from-[#0d0d12] to-[#0a0a0f] rounded-2xl border border-white/[0.15] overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-[#16161e] to-[#1a1a24] border-b border-white/[0.15]">
           <div className="flex items-center gap-4 font-mono text-sm">
             <span className={`px-3 py-1.5 rounded-lg font-medium shadow-[inset_0_1px_2px_rgba(0,0,0,0.2)] ${
               ptySessionId ? 'bg-emerald-900/30 text-emerald-400' : 'bg-orange-900/30 text-orange-400'
             }`}>
               {ptySessionId ? '已连接' : '未连接'}
             </span>
             <span className="text-gray-500">›</span>
             <span className="text-blue-400 cursor-pointer hover:text-blue-300 font-medium transition-colors">{terminalPath}</span>
           </div>
         <div className="flex gap-2">
           <Button 
             onClick={clearTerminal}
             variant="outline"
             size="sm"
             className="text-sm"
           >
             清空
           </Button>
           <Button 
             onClick={handleReconnect}
             variant="outline"
             size="sm"
             className="text-sm"
           >
             重连
           </Button>
         </div>
       </div>
        <div 
          ref={outputRef}
          className="flex-1 p-5 font-mono text-[14px] leading-relaxed overflow-y-auto whitespace-pre-wrap break-all bg-[#0a0a0f] bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-[#0a0a0f] to-[#08080c]"
        >
          {terminalOutput ? (
            <div className="text-green-400">{terminalOutput}</div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-6xl mb-4 opacity-30">
                {ptySessionId ? '💻' : '🔌'}
              </div>
              <div className="text-lg font-medium mb-2">
                {ptySessionId ? '终端已就绪' : '等待连接终端...'}
              </div>
              <div className="text-sm text-[#6e6e80]">
                {!isConnected && '请先连接服务器'}
                {!currentDevice && isConnected && '请先选择设备'}
                {currentDevice && isConnected && !ptySessionId && '正在初始化终端会话...'}
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center gap-4 px-6 py-5 bg-gradient-to-r from-[#16161e] to-[#0d0d12] border-t border-white/[0.15] shadow-[inset_0_2px_4px_rgba(0,0,0,0.4)]">
          <span className="text-emerald-400 font-bold text-xl animate-pulse">❯</span>
          <input
            ref={inputRef}
            type="text"
            placeholder="输入命令..."
            onKeyDown={handleInput}
            className="flex-1 bg-transparent border-none outline-none text-base font-mono text-emerald-400 placeholder-gray-500 focus:placeholder-transparent caret-emerald-400"
            autoFocus
          />
        </div>
     </div>
   );
}
