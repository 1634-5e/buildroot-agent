import { useState } from 'react';
import { Play, Copy, X } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { MessageType } from '@/types';

export function ScriptRunner() {
  const [script, setScript] = useState(`#!/bin/bash

# 在此输入脚本代码
echo 'Hello, World!'
uname -a`);
  const [output, setOutput] = useState('');
  const [status, setStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [exitCode, setExitCode] = useState<number | null>(null);
  const [showOutput, setShowOutput] = useState(false);

  const { currentDevice } = useAppStore();
  const { send } = useWebSocket();

  const handleRun = () => {
    if (!currentDevice) {
      alert('请先选择设备');
      return;
    }

    setStatus('running');
    setOutput('正在执行...\n');
    setShowOutput(true);

    send(MessageType.SCRIPT_RECV, {
      deviceId: currentDevice.device_id || currentDevice.id || '',
      script,
    });
  };

  const handleCopyOutput = () => {
    navigator.clipboard.writeText(output);
  };

  const handleCloseOutput = () => {
    setShowOutput(false);
    setOutput('');
    setStatus('idle');
    setExitCode(null);
  };

  return (
    <div className="flex flex-col">
      <div className="flex justify-between items-center mb-5">
        <div>
          <h3 className="text-base font-semibold mb-1">执行脚本</h3>
          <div className="text-sm text-text-muted">在设备上执行 Shell 脚本</div>
        </div>
        <button
          onClick={handleRun}
          disabled={!currentDevice || status === 'running'}
          className="flex items-center gap-2 px-4 py-2 bg-accent-primary text-white rounded-md text-sm hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play size={16} />
          运行脚本
        </button>
      </div>

      <textarea
        value={script}
        onChange={(e) => setScript(e.target.value)}
        placeholder="#!/bin/bash"
        className="w-full h-80 p-4 bg-bg-tertiary border border-border rounded-md text-text-primary font-mono text-sm resize-none outline-none focus:border-accent-primary"
        spellCheck={false}
      />

      {showOutput && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-bg-secondary border border-border rounded-lg w-full max-w-xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <div className="text-base font-semibold">📜 脚本执行结果</div>
              <button
                onClick={handleCloseOutput}
                className="w-8 h-8 flex items-center justify-center text-text-muted hover:bg-bg-tertiary rounded"
              >
                <X size={20} />
              </button>
            </div>
            <div className="flex items-center gap-2 mb-4 p-5 pb-0">
              <span>{status === 'running' ? '⏳' : status === 'success' ? '✓' : '✕'}</span>
              <span>
                {status === 'running' ? '执行中...' : status === 'success' ? '执行成功' : '执行失败'}
              </span>
              <span className="ml-auto text-xs text-text-muted">
                {exitCode !== null && `退出码: ${exitCode}`}
              </span>
            </div>
            <pre className="flex-1 p-5 bg-bg-primary font-mono text-sm overflow-auto whitespace-pre-wrap break-all">
              {output}
            </pre>
            <div className="flex justify-end gap-2 p-4 border-t border-border">
              <button
                onClick={handleCloseOutput}
                className="px-4 py-2 bg-bg-tertiary border border-border rounded text-text-primary text-sm hover:bg-bg-elevated"
              >
                关闭
              </button>
              <button
                onClick={handleCopyOutput}
                className="flex items-center gap-2 px-4 py-2 bg-accent-primary text-white rounded text-sm hover:bg-accent-primary/90"
              >
                <Copy size={14} />
                复制输出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
