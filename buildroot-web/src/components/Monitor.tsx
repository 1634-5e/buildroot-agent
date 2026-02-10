import { useEffect, useRef } from 'react';
import { useStore } from '../store';
import { Button } from '@/components/ui/button';
import { MessageType } from '../types';
import { formatBytes, formatDuration } from '../utils/helpers';

export function Monitor() {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const {
    systemStatus,
    monitorAutoRefresh,
    currentDevice,
    setMonitorAutoRefresh,
    addToast,
  } = useStore();

  const { sendMessage } = useStore.getState();

  useEffect(() => {
    if (currentDevice) {
      refreshSystemStatus();
      
      if (monitorAutoRefresh) {
        intervalRef.current = setInterval(() => {
          refreshSystemStatus();
        }, 5000);
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [currentDevice, monitorAutoRefresh]);

  const refreshSystemStatus = () => {
    if (!currentDevice) return;
    sendMessage(MessageType.SYSTEM_STATUS, {});
  };

  const toggleAutoRefresh = () => {
    setMonitorAutoRefresh(!monitorAutoRefresh);
    addToast(monitorAutoRefresh ? '已暂停刷新' : '已启用自动刷新', 'info');
  };

  const getBarColor = (value: number) => {
    if (value < 50) return 'bg-[#10b981]';
    if (value < 80) return 'bg-[#f59e0b]';
    return 'bg-[#ef4444]';
  };

   return (
     <div className="h-full overflow-y-auto space-y-6 p-5">
       {/* Toolbar */}
       <div className="flex justify-between items-center mb-5 px-5 py-4 bg-gradient-to-r from-[#16161e] to-[#1a1a24] rounded-2xl border border-white/[0.15] shadow-lg">
         <div className="text-lg font-semibold bg-gradient-to-r from-white to-[#a0a0c0] bg-clip-text text-transparent">📊 系统监控</div>
         <div className="flex gap-3">
           <Button 
             onClick={toggleAutoRefresh}
             variant="outline"
             size="sm"
             className="text-sm"
           >
             {monitorAutoRefresh ? '⏸️ 暂停刷新' : '▶️ 开始刷新'}
           </Button>
           <Button 
             onClick={refreshSystemStatus}
             variant="outline"
             size="sm"
             className="text-sm"
           >
             🔄 立即刷新
           </Button>
         </div>
       </div>

       {/* Metrics Grid */}
       <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-6">
         {/* CPU */}
         <div className="bg-gradient-to-br from-[#16161e] to-[#0d0d12] border border-white/[0.15] rounded-2xl p-6 shadow-xl">
           <div className="flex justify-between items-center mb-4">
             <div className="text-sm text-[#a0a0b0] flex items-center gap-2">
               <span>📊</span> CPU 使用率
             </div>
           </div>
            <div className="text-5xl font-extrabold mb-2 bg-gradient-to-r from-emerald-400 to-blue-500 bg-clip-text text-transparent">
              {systemStatus?.cpu_usage?.toFixed(0) || '--'}%
            </div>
           <div className="text-sm text-[#6e6e80] mb-4">
             {systemStatus?.cpu_cores || '--'} 核心
           </div>
            <div className="h-3 bg-gradient-to-r from-gray-800 to-gray-900 rounded-full overflow-hidden shadow-inner mb-4">
              <div 
                className={`h-full rounded-full transition-all duration-700 ease-out transform origin-left ${getBarColor(systemStatus?.cpu_usage || 0)}`}
                style={{ width: `${systemStatus?.cpu_usage || 0}%` }}
              />
            </div>
            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/[0.08]">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400 font-medium">用户态</span>
                <span className="font-semibold text-emerald-400">{systemStatus?.cpu_user?.toFixed(1) || '--'}%</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400 font-medium">系统态</span>
                <span className="font-semibold text-blue-400">{systemStatus?.cpu_system?.toFixed(1) || '--'}%</span>
              </div>
            </div>
         </div>

         {/* Memory */}
         <div className="bg-gradient-to-br from-[#16161e] to-[#0d0d12] border border-white/[0.15] rounded-2xl p-6 shadow-xl">
           <div className="flex justify-between items-center mb-4">
             <div className="text-sm text-[#a0a0b0] flex items-center gap-2">
               <span>💾</span> 内存使用
             </div>
           </div>
           <div className="text-4xl font-bold mb-1 bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
             {systemStatus?.mem_used ? formatBytes(systemStatus.mem_used * 1024 * 1024) : '--'}
           </div>
           <div className="text-sm text-[#6e6e80] mb-4">
             共 {systemStatus?.mem_total ? formatBytes(systemStatus.mem_total * 1024 * 1024) : '--'}
           </div>
           <div className="h-3 bg-gradient-to-r from-gray-800 to-gray-900 rounded-full overflow-hidden mb-4">
             <div 
               className={`h-full rounded-full transition-all duration-500 ${getBarColor(systemStatus?.mem_total ? (systemStatus.mem_used / systemStatus.mem_total) * 100 : 0)}`}
               style={{ width: `${systemStatus?.mem_total ? (systemStatus.mem_used / systemStatus.mem_total) * 100 : 0}%` }}
             />
           </div>
           <div className="grid grid-cols-2 gap-3 pt-4 border-t border-white/[0.08]">
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">已用</span>
               <span className="text-emerald-400">{systemStatus?.mem_used ? formatBytes(systemStatus.mem_used * 1024 * 1024) : '--'}</span>
             </div>
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">可用</span>
               <span className="text-blue-400">{systemStatus?.mem_free ? formatBytes(systemStatus.mem_free * 1024 * 1024) : '--'}</span>
             </div>
           </div>
         </div>

         {/* Disk */}
         <div className="bg-gradient-to-br from-[#16161e] to-[#0d0d12] border border-white/[0.15] rounded-2xl p-6 shadow-xl">
           <div className="flex justify-between items-center mb-4">
             <div className="text-sm text-[#a0a0b0] flex items-center gap-2">
               <span>💿</span> 磁盘使用
             </div>
           </div>
           <div className="text-4xl font-bold mb-1 bg-gradient-to-r from-yellow-400 to-orange-500 bg-clip-text text-transparent">
             {systemStatus?.disk_usage?.toFixed(0) || '--'}%
           </div>
           <div className="text-sm text-[#6e6e80] mb-4">
             {systemStatus?.disk_used ? formatBytes(systemStatus.disk_used * 1024 * 1024) : '--'} / {systemStatus?.disk_total ? formatBytes(systemStatus.disk_total * 1024 * 1024) : '--'}
           </div>
           <div className="h-3 bg-gradient-to-r from-gray-800 to-gray-900 rounded-full overflow-hidden mb-4">
             <div 
               className={`h-full rounded-full transition-all duration-500 ${getBarColor(systemStatus?.disk_usage || 0)}`}
               style={{ width: `${systemStatus?.disk_usage || 0}%` }}
             />
           </div>
           <div className="grid grid-cols-2 gap-3 pt-4 border-t border-white/[0.08]">
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">已用</span>
               <span className="text-orange-400">{systemStatus?.disk_used ? formatBytes(systemStatus.disk_used * 1024 * 1024) : '--'}</span>
             </div>
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">可用</span>
               <span className="text-blue-400">{systemStatus?.disk_total && systemStatus?.disk_used ? formatBytes((systemStatus.disk_total - systemStatus.disk_used) * 1024 * 1024) : '--'}</span>
             </div>
           </div>
         </div>

         {/* Load & Network */}
         <div className="bg-gradient-to-br from-[#16161e] to-[#0d0d12] border border-white/[0.15] rounded-2xl p-6 shadow-xl">
           <div className="flex justify-between items-center mb-4">
             <div className="text-sm text-[#a0a0b0] flex items-center gap-2">
               <span>⚡</span> 系统负载
             </div>
           </div>
           <div className="text-4xl font-bold mb-1 bg-gradient-to-r from-pink-400 to-red-500 bg-clip-text text-transparent">
             {systemStatus?.load_1min?.toFixed(2) || '--'}
           </div>
           <div className="text-sm text-[#6e6e80] mb-4">
             1分钟 / 5分钟 / 15分钟
           </div>
           <div className="h-3 bg-transparent rounded" />
           <div className="grid grid-cols-2 gap-3 pt-4 border-t border-white/[0.08]">
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">1m</span>
               <span className="text-pink-400">{systemStatus?.load_1min?.toFixed(2) || '--'}</span>
             </div>
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">5m</span>
               <span className="text-purple-400">{systemStatus?.load_5min?.toFixed(2) || '--'}</span>
             </div>
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">15m</span>
               <span className="text-blue-400">{systemStatus?.load_15min?.toFixed(2) || '--'}</span>
             </div>
             <div className="flex justify-between text-sm">
               <span className="text-[#6e6e80]">运行时间</span>
               <span className="text-emerald-400">{systemStatus?.uptime ? formatDuration(systemStatus.uptime) : '--'}</span>
             </div>
           </div>
         </div>
       </div>

       {/* Network Info */}
       <div className="bg-gradient-to-br from-[#16161e] to-[#0d0d12] border border-white/[0.15] rounded-2xl p-6 mb-6 shadow-xl">
         <div className="flex justify-between items-center mb-5">
           <div className="text-sm font-semibold text-[#a0a0b0] flex items-center gap-2">
             <span>🌐</span> 网络信息
           </div>
         </div>
         <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
           <div className="flex flex-col">
             <span className="text-[#6e6e80] text-sm mb-1">IP 地址</span>
             <span className="font-semibold text-white">{systemStatus?.ip_addr || '--'}</span>
           </div>
           <div className="flex flex-col">
             <span className="text-[#6e6e80] text-sm mb-1">MAC 地址</span>
             <span className="font-semibold text-white">{systemStatus?.mac_addr || '--'}</span>
           </div>
           <div className="flex flex-col">
             <span className="text-[#6e6e80] text-sm mb-1">接收</span>
             <span className="font-semibold text-emerald-400">{systemStatus?.rx_bytes ? formatBytes(systemStatus.rx_bytes) : '--'}</span>
           </div>
           <div className="flex flex-col">
             <span className="text-[#6e6e80] text-sm mb-1">发送</span>
             <span className="font-semibold text-blue-400">{systemStatus?.tx_bytes ? formatBytes(systemStatus.tx_bytes) : '--'}</span>
           </div>
         </div>
       </div>
     </div>
   );
}
