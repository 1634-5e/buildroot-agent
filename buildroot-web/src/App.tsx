import { useWebSocket } from './hooks/useWebSocket';
import { useStore } from './store';
import { DeviceList } from './components/DeviceList';
import { Terminal } from './components/Terminal';
import { FileManager } from './components/FileManager';
import { Monitor } from './components/Monitor';
import { ScriptManager } from './components/ScriptManager';
import { Toaster } from './components/ui/sonner';
import { MessageType } from './types';
import './styles/index.css';

function App() {
  useWebSocket();
  const {
    currentDevice,
    currentTab,
    setCurrentTab,
    setCurrentDevice,
    clearTerminal,
    ptySessionId,
    addToast,
    isConnected,
  } = useStore();

  const { sendMessage } = useStore.getState();

  const handleDisconnect = () => {
    if (ptySessionId) {
      sendMessage(MessageType.PTY_CLOSE, { session_id: ptySessionId });
    }
    setCurrentDevice(null);
    clearTerminal();
    addToast('已断开设备连接', 'info');
  };

  const tabs = [
    { id: 'terminal' as const, label: '终端', icon: '💻' },
    { id: 'files' as const, label: '文件', icon: '📁' },
    { id: 'monitor' as const, label: '监控', icon: '📊' },
    { id: 'scripts' as const, label: '脚本', icon: '📜' },
  ];

  const renderTabContent = () => {
    switch (currentTab) {
      case 'terminal':
        return <Terminal />;
      case 'files':
        return <FileManager />;
      case 'monitor':
        return <Monitor />;
      case 'scripts':
        return <ScriptManager />;
      default:
        return <Terminal />;
    }
  };

   return (
     <div className="h-screen grid grid-cols-[64px_320px_1fr] bg-gradient-to-br from-[#0d0d12] to-[#0a0a0f]">
        {/* Primary Sidebar */}
        <nav className="bg-gradient-to-b from-[#16161e] to-[#121218] border-r border-white/[0.15] flex flex-col items-center py-4 gap-2 shadow-lg">
          <div className="w-10 h-10 bg-gradient-to-br from-[#6366f1] via-[#8b5cf6] to-[#ec4899] rounded-[12px] flex items-center justify-center text-xl mb-4 shadow-[0_8px_32px_rgba(99,102,241,0.3)]">
            🖥️
          </div>
          {/* Connection Status Indicator */}
          <div 
            className="w-12 h-12 flex items-center justify-center rounded-[12px] text-[22px] relative hover:scale-105 transition-all"
            title={`服务器状态: ${isConnected ? '已连接' : '未连接'}`}
          >
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-[#10b981] shadow-[0_0_12px_rgba(16,185,129,0.6)] animate-pulse' : 'bg-[#ef4444]'}`}></div>
          </div>
         <div 
           className="w-12 h-12 flex items-center justify-center rounded-[12px] text-[22px] cursor-pointer transition-all bg-gradient-to-b from-[#6366f1]/20 to-[#8b5cf6]/20 text-[#818cf8] relative hover:scale-105 hover:shadow-lg"
           title="设备"
         >
           📱
           <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-gradient-to-b from-[#6366f1] to-[#8b5cf6] rounded-r-[3px] shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
         </div>
         <div 
           className="w-12 h-12 flex items-center justify-center rounded-[12px] text-[#a0a0b0] text-[22px] cursor-pointer transition-all hover:bg-gradient-to-b hover:from-[#6366f1]/20 hover:to-[#8b5cf6]/20 hover:text-[#818cf8] hover:scale-105 hover:shadow-lg"
           title="设置"
           onClick={() => addToast('设置功能开发中...', 'info')}
         >
           ⚙️
         </div>
       </nav>

      {/* Secondary Sidebar */}
      <DeviceList />

      {/* Main Content */}
      <main className="flex flex-col overflow-hidden">
       {!currentDevice ? (
           <div className="flex-1 flex flex-col items-center justify-center p-10 text-center animate-fadeSlideIn">
             <div className="text-8xl mb-6 opacity-40 animate-float">📱</div>
             <div className="text-3xl font-bold mb-3 bg-gradient-to-r from-white to-[#a0a0c0] bg-clip-text text-transparent">选择设备开始</div>
             <div className="text-lg text-[#a0a0b0] max-w-md">从左侧设备列表选择一个设备以开始管理和监控</div>
             <div className="mt-8 text-sm text-[#6e6e80]">等待设备连接...</div>
           </div>
         ) : (
          <>
            {/* Header */}
            <div className="px-6 py-5 bg-[#16161e] border-b border-white/[0.08] flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="text-3xl">📱</div>
                <div>
                  <h2 className="text-xl font-semibold">{currentDevice.device_id}</h2>
                  <div className="flex gap-2 mt-1">
                    <span className="flex items-center gap-1.5 px-3 py-1 bg-[#10b981]/15 text-[#10b981] rounded-full text-xs font-medium">
                      <span>●</span>
                      <span>在线</span>
                    </span>
                    <span className="text-[13px] text-[#6e6e80]">{currentDevice.ip_addr || 'IP未知'}</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-3">
                <button 
                  onClick={handleDisconnect}
                  className="px-5 py-2 bg-[#1e1e28] border border-white/[0.08] rounded-[10px] text-sm hover:bg-[#252532] hover:border-white/20 transition-all"
                >
                  断开
                </button>
                <button 
                  onClick={() => addToast('重启功能开发中...', 'info')}
                  className="px-5 py-2 bg-[#ef4444] text-white rounded-[10px] text-sm hover:bg-[#dc2626] transition-all"
                >
                  重启
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 px-6 bg-[#16161e] border-b border-white/[0.08]">
              {tabs.map((tab) => (
                <div
                  key={tab.id}
                  onClick={() => setCurrentTab(tab.id)}
                  className={`px-5 py-3 text-sm font-medium cursor-pointer border-b-2 transition-all flex items-center gap-2 ${
                    currentTab === tab.id 
                      ? 'text-[#6366f1] border-[#6366f1]' 
                      : 'text-[#a0a0b0] border-transparent hover:text-white'
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </div>
              ))}
            </div>

             {/* Tab Content */}
             <div className="flex-1 overflow-hidden relative p-6">
               <div className="animate-fadeSlideIn h-full">
                 {renderTabContent()}
               </div>
             </div>
          </>
        )}
      </main>

       {/* Toast Container */}
       <Toaster />
     </div>
   );
 }

export default App;
