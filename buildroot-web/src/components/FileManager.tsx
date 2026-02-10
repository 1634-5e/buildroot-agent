import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { Button } from '@/components/ui/button';
import { MessageType } from '../types';
import { getFileIcon, formatBytes } from '../utils/helpers';

export function FileManager() {
  const {
    fileTreeData,
    expandedDirs,
    selectedFiles,
    previewFile,
    currentDevice,
    toggleExpandedDir,
    toggleFileSelection,
    clearFileSelection,
    setPreviewFile,
    addToast,
  } = useStore();

  const { sendMessage } = useStore.getState();
  const [isLoading, setIsLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (currentDevice) {
      refreshFileTree();
    }
  }, [currentDevice]);

  const refreshFileTree = () => {
    if (!currentDevice) {
      addToast('请先选择设备', 'warning');
      return;
    }
    setIsLoading(true);
    sendMessage(MessageType.FILE_LIST_REQUEST, {
      path: '/',
      request_id: 'tree-' + Date.now(),
    });
    setTimeout(() => setIsLoading(false), 2000); // Fallback timeout
  };

  const loadDirectory = (path: string) => {
    sendMessage(MessageType.FILE_LIST_REQUEST, {
      path,
      request_id: 'tree-' + Date.now(),
    });
  };

  const handleToggleDir = (path: string) => {
    const isExpanded = expandedDirs.has(path);
    toggleExpandedDir(path);
    if (!isExpanded && !fileTreeData[path]) {
      loadDirectory(path);
    }
  };

  const handleFileClick = (path: string, isDir: boolean) => {
    if (isDir) {
      handleToggleDir(path);
    } else {
      clearFileSelection();
      toggleFileSelection(path);
      requestFilePreview(path);
    }
  };

  const requestFilePreview = (path: string) => {
    setPreviewLoading(true);
    sendMessage(MessageType.FILE_REQUEST, { path });
    setTimeout(() => setPreviewLoading(false), 3000); // Fallback timeout
  };

  const renderTree = (path: string = '/', level: number = 0) => {
    const files = fileTreeData[path] || [];
    // const isExpanded = expandedDirs.has(path);

    return (
      <div key={path} style={{ paddingLeft: level * 16 }}>
        {files.map((file) => {
          const filePath = path === '/' ? `/${file.name}` : `${path}/${file.name}`;
          const isSelected = selectedFiles.has(filePath);
          const isFileExpanded = expandedDirs.has(filePath);

          return (
            <div key={filePath}>
              <div
                onClick={() => handleFileClick(filePath, file.is_dir)}
                className={`flex items-center gap-1 px-2 py-1 cursor-pointer rounded-[6px] transition-colors mx-1 my-0.5 ${
                  isSelected ? 'bg-[#6366f1]/25' : 'hover:bg-[#252532]'
                }`}
              >
                {file.is_dir ? (
                  <span 
                    onClick={(e) => {
                      e.stopPropagation();
                      handleToggleDir(filePath);
                    }}
                    className={`text-[10px] text-[#6e6e80] w-4 transition-transform ${isFileExpanded ? 'rotate-90' : ''}`}
                  >
                    ▶
                  </span>
                ) : (
                  <span className="w-4" />
                )}
             <span className="text-base mr-1">{file.is_dir ? (isFileExpanded ? '📂' : '📁') : getFileIcon(file.name)}</span>
             <span className="flex-1 text-sm truncate font-medium hover:text-white transition-colors">{file.name}</span>
              </div>
              {file.is_dir && isFileExpanded && renderTree(filePath, level + 1)}
            </div>
          );
        })}
      </div>
    );
  };

   return (
     <div className="h-full grid grid-cols-[320px_1fr] border border-white/[0.15] rounded-2xl overflow-hidden shadow-2xl">
       {/* File Tree Sidebar */}
       <div className="bg-gradient-to-b from-[#16161e] to-[#0d0d12] border-r border-white/[0.15] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.15] bg-gradient-to-r from-[#16161e]/50 to-[#1a1a24]/50 backdrop-blur-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-gray-400 bg-gradient-to-r from-gray-400 to-gray-600 bg-clip-text text-transparent">文件资源管理器</span>
           <Button 
             onClick={refreshFileTree}
             size="sm"
             variant="ghost"
             className="h-8 w-8 p-0"
             title="刷新"
           >
             🔄
           </Button>
         </div>
          <div className="flex-1 overflow-y-auto py-2 relative">
            {isLoading && (
              <div className="absolute inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-10">
                <div className="text-center">
                  <div className="text-3xl mb-2">🔄</div>
                  <div className="text-sm text-gray-400">加载中...</div>
                </div>
              </div>
            )}
            {renderTree('/')}
          </div>
         {selectedFiles.size > 0 && (
           <div className="px-4 py-3 border-t border-white/[0.15] text-sm text-[#6e6e80] bg-gradient-to-r from-[#1e1e28] to-[#1a1a24] backdrop-blur-sm">
             {selectedFiles.size} 项已选中
           </div>
         )}
       </div>
 
        {/* Preview Panel */}
        <div className="bg-gradient-to-b from-[#0d0d12] to-[#08080c] flex flex-col border-l border-white/[0.15]">
         {!previewFile ? (
           <div className="flex-1 flex flex-col items-center justify-center text-[#6e6e80] animate-fadeSlideIn">
             <div className="text-7xl mb-5 opacity-40 animate-float">📄</div>
             <div className="text-xl font-medium mb-2">选择文件预览内容</div>
             <div className="text-sm opacity-70">提示：点击文件进行预览</div>
           </div>
         ) : (
           <div className="flex flex-col h-full">
             <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.15] bg-gradient-to-r from-[#16161e] to-[#1a1a24]">
               <div className="flex items-center gap-3 min-w-0">
                 <span className="text-lg font-semibold truncate">{previewFile.name}</span>
                 <span className="text-sm text-[#6e6e80] whitespace-nowrap">{formatBytes(previewFile.size)}</span>
               </div>
               <Button 
                 onClick={() => setPreviewFile(null)}
                 variant="outline"
                 size="sm"
                 className="text-sm"
               >
                 ✕ 关闭
               </Button>
             </div>
              <div className="flex-1 overflow-auto p-5 font-mono text-[14px] leading-relaxed whitespace-pre-wrap break-all bg-[#0a0a0f] bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-[#0a0a0f] to-[#08080c] relative">
                {previewLoading && (
                  <div className="absolute inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-10">
                    <div className="text-center">
                      <div className="text-3xl mb-2">📄</div>
                      <div className="text-sm text-gray-400">预览加载中...</div>
                    </div>
                  </div>
                )}
                {previewFile.content}
              </div>
           </div>
         )}
       </div>
     </div>
   );
}
