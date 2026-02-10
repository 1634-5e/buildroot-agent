import { useStore } from '../store';
import { Input } from '@/components/ui/input';
import type { Device } from '../types';

export function DeviceList() {
  const { devices, currentDevice, searchQuery, setSearchQuery, setCurrentDevice, isConnected, addToast } = useStore();

  const filteredDevices = devices.filter((d: Device) =>
    d.device_id.toLowerCase().includes(searchQuery.toLowerCase())
  ).sort((a, b) => {
    // Sort by status: online first, then by last_seen
    if (a.status === 'online' && b.status !== 'online') return -1;
    if (a.status !== 'online' && b.status === 'online') return 1;
    return (b.last_seen || 0) - (a.last_seen || 0);
  });

  const getDeviceStatus = (device: Device) => {
    const now = Date.now();
    const lastSeen = device.last_seen || 0;
    const timeDiff = now - lastSeen;
    
    if (timeDiff < 60000) { // Less than 1 minute
      return { status: 'online', label: '在线', color: 'text-[#10b981]' };
    } else if (timeDiff < 300000) { // Less than 5 minutes
      return { status: 'unknown', label: '离线', color: 'text-[#f59e0b]' };
    } else {
      return { status: 'offline', label: '离线', color: 'text-[#6e6e80]' };
    }
  };

  const handleSelectDevice = (device: Device) => {
    if (currentDevice?.device_id === device.device_id) {
      // If clicking the same device, deselect it
      setCurrentDevice(null);
      addToast('已取消选择设备', 'info');
      return;
    }
    
    setCurrentDevice(device);
    addToast(`已选择设备: ${device.device_id}`, 'success');
  };

   return (
     <aside className="bg-gradient-to-b from-[#1a1a24] to-[#0d0d12] border-r border-white/[0.15] flex flex-col w-80 lg:flex hidden shadow-2xl">
       <div className="p-6 border-b border-white/[0.15] bg-gradient-to-r from-[#16161e]/50 to-[#1a1a24]/50 backdrop-blur-sm">
         <div className="text-xl font-bold bg-gradient-to-r from-white via-[#a0a0c0] to-[#c0c0e0] bg-clip-text text-transparent mb-2">设备管理</div>
          <div className={`flex items-center gap-2.5 text-sm ${isConnected ? 'text-emerald-400' : 'text-gray-500'} transition-all`}>
            <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-[#10b981] shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse' : 'bg-[#6e6e80]'}`}></span>
            <span>{isConnected ? '已连接' : '未连接'}</span>
          </div>
       </div>
       <div className="mx-5 my-3">
         <Input
           placeholder="搜索设备..."
           value={searchQuery}
           onChange={(e) => setSearchQuery(e.target.value)}
           className="w-full bg-gradient-to-br from-[#16161e] to-[#0d0d12] border border-white/[0.15] text-sm shadow-[inset_0_2px_4px_rgba(0,0,0,0.2)]"
         />
       </div>
      <div className="flex-1 overflow-y-auto p-2">
         {filteredDevices.length === 0 ? (
           <div className="p-10 text-center text-[#6e6e80] animate-fadeSlideIn">
             <div className="text-6xl mb-4 opacity-50">📡</div>
             <div className="text-lg font-medium">暂无设备</div>
             <div className="text-sm mt-2">等待设备连接...</div>
           </div>
         ) : (
           filteredDevices.map((device: Device) => (
              <div
                key={device.device_id}
                onClick={() => handleSelectDevice(device)}
                className={`p-5 bg-gradient-to-br from-[#1a1a24] to-[#0d0d12] border border-white/[0.15] rounded-2xl mb-3 cursor-pointer transition-all duration-300 hover:shadow-2xl hover:scale-[1.02] transform ${
                  currentDevice?.device_id === device.device_id 
                    ? 'ring-2 ring-[#6366f1] bg-gradient-to-br from-blue-900/30 via-purple-900/20 to-blue-900/20 shadow-[0_0_20px_rgba(99,102,241,0.3)]' 
                    : 'shadow-lg'
                }`}
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-12 h-12 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-2xl flex items-center justify-center text-xl shadow-lg transform hover:scale-105 transition-all duration-200 ${
                    currentDevice?.device_id === device.device_id ? 'animate-pulse shadow-[0_0_20px_rgba(99,102,241,0.5)]' : 'hover:shadow-xl'
                  }`}>
                    📱
                  </div>
                 <div className="flex-1 min-w-0">
                   <h4 className="text-sm font-semibold truncate flex items-center gap-2">
                     {device.device_id}
                     {currentDevice?.device_id === device.device_id && (
                       <span className="text-xs px-2 py-0.5 bg-[#6366f1]/20 text-[#6366f1] rounded-full">当前</span>
                     )}
                   </h4>
                   <div className="flex items-center gap-2">
                     <div className="flex items-center gap-1.5">
                       <div className={`text-xs ${getDeviceStatus(device).color}`}>{getDeviceStatus(device).label}</div>
                       <div className={`w-1 h-1 rounded-full ${getDeviceStatus(device).color} ${getDeviceStatus(device).status === 'online' ? 'animate-pulse' : ''}`}></div>
                     </div>
                     {device.ip_addr && (
                       <div className="text-xs text-[#6e6e80]">{device.ip_addr}</div>
                     )}
                   </div>
                 </div>
               </div>
               <div className="grid grid-cols-3 gap-2 pt-3 border-t border-white/[0.08]">
                 <div className="text-center">
                   <div className="text-sm font-semibold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">{device.cpu_usage?.toFixed(0) || '--'}%</div>
                   <div className="text-[11px] text-[#6e6e80]">CPU</div>
                 </div>
                 <div className="text-center">
                   <div className="text-sm font-semibold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                     {device.mem_used ? (device.mem_used / 1024).toFixed(1) + 'G' : '--'}
                   </div>
                   <div className="text-[11px] text-[#6e6e80]">内存</div>
                 </div>
                 <div className="text-center">
                   <div className="text-sm font-semibold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">{device.load_1min?.toFixed(1) || '--'}</div>
                   <div className="text-[11px] text-[#6e6e80]">负载</div>
                 </div>
               </div>
             </div>
           ))
        )}
      </div>
    </aside>
  );
}
