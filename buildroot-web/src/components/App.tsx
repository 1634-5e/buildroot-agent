import { useState } from 'react';
import { Monitor, File, ScrollText, Settings, Power } from 'lucide-react';
import { PrimarySidebar } from './Sidebar/PrimarySidebar';
import { DeviceList } from './DeviceList/DeviceList';
import { FileExplorer } from './FileExplorer/FileExplorer';
import { Monitor as MonitorComponent } from './Monitor/Monitor';
import { ScriptRunner } from './ScriptRunner/ScriptRunner';
import { useAppStore } from '@/store/appStore';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { ToastContainer } from './Shared/Toast';
import { MessageType } from '@/types';

type TabType = 'files' | 'monitor' | 'scripts';

export function App() {
  const [currentView, setCurrentView] = useState<'devices'>('devices');
  const [activeTab, setActiveTab] = useState<TabType>('files');
  const [showSettings, setShowSettings] = useState(false);
  const [toasts, setToasts] = useState<Array<{ id: string; message: string; type: 'success' | 'error' | 'warning' | 'info' }>>([]);

  const { currentDevice, devices, setCurrentDevice, isConnected } = useAppStore();
  const { connect, send } = useWebSocket();

  const addToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { id, message, type }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handleDeviceSelect = (device: any) => {
    setCurrentDevice(device);
    setActiveTab('files');

    const deviceId = device.device_id || device.id;
    console.log('Selected device, requesting system_status:', deviceId);
    send(MessageType.CMD_REQUEST, {
      deviceId,
      command: 'system_status',
    });
  };

  const handleDisconnect = () => {
    if (currentDevice) {
      addToast('已断开设备连接', 'info');
      setCurrentDevice(null);
    }
  };

  const handleReboot = () => {
    if (currentDevice && confirm(`确定要重启设备 "${currentDevice.name}" 吗？`)) {
      addToast('重启命令已发送', 'success');
    }
  };

  const tabs = [
    { id: 'files' as TabType, label: '文件', icon: <File size={18} /> },
    { id: 'monitor' as TabType, label: '监控', icon: <Monitor size={18} /> },
    { id: 'scripts' as TabType, label: '脚本', icon: <ScrollText size={18} /> },
  ];

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary">
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      <PrimarySidebar
        currentView={currentView}
        onViewChange={setCurrentView}
        onSettingsClick={() => setShowSettings(true)}
      />

       <DeviceList
         devices={devices}
         selectedDevice={currentDevice}
         onDeviceSelect={handleDeviceSelect}
         onReconnect={connect}
         isConnected={isConnected}
       />

      <main className="flex-1 flex flex-col overflow-hidden">
        {!currentDevice ? (
          <div className="flex-1 flex flex-col items-center justify-center text-text-muted">
            <span className="text-6xl mb-6 opacity-30">📱</span>
            <h2 className="text-2xl font-semibold mb-2">选择设备开始</h2>
            <p className="text-sm">从左侧设备列表选择一个设备以开始管理和监控</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between px-6 py-5 bg-bg-secondary border-b border-border">
              <div className="flex items-center gap-4">
                <span className="text-3xl">📱</span>
                <div>
                  <h2 className="text-xl font-semibold">{currentDevice.name}</h2>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-accent-success/15 text-accent-success rounded-full text-xs font-medium">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent-success" />
                      在线
                    </span>
                    <span className="text-xs text-text-muted">{currentDevice.ip}</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleDisconnect}
                  className="px-3 py-1.5 bg-bg-tertiary border border-border rounded text-text-primary text-sm hover:bg-bg-elevated"
                >
                  断开
                </button>
                <button
                  onClick={handleReboot}
                  className="flex items-center gap-2 px-3 py-1.5 bg-accent-error text-white rounded text-sm hover:bg-accent-error/90"
                >
                  <Power size={14} />
                  重启
                </button>
              </div>
            </div>

            <div className="flex items-center gap-1 px-6 bg-bg-secondary border-b border-border">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
                    activeTab === tab.id
                      ? 'text-accent-primary border-accent-primary'
                      : 'text-text-secondary border-transparent hover:text-text-primary'
                  }`}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-hidden">
              {activeTab === 'files' && <FileExplorer />}
              {activeTab === 'monitor' && <MonitorComponent />}
              {activeTab === 'scripts' && <ScriptRunner />}
            </div>
          </>
        )}
      </main>

      {showSettings && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-bg-secondary border border-border rounded-lg w-full max-w-[520px]">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <div className="text-base font-semibold flex items-center gap-2">
                <Settings size={20} />
                设置
              </div>
              <button
                onClick={() => setShowSettings(false)}
                className="w-8 h-8 flex items-center justify-center text-text-muted hover:bg-bg-tertiary rounded"
              >
                ×
              </button>
            </div>
            <div className="p-5 space-y-5">
              <SettingsForm onClose={() => setShowSettings(false)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SettingsForm({ onClose }: { onClose: () => void }) {
  const {
    wsUrl,
    setWsUrl,
    authToken,
    setAuthToken,
    maxReconnectAttempts,
    setMaxReconnectAttempts,
    refreshInterval,
    setRefreshInterval,
    autoSelectFirst,
    setAutoSelectFirst,
    resetSettings,
  } = useAppStore();

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [tempValues, setTempValues] = useState({
    wsUrl,
    authToken,
    maxReconnectAttempts,
    refreshInterval,
    autoSelectFirst,
  });

  // Validation functions
  const validateWsUrl = (url: string): string | null => {
    if (!url.trim()) return null; // Empty is valid (auto-detect)
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== 'ws:' && parsed.protocol !== 'wss:') {
        return 'URL 必须使用 ws:// 或 wss:// 协议';
      }
      if (!parsed.hostname) {
        return 'URL 必须包含有效的主机名';
      }
      return null;
    } catch {
      return 'URL 格式无效';
    }
  };

  const validateAuthToken = (token: string): string | null => {
    if (token && !token.trim()) {
      return 'Token 不能仅为空格';
    }
    return null;
  };

  const validateMaxReconnect = (value: number): string | null => {
    if (isNaN(value) || value < 1 || value > 50) {
      return '必须在 1 到 50 之间';
    }
    return null;
  };

  const validateRefreshInterval = (value: number): string | null => {
    if (isNaN(value) || value < 1 || value > 60) {
      return '必须在 1 到 60 之间';
    }
    return null;
  };

  const validateAll = (): boolean => {
    const newErrors: Record<string, string> = {};

    const wsUrlError = validateWsUrl(tempValues.wsUrl);
    if (wsUrlError) newErrors.wsUrl = wsUrlError;

    const authTokenError = validateAuthToken(tempValues.authToken);
    if (authTokenError) newErrors.authToken = authTokenError;

    const maxReconnectError = validateMaxReconnect(tempValues.maxReconnectAttempts);
    if (maxReconnectError) newErrors.maxReconnectAttempts = maxReconnectError;

    const refreshIntervalError = validateRefreshInterval(tempValues.refreshInterval);
    if (refreshIntervalError) newErrors.refreshInterval = refreshIntervalError;

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = () => {
    if (!validateAll()) return;

    // Save all values
    setWsUrl(tempValues.wsUrl);
    setAuthToken(tempValues.authToken);
    setMaxReconnectAttempts(tempValues.maxReconnectAttempts);
    setRefreshInterval(tempValues.refreshInterval);
    setAutoSelectFirst(tempValues.autoSelectFirst);
    onClose();
  };

  const handleReset = () => {
    if (confirm('确定要恢复默认设置吗？')) {
      resetSettings();
      setTempValues({
        wsUrl: '',
        authToken: '',
        maxReconnectAttempts: 10,
        refreshInterval: 5,
        autoSelectFirst: true,
      });
      setErrors({});
    }
  };

  const handleCancel = () => {
    // Reset to current store values
    setTempValues({
      wsUrl,
      authToken,
      maxReconnectAttempts,
      refreshInterval,
      autoSelectFirst,
    });
    setErrors({});
    onClose();
  };

  return (
    <>
      <div>
        <label className="block text-sm font-medium text-text-secondary mb-2">
          WebSocket 服务器地址
        </label>
        <input
          type="text"
          value={tempValues.wsUrl}
          onChange={(e) => {
            setTempValues({ ...tempValues, wsUrl: e.target.value });
            const error = validateWsUrl(e.target.value);
            setErrors((prev) => ({ ...prev, wsUrl: error || '' }));
          }}
          placeholder="ws://localhost:8765 或 wss://example.com:8765"
          className={`w-full px-3.5 py-2.5 bg-bg-tertiary border rounded-md text-text-primary text-sm outline-none focus:border-accent-primary font-mono ${
            errors.wsUrl ? 'border-accent-error' : 'border-border'
          }`}
        />
        <div className="text-xs text-text-muted mt-1.5">
          留空则自动检测。HTTPS 网站使用 wss://，HTTP 使用 ws://
        </div>
        {errors.wsUrl && (
          <div className="text-xs text-accent-error mt-1">{errors.wsUrl}</div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-text-secondary mb-2">
          认证 Token
        </label>
        <input
          type="text"
          value={tempValues.authToken}
          onChange={(e) => {
            setTempValues({ ...tempValues, authToken: e.target.value });
            const error = validateAuthToken(e.target.value);
            setErrors((prev) => ({ ...prev, authToken: error || '' }));
          }}
          placeholder="your-auth-token"
          className={`w-full px-3.5 py-2.5 bg-bg-tertiary border rounded-md text-text-primary text-sm outline-none focus:border-accent-primary font-mono ${
            errors.authToken ? 'border-accent-error' : 'border-border'
          }`}
        />
        {errors.authToken && (
          <div className="text-xs text-accent-error mt-1">{errors.authToken}</div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-2">
            最大重连次数
          </label>
          <input
            type="number"
            min="1"
            max="50"
            value={tempValues.maxReconnectAttempts}
            onChange={(e) => {
              const value = parseInt(e.target.value) || 10;
              setTempValues({ ...tempValues, maxReconnectAttempts: value });
              const error = validateMaxReconnect(value);
              setErrors((prev) => ({ ...prev, maxReconnectAttempts: error || '' }));
            }}
            className={`w-full px-3.5 py-2.5 bg-bg-tertiary border rounded-md text-text-primary text-sm outline-none focus:border-accent-primary ${
              errors.maxReconnectAttempts ? 'border-accent-error' : 'border-border'
            }`}
          />
          {errors.maxReconnectAttempts && (
            <div className="text-xs text-accent-error mt-1">{errors.maxReconnectAttempts}</div>
          )}
        </div>
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-2">
            监控刷新间隔 (秒)
          </label>
          <input
            type="number"
            min="1"
            max="60"
            value={tempValues.refreshInterval}
            onChange={(e) => {
              const value = parseInt(e.target.value) || 5;
              setTempValues({ ...tempValues, refreshInterval: value });
              const error = validateRefreshInterval(value);
              setErrors((prev) => ({ ...prev, refreshInterval: error || '' }));
            }}
            className={`w-full px-3.5 py-2.5 bg-bg-tertiary border rounded-md text-text-primary text-sm outline-none focus:border-accent-primary ${
              errors.refreshInterval ? 'border-accent-error' : 'border-border'
            }`}
          />
          {errors.refreshInterval && (
            <div className="text-xs text-accent-error mt-1">{errors.refreshInterval}</div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          id="autoSelect"
          checked={tempValues.autoSelectFirst}
          onChange={(e) => setTempValues({ ...tempValues, autoSelectFirst: e.target.checked })}
          className="w-4 h-4 accent-accent-primary"
        />
        <label htmlFor="autoSelect" className="text-sm text-text-secondary">
          自动选择第一个在线设备
        </label>
      </div>

      <div className="flex justify-end gap-2 pt-4 border-t border-border">
        <button
          onClick={handleReset}
          className="px-4 py-2 bg-bg-tertiary border border-border rounded text-text-primary text-sm hover:bg-bg-elevated"
        >
          恢复默认
        </button>
        <button
          onClick={handleCancel}
          className="px-4 py-2 bg-bg-tertiary border border-border rounded text-text-primary text-sm hover:bg-bg-elevated"
        >
          取消
        </button>
        <button
          onClick={handleSave}
          disabled={Object.keys(errors).length > 0}
          className="px-4 py-2 bg-accent-primary text-white rounded text-sm hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          保存
        </button>
      </div>
    </>
  );
}
