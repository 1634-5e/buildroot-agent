import { useEffect, useState } from 'react';
import { Cpu, HardDrive, Activity, Network, Pause, RefreshCw } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { formatBytes, formatUptime } from '@/utils/format';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { MessageType } from '@/types';
import { ProcessList } from '@/components/ProcessList/ProcessList';
import { Card } from '@/components/ui/card';

export function Monitor() {
  const { systemStatus, currentDevice, refreshInterval } = useAppStore();
  const { send } = useWebSocket();
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    if (!currentDevice || !autoRefresh) return;

    const interval = setInterval(() => {
      send(MessageType.CMD_REQUEST, {
        deviceId: currentDevice.device_id || currentDevice.id || '',
        command: 'system_status',
      });
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDevice, autoRefresh, refreshInterval]);

  const handleRefresh = () => {
    if (currentDevice) {
      send(MessageType.CMD_REQUEST, {
        deviceId: currentDevice.device_id || currentDevice.id || '',
        command: 'system_status',
      });
    }
  };

  if (!systemStatus || !systemStatus.cpu || !systemStatus.memory || !systemStatus.disk) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted">
        <Activity size={48} className="mb-4 opacity-50" />
        <span className="text-sm">等待系统数据...</span>
      </div>
    );
  }

  const cpuPercent = systemStatus.cpu.usage?.toFixed(1) ?? '0.0';
  const memPercent = systemStatus.memory.total > 0 ? ((systemStatus.memory.used / systemStatus.memory.total) * 100).toFixed(1) : '0.0';
  const diskPercent = systemStatus.disk.total > 0 ? ((systemStatus.disk.used / systemStatus.disk.total) * 100).toFixed(1) : '0.0';

  return (
    <div className="flex flex-col gap-4 h-full">
      <Card className="p-2 border-border bg-bg-secondary flex-shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold flex items-center gap-2">
            <Activity size={16} />
            系统监控
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className="px-2.5 py-1 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated"
            >
              {autoRefresh ? <Pause size={12} /> : <Activity size={12} />}
              {autoRefresh ? ' 暂停刷新' : ' 恢复刷新'}
            </button>
            <button
              onClick={handleRefresh}
              className="px-2.5 py-1 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated"
            >
              <RefreshCw size={12} />
              立即刷新
            </button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-6 gap-3 flex-shrink-0">
        <MetricCard
          icon={<Cpu size={18} />}
          title="CPU 使用率"
          value={`${cpuPercent}%`}
          subtitle={`${systemStatus.cpu.cores ?? 0} 核心`}
          percent={parseFloat(cpuPercent)}
          details={[
            { label: '用户态', value: `${systemStatus.cpu.user?.toFixed(1) ?? '0.0'}%` },
            { label: '系统态', value: `${systemStatus.cpu.sys?.toFixed(1) ?? '0.0'}%` },
          ]}
        />

        <MetricCard
          icon={<Activity size={18} />}
          title="内存使用"
          value={formatBytes(systemStatus.memory.used)}
          subtitle={`共 ${formatBytes(systemStatus.memory.total)}`}
          percent={parseFloat(memPercent)}
          details={[
            { label: '已用', value: formatBytes(systemStatus.memory.used ?? 0) },
            { label: '可用', value: formatBytes(systemStatus.memory.free ?? 0) },
          ]}
        />

        <MetricCard
          icon={<HardDrive size={18} />}
          title="磁盘使用"
          value={`${diskPercent}%`}
          subtitle={`${formatBytes(systemStatus.disk.used)} / ${formatBytes(systemStatus.disk.total)}`}
          percent={parseFloat(diskPercent)}
          details={[
            { label: '已用', value: formatBytes(systemStatus.disk.used ?? 0) },
            { label: '可用', value: formatBytes(systemStatus.disk.free ?? 0) },
          ]}
        />

        <MetricCard
          icon={<Network size={18} />}
          title="系统负载"
          value={systemStatus.load?.['1m']?.toFixed(2) ?? '0.00'}
          subtitle="1m / 5m / 15m"
          percent={(systemStatus.load?.['1m'] ?? 0) * 25}
          details={[
            { label: '1m', value: systemStatus.load?.['1m']?.toFixed(2) ?? '0.00' },
            { label: '5m', value: systemStatus.load?.['5m']?.toFixed(2) ?? '0.00' },
            { label: '15m', value: systemStatus.load?.['15m']?.toFixed(2) ?? '0.00' },
            { label: '运行时间', value: formatUptime(systemStatus.uptime ?? 0) },
          ]}
        />

        <div className="col-span-2">
          <NetworkCard status={systemStatus} />
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <ProcessList />
      </div>
    </div>
  );
}

interface MetricCardProps {
  icon: React.ReactNode;
  title: string;
  value: string;
  subtitle: string;
  percent: number;
  details: Array<{ label: string; value: string }>;
}

function MetricCard({ icon, title, value, subtitle, percent, details }: MetricCardProps) {
  const getBarColor = (p: number) => {
    if (p < 50) return 'bg-accent-success';
    if (p < 80) return 'bg-accent-warning';
    return 'bg-accent-error';
  };

  return (
    <Card className="p-4 border-border bg-bg-secondary">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-text-secondary text-sm">
          {icon}
          <span>{title}</span>
        </div>
      </div>
      <div className="text-2xl font-bold mb-1">{value}</div>
      <div className="text-xs text-text-muted mb-2">{subtitle}</div>
      <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden mb-3">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getBarColor(percent)}`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border">
        {details.map((detail, index) => (
          <div key={index} className="flex justify-between text-xs">
            <span className="text-text-muted">{detail.label}</span>
            <span className="text-text-primary font-medium">{detail.value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function NetworkCard({ status }: { status: any }) {
  return (
    <Card className="p-4 border-border bg-bg-secondary">
      <div className="flex items-center gap-2 text-text-secondary text-sm mb-3">
        <Network size={18} />
        <span>网络信息</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">IP 地址</span>
          <span className="text-text-primary font-medium text-right truncate ml-2">{status.ip || '--'}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">MAC 地址</span>
          <span className="text-text-primary font-medium text-right truncate ml-2">{status.mac || '--'}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">接收</span>
          <span className="text-text-primary font-medium">{formatBytes(status.network?.rx ?? 0)}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">发送</span>
          <span className="text-text-primary font-medium">{formatBytes(status.network?.tx ?? 0)}</span>
        </div>
      </div>
    </Card>
  );
}
