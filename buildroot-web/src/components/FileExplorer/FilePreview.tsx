import { useState } from 'react';
import { Edit, Save, X, Download } from 'lucide-react';
import { FileInfo } from '@/types';
import { formatBytes, escapeHtml } from '@/utils/format';

interface FilePreviewProps {
  file: FileInfo | null;
  content: string | null;
  onEdit: () => void;
  onSave: () => void;
  onDownload: () => void;
  onClose: () => void;
}

export function FilePreview({ file, content, onEdit, onSave, onDownload, onClose }: FilePreviewProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editorContent, setEditorContent] = useState(content || '');

  if (!file) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-text-muted bg-bg-primary">
        <span className="text-5xl mb-4 opacity-30">📄</span>
        <span className="text-sm">选择文件预览内容</span>
        <span className="text-xs text-text-muted mt-2">提示：Ctrl+点击多选，Shift+点击范围选择</span>
      </div>
    );
  }

  const handleEdit = () => {
    setIsEditing(true);
    onEdit();
  };

  const handleSave = () => {
    setIsEditing(false);
    onSave();
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditorContent(content || '');
  };

  const renderContent = () => {
    if (isEditing) {
      return (
        <textarea
          value={editorContent}
          onChange={(e) => setEditorContent(e.target.value)}
          className="flex-1 w-full p-4 bg-bg-tertiary text-text-primary font-mono text-sm resize-none outline-none"
          spellCheck={false}
        />
      );
    }

    if (!content) {
      return (
        <div className="flex-1 flex items-center justify-center text-text-muted">
          加载中...
        </div>
      );
    }

    // Simple syntax highlighting
    const highlightedContent = escapeHtml(content);

    return (
      <pre className="flex-1 p-4 overflow-auto bg-bg-primary font-mono text-sm leading-6 whitespace-pre-wrap break-all">
        <div dangerouslySetInnerHTML={{ __html: highlightedContent }} />
      </pre>
    );
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-bg-tertiary">
      <div className="flex items-center justify-between px-4 py-3 bg-bg-secondary border-b border-border">
        <div className="flex items-center gap-3 min-w-0">
          <span className="font-semibold truncate">{file.name}</span>
          <span className="text-xs text-text-muted whitespace-nowrap">{formatBytes(file.size)}</span>
        </div>
        <div className="flex gap-2">
          {!isEditing ? (
            <button
              onClick={handleEdit}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated transition-colors"
            >
              <Edit size={12} />
              编辑
            </button>
          ) : (
            <>
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-primary text-white rounded text-xs hover:bg-accent-primary/90"
              >
                <Save size={12} />
                保存
              </button>
              <button
                onClick={handleCancel}
                className="px-3 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated"
              >
                取消
              </button>
            </>
          )}
          <button
            onClick={onDownload}
            className="px-3 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary text-xs hover:bg-bg-elevated"
          >
            <Download size={12} />
          </button>
          <button
            onClick={onClose}
            className="px-2 py-1.5 bg-bg-tertiary border border-border rounded text-text-secondary hover:bg-bg-elevated"
          >
            <X size={14} />
          </button>
        </div>
      </div>
      {renderContent()}
    </div>
  );
}
