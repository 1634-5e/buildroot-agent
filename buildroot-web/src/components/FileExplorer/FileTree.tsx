import { useState } from 'react';
import { RefreshCw, FilePlus, Upload, Download } from 'lucide-react';
import { FileInfo } from '@/types';
import { getFileIcon } from '@/utils/format';

interface FileTreeProps {
  files: FileInfo[];
  selectedFile: FileInfo | null;
  onFileSelect: (file: FileInfo) => void;
  onRefresh: () => void;
}

interface FileTreeNodeProps {
  file: FileInfo;
  level: number;
  selectedFile: FileInfo | null;
  onFileSelect: (file: FileInfo) => void;
}

function FileTreeNode({ file, level, selectedFile, onFileSelect }: FileTreeNodeProps) {
  const [expanded, setExpanded] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    if (e.ctrlKey || e.metaKey) {
      // Multi-select (not implemented yet)
    } else {
      onFileSelect(file);
    }

    if (file.isDirectory) {
      setExpanded(!expanded);
    }
  };

  const hasChildren = file.children && file.children.length > 0;

  return (
    <div>
      <div
        onClick={handleClick}
        className={`flex items-center gap-1 py-1 px-2 cursor-pointer rounded hover:bg-bg-tertiary transition-colors select-none ${
          selectedFile?.path === file.path ? 'bg-accent-primary/25' : ''
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
      >
        <span
          className={`w-4 h-4 flex items-center justify-center text-[10px] text-text-muted transition-transform ${
            expanded ? 'rotate-90' : ''
          } ${!hasChildren ? 'invisible' : ''}`}
        >
          ▶
        </span>
        <span className="w-4 text-center">{getFileIcon(file.name, file.isDirectory)}</span>
        <span className="flex-1 truncate text-sm">{file.name}</span>
      </div>

      {expanded && file.children && (
        <div>
          {file.children.map((child) => (
            <FileTreeNode
              key={child.path}
              file={child}
              level={level + 1}
              selectedFile={selectedFile}
              onFileSelect={onFileSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({ files, selectedFile, onFileSelect, onRefresh }: FileTreeProps) {
  const [newFileName, setNewFileName] = useState('');
  const [showNewFileDialog, setShowNewFileDialog] = useState(false);

  return (
    <div className="w-80 bg-bg-secondary border-r border-border flex flex-col">
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border">
        <span className="text-xs font-semibold uppercase text-text-muted tracking-wider">
          资源管理器
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => setShowNewFileDialog(true)}
            className="w-7 h-7 flex items-center justify-center text-text-muted hover:bg-bg-tertiary rounded transition-colors"
            title="新建文件"
          >
            <FilePlus size={14} />
          </button>
          <button
            className="w-7 h-7 flex items-center justify-center text-text-muted hover:bg-bg-tertiary rounded transition-colors"
            title="上传文件"
          >
            <Upload size={14} />
          </button>
          <button
            className="w-7 h-7 flex items-center justify-center text-text-muted hover:bg-bg-tertiary rounded transition-colors"
            title="下载选中"
          >
            <Download size={14} />
          </button>
          <button
            onClick={onRefresh}
            className="w-7 h-7 flex items-center justify-center text-text-muted hover:bg-bg-tertiary rounded transition-colors"
            title="刷新"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {files.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-text-muted">
            <span className="text-4xl mb-4 opacity-50">📁</span>
            <span className="text-sm">文件夹为空</span>
          </div>
        ) : (
          files.map((file) => (
            <FileTreeNode
              key={file.path}
              file={file}
              level={0}
              selectedFile={selectedFile}
              onFileSelect={onFileSelect}
            />
          ))
        )}
      </div>

      {showNewFileDialog && (
        <div className="p-3 border-t border-border bg-bg-tertiary">
          <input
            type="text"
            placeholder="输入文件路径..."
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            className="w-full px-3 py-2 bg-bg-primary border border-border rounded text-text-primary text-xs font-mono outline-none focus:border-accent-primary"
            autoFocus
          />
          <div className="flex justify-end gap-2 mt-2">
            <button
              onClick={() => setShowNewFileDialog(false)}
              className="px-3 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated"
            >
              取消
            </button>
            <button className="px-3 py-1.5 bg-accent-primary text-white rounded text-xs hover:bg-accent-primary/90">
              创建
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
