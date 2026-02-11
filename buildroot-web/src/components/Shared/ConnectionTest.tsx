import { useEffect, useState } from 'react';
import { X, CheckCircle, XCircle } from 'lucide-react';

interface ConnectionTestProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ConnectionTest({ isOpen, onClose }: ConnectionTestProps) {
  const [testResults, setTestResults] = useState<Array<{
    name: string;
    status: 'pending' | 'success' | 'error';
    message: string;
  }>>([]);

  useEffect(() => {
    if (!isOpen) return;

    // Run connection tests
    const runTests = async () => {
      const results: Array<{
        name: string;
        status: 'pending' | 'success' | 'error';
        message: string;
      }> = [
        {
          name: '检测 WebSocket 服务器',
          status: 'pending',
          message: '检测中...',
        },
        {
          name: '检查网络连通性',
          status: 'pending',
          message: '检测中...',
        },
        {
          name: '测试 WebSocket 连接',
          status: 'pending',
          message: '检测中...',
        },
      ];

      setTestResults(results);

      // Test 1: Check if server is listening
      try {
        await fetch('http://localhost:8765/', {
          mode: 'no-cors',
        });
        results[0].status = 'success';
        results[0].message = '服务器响应正常';
      } catch (e) {
        results[0].status = 'error';
        results[0].message = '无法连接到服务器，请确认服务器已启动';
      }
      setTestResults([...results]);

      // Test 2: Check network connectivity
      try {
        await fetch(window.location.origin, {
          method: 'HEAD',
          cache: 'no-cache',
        });
        results[1].status = 'success';
        results[1].message = '网络连通正常';
      } catch (e) {
        results[1].status = 'error';
        results[1].message = '网络连接失败';
      }
      setTestResults([...results]);

      // Test 3: Try WebSocket connection
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const hostname = window.location.hostname;
      const port = '8765';
      const wsUrl = `${protocol}//${hostname}:${port}`;

      try {
        const ws = new WebSocket(wsUrl, 'binary');

        const timeout = setTimeout(() => {
          ws.close();
          results[2].status = 'error';
          results[2].message = `连接超时 (5秒)\nURL: ${wsUrl}`;
          setTestResults([...results]);
        }, 5000);

        ws.onopen = () => {
          clearTimeout(timeout);
          results[2].status = 'success';
          results[2].message = `连接成功\nURL: ${wsUrl}`;
          ws.close();
          setTestResults([...results]);
        };

        ws.onerror = (error) => {
          clearTimeout(timeout);
          results[2].status = 'error';
          results[2].message = `连接失败\nURL: ${wsUrl}\n错误: ${(error.target as WebSocket)?.url || 'Unknown'}`;
          setTestResults([...results]);
        };

        ws.onclose = (event) => {
          clearTimeout(timeout);
          if (results[2].status === 'pending') {
            results[2].status = 'error';
            results[2].message = `连接关闭\n代码: ${event.code}\n原因: ${event.reason || 'Unknown'}`;
            setTestResults([...results]);
          }
        };
      } catch (e) {
        results[2].status = 'error';
        results[2].message = `WebSocket 创建失败\n${e instanceof Error ? e.message : 'Unknown error'}`;
        setTestResults([...results]);
      }
    };

    runTests();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-6">
      <div className="bg-bg-secondary border border-border rounded-lg w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="text-base font-semibold">连接诊断</div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center text-text-muted hover:bg-bg-tertiary rounded"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-5 space-y-4">
          {testResults.map((result, index) => (
            <div key={index} className="flex items-start gap-3 p-4 bg-bg-tertiary rounded-lg">
              <div className="flex-shrink-0 mt-0.5">
                {result.status === 'pending' && (
                  <div className="w-5 h-5 border-2 border-text-muted border-t-transparent rounded-full animate-spin" />
                )}
                {result.status === 'success' && (
                  <CheckCircle size={20} className="text-accent-success" />
                )}
                {result.status === 'error' && (
                  <XCircle size={20} className="text-accent-error" />
                )}
              </div>
              <div className="flex-1">
                <div className="font-medium mb-1">{result.name}</div>
                <div className={`text-sm whitespace-pre-wrap ${
                  result.status === 'error' ? 'text-accent-error' : 'text-text-muted'
                }`}>
                  {result.message}
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-border bg-bg-tertiary">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-accent-primary text-white rounded hover:bg-accent-primary/90 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
