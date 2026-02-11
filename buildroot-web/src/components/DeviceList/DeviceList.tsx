import { useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import { Device } from '@/types';
import { useAppStore } from '@/store/appStore';

interface DeviceListProps {
  devices: Device[];
  selectedDevice: Device | null;
  onDeviceSelect: (device: Device) => void;
  onReconnect: () => void;
  isConnected: boolean;
}

export function DeviceList({ devices, selectedDevice, onDeviceSelect, onReconnect, isConnected }: DeviceListProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [reconnecting, setReconnecting] = useState(false);
  const [showUrl, setShowUrl] = useState(false);

  // Get current WebSocket URL
  const wsUrl = useAppStore((state) => state.wsUrl);
  const autoDetectedUrl = wsUrl || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8765`;

  const filteredDevices = devices.filter((device) => {
    const name = device.name || device.device_id || 'Unknown';
    const ip = device.ip || device.remote_addr || '';
    
    return (
      name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ip.includes(searchTerm)
    );
  });

  const handleReconnect = () => {
    setReconnecting(true);
    onReconnect();
    setTimeout(() => setReconnecting(false), 2000);
  };

  return (
    <aside className="w-80 bg-bg-tertiary border-r border-border flex flex-col">
      <div className="p-5 border-b border-border">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-base font-semibold">设备列表</h2>
          <button
            onClick={handleReconnect}
            disabled={reconnecting}
            className={`text-xs px-2 py-1 bg-bg-tertiary border border-border rounded hover:bg-bg-elevated transition-colors ${
              reconnecting ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            title="重新连接服务器"
          >
            <RefreshCw size={14} className={reconnecting ? 'animate-spin' : ''} />
          </button>
        </div>
        <div className={`flex items-center gap-2 text-sm ${
          isConnected ? 'text-accent-success' : 'text-text-muted'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            isConnected
              ? 'bg-accent-success shadow-[0_0_8px_var(--accent-success)]'
              : 'bg-text-muted'
          }`} />
          <span className="flex-1">
            {reconnecting ? '重新连接中...' : isConnected ? '已连接' : '未连接'}
          </span>
          <button
            onClick={() => setShowUrl(!showUrl)}
            className="text-xs text-text-muted hover:text-text-primary transition-colors"
            title="查看连接地址"
          >
            🔗
          </button>
        </div>
        {showUrl && (
          <div className="mt-2 p-2 bg-bg-secondary rounded text-xs font-mono text-text-muted break-all">
            {autoDetectedUrl}
          </div>
        )}
      </div>

      <div className="px-5 py-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" size={16} />
          <input
            type="text"
            placeholder="搜索设备..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-bg-secondary border border-border rounded-md text-text-primary text-sm outline-none focus:border-accent-primary transition-colors"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {filteredDevices.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-text-muted">
            <span className="text-5xl mb-4 opacity-50">📡</span>
            <span className="text-sm">{searchTerm ? '未找到设备' : '等待设备连接...'}</span>
          </div>
         ) : (
           filteredDevices.map((device) => (
             <div
               key={device.device_id || device.id}
               onClick={() => onDeviceSelect(device)}
               className={`p-4 bg-bg-secondary border rounded-lg mb-2 cursor-pointer transition-all hover:translate-x-1 ${
                 selectedDevice?.id === device.id || selectedDevice?.device_id === device.device_id
                     ? 'bg-accent-primary/10 border-accent-primary'
                     : 'border-border hover:border-accent-primary/30'
                 }`}
             >
               <div className="flex items-center gap-3 mb-3">
                 <div className="w-10 h-10 bg-gradient-to-br from-accent-primary to-accent-secondary rounded-lg flex items-center justify-center text-lg">
                   📱
                 </div>
                 <div>
                   <h4 className="text-sm font-semibold">
                     {device.name || device.device_id || 'Unknown Device'}
                   </h4>
                   <span className="text-xs text-accent-success">
                     {device.status === 'online' ? '在线' : '离线'}
                   </span>
                 </div>
               </div>

                <div className="grid grid-cols-3 gap-2 pt-3 border-t border-border">
                  <div className="text-center truncate px-1">
                    <div className="text-sm font-semibold text-accent-primary">
                      {device.cpu !== undefined ? `${device.cpu}%` : '--'}
                    </div>
                    <div className="text-[11px] text-text-muted">CPU</div>
                  </div>
                  <div className="text-center truncate px-1">
                    <div className="text-sm font-semibold text-accent-primary">
                      {device.memory !== undefined ? `${device.memory}%` : '--'}
                    </div>
                    <div className="text-[11px] text-text-muted">内存</div>
                  </div>
                  <div className="text-center truncate px-1">
                    <div className="text-sm font-semibold text-accent-primary">
                      {device.disk !== undefined ? `${device.disk}%` : '--'}
                    </div>
                    <div className="text-[11px] text-text-muted">磁盘</div>
                  </div>
                </div>
             </div>
           ))
         )}
       </div>
    </aside>
  );
}
