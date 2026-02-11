import { useState, useEffect } from 'react';
import { RefreshCw, FilePlus, Upload, Download, Minimize2, Maximize2 } from 'lucide-react';
import { FileInfo } from '@/types';
import { getFileIcon } from '@/utils/format';
import { useAppStore } from '@/store/appStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

interface FileTreeNodeProps {
  file: FileInfo;
  level: number;
  selectedFile: FileInfo | null;
  onFileSelect: (file: FileInfo) => void;
  onDirectoryExpand: (path: string, onDataReceived: (files: FileInfo[]) => void) => void;
}

function FileTreeNode({ file, level, selectedFile, onFileSelect, onDirectoryExpand }: FileTreeNodeProps) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [localChildren, setLocalChildren] = useState<FileInfo[]>(file.children || []);
  const [hasFetched, setHasFetched] = useState(false);
  const directoryData = useAppStore(state => state.directoryData);

  const handleDataReceived = (files: FileInfo[]) => {
    console.log('Directory data received callback for', file.path, ':', files.length, 'files:', files);
    setLocalChildren(files);
    setExpanded(true);
    setLoading(false);
    setHasFetched(true);
  };

  const handleClick = () => {
    console.log(`=== FileTreeNode click: ${file.path} (isDirectory: ${file.isDirectory}) ===`);
    onFileSelect(file);

    if (file.isDirectory) {
      const cached = directoryData.get(file.path);
      const hasCachedData = cached && cached.length > 0;

      console.log('Directory click details:');
      console.log('  - Path:', file.path);
      console.log('  - Level:', level);
      console.log('  - Expanded:', expanded);
      console.log('  - HasFetched:', hasFetched);
      console.log('  - Has children:', !!file.children?.length);
      console.log('  - Has cached data:', hasCachedData);
      console.log('  - Cached data:', cached);

      if (!expanded && !hasFetched && !file.children?.length && !hasCachedData) {
        console.log('>>> Fetching directory data for:', file.path);
        setLoading(true);
        onDirectoryExpand(file.path, handleDataReceived);
      } else if (!expanded && hasCachedData && !hasFetched) {
        console.log('>>> Using cached data for:', file.path);
        console.log('  Cached files:', cached.map(f => f.path));
        setLocalChildren(cached);
        setExpanded(true);
        setHasFetched(true);
      } else {
        console.log('>>> Toggling expansion for:', file.path, expanded ? 'collapsed' : 'expanded');
        setExpanded(!expanded);
      }
    }
  };

  const hasChildren = localChildren && localChildren.length > 0;

  return (
    <div>
      <div
        onClick={handleClick}
        className={cn(
          "group flex items-center select-none cursor-pointer",
          "hover:bg-accent/60",
          selectedFile?.path === file.path ? "bg-accent/50" : ""
        )}
        style={{ 
          paddingLeft: `${level * 16 + 8}px`,
          height: '22px'
        }}
      >
        <span 
          className="mr-2 inline-flex items-center justify-center"
          style={{ width: '16px', height: '16px' }}
        >
          <span className="text-[15px] leading-none">{getFileIcon(file.name, file.isDirectory)}</span>
        </span>
        <span className="truncate text-[13px]">{file.name}</span>
      </div>

      {file.isDirectory && (hasChildren || loading) && (
        <div>
          {loading ? (
            <div 
              className="text-muted-foreground/50 text-[13px]" 
              style={{ paddingLeft: `${(level + 1) * 16 + 8}px`, height: '22px' }}
            >
              加载中...
            </div>
          ) : (
            localChildren?.map((child) => (
              <FileTreeNode
                key={child.path}
                file={child}
                level={level + 1}
                selectedFile={selectedFile}
                onFileSelect={onFileSelect}
                onDirectoryExpand={onDirectoryExpand}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

interface FileTreeProps {
  files: FileInfo[];
  selectedFile: FileInfo | null;
  onFileSelect: (file: FileInfo) => void;
  onRefresh: () => void;
  onDirectoryExpand: (path: string, onDataReceived: (files: FileInfo[]) => void) => void;
}

export function FileTree({ files, selectedFile, onFileSelect, onRefresh, onDirectoryExpand }: FileTreeProps) {
  const [newFileName, setNewFileName] = useState('');
  const [showNewFileDialog, setShowNewFileDialog] = useState(false);
  const [allCollapsed, setAllCollapsed] = useState(false);

  // Debug files prop
  useEffect(() => {
    console.log('FileTree: files prop updated:', files);
    console.log('FileTree: files length:', files?.length || 0);
    console.log('FileTree: files type:', typeof files);
    console.log('FileTree: files isArray:', Array.isArray(files));
    if (files && files.length > 0) {
      console.log('FileTree: First few files:', files.slice(0, 3));
    }
  }, [files]);

  const toggleAll = () => {
    setAllCollapsed(!allCollapsed);
    // TODO: Implement actual collapse/expand of all nodes
  };

  return (
    <div className="w-80 bg-background border-r flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/80">
          文件
        </span>
        <div className="flex gap-0.5">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:bg-accent/60"
            onClick={toggleAll}
            title={allCollapsed ? "展开全部" : "折叠全部"}
          >
            {allCollapsed ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:bg-accent/60"
            onClick={() => setShowNewFileDialog(true)}
            title="新建文件"
          >
            <FilePlus size={14} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:bg-accent/60"
            title="上传文件"
          >
            <Upload size={14} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:bg-accent/60"
            title="下载选中"
          >
            <Download size={14} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:bg-accent/60"
            onClick={onRefresh}
            title="刷新"
          >
            <RefreshCw size={14} />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {files.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground/40">
            <span className="text-3xl mb-3 opacity-30">📁</span>
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
              onDirectoryExpand={onDirectoryExpand}
            />
          ))
        )}
      </div>

      {showNewFileDialog && (
        <div className="p-3 border-t bg-muted/30 flex-shrink-0">
          <Input
            placeholder="输入文件路径..."
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            className="mb-2.5 text-xs font-mono bg-background"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                setShowNewFileDialog(false);
              }
            }}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowNewFileDialog(false)}
            >
              取消
            </Button>
            <Button size="sm">创建</Button>
          </div>
        </div>
      )}
    </div>
  );
}
