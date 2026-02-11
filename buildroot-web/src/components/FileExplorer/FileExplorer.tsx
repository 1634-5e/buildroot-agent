import { useState, useEffect } from 'react';
import { FileTree } from './FileTree';
import { FilePreview } from './FilePreview';
import { FileInfo } from '@/types';
import { useAppStore } from '@/store/appStore';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { MessageType } from '@/types';

export function FileExplorer() {
  const { currentDevice, fileList } = useAppStore();
  const { send } = useWebSocket();
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);

  // Debug file list changes
  useEffect(() => {
    console.log('FileExplorer: fileList updated:', fileList);
    console.log('FileExplorer: fileList length:', fileList?.length || 0);
  }, [fileList]);

  // Fetch file list when device changes
  useEffect(() => {
    if (!currentDevice) {
      console.log('FileExplorer: No current device, skipping file list request');
      return;
    }

    const deviceId = currentDevice.device_id || currentDevice.id;
    console.log('FileExplorer: Fetching file list for device:', deviceId);
    console.log('FileExplorer: Current device object:', currentDevice);

    const messageData = {
      device_id: deviceId,
      path: '/root',
    };
    
    console.log('FileExplorer: Sending FILE_LIST_REQUEST with data:', messageData);
    send(MessageType.FILE_LIST_REQUEST, messageData);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDevice]);

  const handleFileSelect = (file: FileInfo) => {
    setSelectedFile(file);
    if (!file.isDirectory) {
      // Fetch file content
      const deviceId = currentDevice?.device_id || currentDevice?.id;
      send(MessageType.FILE_REQUEST, {
        device_id: deviceId,
        path: file.path,
      });
      setFileContent('示例文件内容\n\n这是文件的预览内容。');
    }
  };

  const handleRefresh = () => {
    if (!currentDevice) return;

    const deviceId = currentDevice.device_id || currentDevice.id;
    send(MessageType.FILE_LIST_REQUEST, {
      device_id: deviceId,
      path: '/root',
    });
  };

  return (
    <div className="h-full grid grid-cols-[320px_1fr] gap-0 border border-border rounded-lg overflow-hidden">
      <FileTree
        files={fileList}
        selectedFile={selectedFile}
        onFileSelect={handleFileSelect}
        onRefresh={handleRefresh}
      />
      <FilePreview
        file={selectedFile}
        content={fileContent}
        onEdit={() => console.log('Edit mode')}
        onSave={() => console.log('Save file')}
        onDownload={() => console.log('Download file')}
        onClose={() => setSelectedFile(null)}
      />
    </div>
  );
}
