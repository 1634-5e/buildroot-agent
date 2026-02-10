import { useState } from 'react';
import { useStore } from '../store';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { MessageType } from '../types';

export function ScriptManager() {
  const {
    scriptEditorContent,
    scriptResult,
    isScriptRunning,
    currentDevice,
    setScriptEditorContent,
    setScriptResult,
    setIsScriptRunning,
    addToast,
  } = useStore();

  const { sendMessage } = useStore.getState();
  const [showModal, setShowModal] = useState(false);

  const scriptTemplates = [
    {
      name: '系统信息',
      content: `#!/bin/bash
# 系统信息检查脚本
echo "=== 系统信息 ==="
uname -a
echo ""
echo "=== 内存使用 ==="
free -h
echo ""
echo "=== 磁盘使用 ==="
df -h
echo ""
echo "=== CPU 使用情况 ==="
top -bn1 | head -20`,
    },
    {
      name: '网络状态',
      content: `#!/bin/bash
# 网络状态检查
echo "=== 网络接口 ==="
ip addr show
echo ""
echo "=== 路由表 ==="
ip route
echo ""
echo "=== 网络连接 ==="
ss -tuln`,
    },
    {
      name: '进程监控',
      content: `#!/bin/bash
# 进程监控脚本
echo "=== TOP 10 进程 ==="
ps aux | sort -rk 3 | head -10
echo ""
echo "=== 内存占用 TOP 10 ==="
ps aux | sort -rk 4 | head -10`,
    },
  ];

  const applyTemplate = (template: typeof scriptTemplates[0]) => {
    setScriptEditorContent(template.content);
    addToast(`已应用模板: ${template.name}`, 'success');
  };

  const handleRunScript = () => {
    if (!currentDevice) {
      addToast('请先选择设备', 'warning');
      return;
    }
    
    if (!scriptEditorContent.trim()) {
      addToast('脚本内容不能为空', 'warning');
      return;
    }

    setIsScriptRunning(true);
    setScriptResult(null);
    setShowModal(true);
    
    sendMessage(MessageType.SCRIPT_RECV, {
      script: scriptEditorContent,
    });
  };

  const handleCopyOutput = () => {
    if (scriptResult) {
      const output = `${scriptResult.stdout}${scriptResult.stderr ? '\n' + scriptResult.stderr : ''}`;
      navigator.clipboard.writeText(output);
      addToast('已复制到剪贴板', 'success');
    }
  };

   return (
      <div className="h-full max-w-4xl">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h3 className="text-lg font-semibold mb-1 bg-gradient-to-r from-white to-[#a0a0c0] bg-clip-text text-transparent">执行脚本</h3>
            <div className="text-sm text-[#6e6e80]">在设备上执行 Shell 脚本</div>
          </div>
          <div className="flex gap-3">
            <div className="flex gap-2">
              {scriptTemplates.map((template, index) => (
                <Button
                  key={index}
                  onClick={() => applyTemplate(template)}
                  variant="outline"
                  size="sm"
                  className="text-xs px-3 py-1.5"
                  title={`应用模板: ${template.name}`}
                >
                  {template.name}
                </Button>
              ))}
            </div>
            <Button 
              onClick={handleRunScript}
              disabled={isScriptRunning || !currentDevice}
              className="px-6 py-3 bg-gradient-to-b from-[#6366f1] to-[#4f46e5] text-white rounded-xl text-sm font-medium hover:from-[#5558e6] hover:to-[#4338ca] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-[0_4px_12px_rgba(99,102,241,0.3)]"
            >
              {isScriptRunning ? '⏳' : '▶️'} {isScriptRunning ? '执行中...' : '运行脚本'}
            </Button>
          </div>
        </div>
       
       <Textarea
         value={scriptEditorContent}
         onChange={(e) => setScriptEditorContent(e.target.value)}
         placeholder="#!/bin/bash&#10;&#10;# 在此输入脚本代码&#10;echo 'Hello, World!'&#10;uname -a"
         className="w-full h-[calc(100%-100px)] min-h-[320px] p-5 bg-gradient-to-br from-[#1e1e28] to-[#16161e] border border-white/[0.15] rounded-xl text-sm font-mono resize-y shadow-[inset_0_2px_8px_rgba(0,0,0,0.3)]"
         spellCheck={false}
       />

       {/* Script Result Modal */}
       {showModal && (
         <div 
           className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-6 animate-fadeIn"
           onClick={() => setShowModal(false)}
         >
           <div 
             className="bg-gradient-to-b from-[#16161e] to-[#0d0d12] rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden border border-white/[0.15] shadow-2xl"
             onClick={(e) => e.stopPropagation()}
           >
             <div className="flex justify-between items-center px-6 py-5 border-b border-white/[0.15] bg-gradient-to-r from-[#16161e]/80 to-[#1a1a24]/80 backdrop-blur-sm">
               <div className="text-lg font-semibold bg-gradient-to-r from-white to-[#a0a0c0] bg-clip-text text-transparent">📜 脚本执行结果</div>
               <button 
                 onClick={() => setShowModal(false)}
                 className="text-2xl text-[#6e6e80] hover:text-white w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gradient-to-b hover:from-[#252532] hover:to-[#1e1e28] transition-all duration-200"
               >
                 ×
               </button>
             </div>
             <div className="px-6 py-6 max-h-[50vh] overflow-y-auto">
               <div className="flex items-center gap-3 mb-5">
                 <span className="text-xl">{isScriptRunning ? '⏳' : scriptResult?.exit_code === 0 ? '✓' : '✕'}</span>
                 <span className="text-base font-medium">{isScriptRunning ? '执行中...' : scriptResult ? (scriptResult.exit_code === 0 ? '执行成功' : '执行失败') : '等待执行'}</span>
                 {!isScriptRunning && scriptResult && (
                   <span className="ml-auto text-sm text-[#6e6e80] bg-[#1e1e28] px-3 py-1 rounded-lg">
                     退出码: {scriptResult.exit_code}
                   </span>
                 )}
               </div>
               <pre className="bg-gradient-to-br from-[#0d0d12] to-[#0a0a0f] p-5 rounded-xl font-mono text-sm overflow-x-auto whitespace-pre-wrap break-all border border-white/[0.1] shadow-inner">
                 {isScriptRunning ? '等待执行结果...' : scriptResult ? (
                   <>
                     {scriptResult.stdout}
                     {scriptResult.stderr && (
                       <span className="text-[#ef4444]">{'\n'}{scriptResult.stderr}</span>
                     )}
                   </>
                 ) : '无输出'}
               </pre>
             </div>
             <div className="flex justify-end gap-4 px-6 py-5 border-t border-white/[0.15] bg-gradient-to-r from-[#16161e]/50 to-[#1a1a24]/50 backdrop-blur-sm">
               <Button 
                 onClick={() => setShowModal(false)}
                 variant="outline"
                 className="px-5 py-2.5 text-sm"
               >
                 关闭
               </Button>
               <Button 
                 onClick={handleCopyOutput}
                 disabled={!scriptResult || isScriptRunning}
                 className="px-5 py-2.5 text-sm"
               >
                 📋 复制输出
               </Button>
             </div>
           </div>
         </div>
       )}
     </div>
   );
}
