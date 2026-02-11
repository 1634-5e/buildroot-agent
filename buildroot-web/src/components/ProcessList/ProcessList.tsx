import { useState } from 'react';
import { Search, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { formatBytes } from '@/utils/format';
import { Process } from '@/types';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';

const STATE_LABELS: Record<string, string> = {
  'R': '运行',
  'S': '睡眠',
  'D': '等待',
  'Z': '僵尸',
  'T': '停止',
  'I': '空闲',
  't': '跟踪',
  'X': '死亡',
};

type SortKey = keyof Pick<Process, 'pid' | 'name' | 'cpu' | 'mem' | 'state'>;

export function ProcessList() {
  const { processes, systemStatus } = useAppStore();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('cpu');
  const [sortAsc, setSortAsc] = useState(false);

  const filtered = processes.filter(p =>
    (p.name || '').toLowerCase().includes(search.toLowerCase()) ||
    String(p.pid || '').includes(search)
  );

  const sorted = [...filtered].sort((a, b) => {
    let va: any = a[sortKey] ?? 0;
    let vb: any = b[sortKey] ?? 0;
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (typeof va === 'string' && typeof vb === 'string') {
      return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    return sortAsc ? va - vb : vb - va;
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === 'name' || key === 'pid');
    }
  };

  const getSortIcon = (key: SortKey) => {
    if (sortKey !== key) return <ArrowUpDown size={12} className="opacity-30" />;
    return sortAsc ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
  };

  const memTotalBytes = systemStatus?.memory?.total ?? 0;
  const stateColor: Record<string, string> = {
    'R': 'bg-accent-success',
    'S': 'bg-accent-primary',
    'D': 'bg-accent-warning',
    'Z': 'bg-accent-error',
    'T': 'bg-text-muted',
  };

  return (
    <div className="bg-bg-secondary border border-border rounded-lg p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-secondary">进程列表</span>
          <span className="px-2 py-0.5 bg-bg-tertiary rounded text-xs text-text-muted">
            {sorted.length}
          </span>
        </div>
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索进程..."
            className="pl-8 pr-3 py-1.5 bg-bg-tertiary border border-border rounded text-xs w-40 focus:outline-none focus:border-accent-primary"
          />
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-text-muted">
          <span className="text-2xl mb-2">{search ? '🔍' : '📊'}</span>
          <span className="text-sm">{search ? '未找到匹配的进程' : '等待进程数据'}</span>
        </div>
      ) : (
        <div className="overflow-auto flex-1">
          <Table>
            <TableHeader className="sticky top-0 bg-bg-secondary">
              <TableRow className="border-border hover:bg-transparent">
                <TableHead onClick={() => handleSort('pid')} className="cursor-pointer hover:text-text-primary text-xs py-2 px-3">
                  <div className="flex items-center gap-1">PID {getSortIcon('pid')}</div>
                </TableHead>
                <TableHead onClick={() => handleSort('name')} className="cursor-pointer hover:text-text-primary text-xs py-2 px-3">
                  <div className="flex items-center gap-1">名称 {getSortIcon('name')}</div>
                </TableHead>
                <TableHead onClick={() => handleSort('cpu')} className="cursor-pointer hover:text-text-primary text-right text-xs py-2 px-3">
                  <div className="flex items-center justify-end gap-1">CPU {getSortIcon('cpu')}</div>
                </TableHead>
                <TableHead onClick={() => handleSort('mem')} className="cursor-pointer hover:text-text-primary text-right text-xs py-2 px-3">
                  <div className="flex items-center justify-end gap-1">内存 {getSortIcon('mem')}</div>
                </TableHead>
                <TableHead onClick={() => handleSort('state')} className="cursor-pointer hover:text-text-primary text-center text-xs py-2 px-3">
                  <div className="flex items-center justify-center gap-1">状态 {getSortIcon('state')}</div>
                </TableHead>
                <TableHead className="text-right text-xs py-2 px-3">时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map(p => {
                const cpu = p.cpu ?? 0;
                const memBytes = (p.mem ?? 0) * 1024;
                const cpuClass = cpu > 50 ? 'bg-accent-error' : cpu > 20 ? 'bg-accent-warning' : 'bg-accent-primary';
                const memPercent = memTotalBytes > 0 ? Math.min((memBytes / memTotalBytes) * 100, 100) : 0;
                const memClass = memPercent > 50 ? 'bg-accent-error' : 'bg-accent-secondary';
                const stateBg = stateColor[p.state] || 'bg-text-muted';

                return (
                  <TableRow key={p.pid} className="border-border hover:bg-bg-tertiary">
                    <TableCell className="text-xs py-2 px-3">{p.pid ?? '--'}</TableCell>
                    <TableCell className="text-xs py-2 px-3 truncate max-w-48" title={p.name}>
                      {p.name ?? '--'}
                    </TableCell>
                    <TableCell className="text-xs py-2 px-3 text-right">
                      <div className="flex flex-col items-end gap-0.5">
                        <span>{cpu.toFixed(1)}%</span>
                        <div className="w-16 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${cpuClass}`} style={{ width: `${Math.min(cpu, 100)}%` }} />
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs py-2 px-3 text-right">
                      <div className="flex flex-col items-end gap-0.5">
                        <span>{formatBytes(memBytes)}</span>
                        <div className="w-16 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${memClass}`} style={{ width: `${memPercent}%` }} />
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs py-2 px-3 text-center">
                      <span className="inline-flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${stateBg}`} />
                        <span>{STATE_LABELS[p.state] || p.state || '--'}</span>
                      </span>
                    </TableCell>
                    <TableCell className="text-xs py-2 px-3 text-right text-text-muted">{p.time || '--'}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
