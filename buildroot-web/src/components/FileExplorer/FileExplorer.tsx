import { useState, useEffect } from 'react';
import { FileTree } from './FileTree';
import { FilePreview } from './FilePreview';
import { FileInfo } from '@/types';
import { useAppStore } from '@/store/appStore';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { MessageType } from '@/types';

export function FileExplorer() {
  const { currentDevice, fileList, fileContent, setFileContent, clearFileListChunks, setDirectoryCallback, clearDirectoryData, directoryData, removeDirectoryCallback } = useAppStore();
  const { send } = useWebSocket();
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null);

  // Debug file list changes
  useEffect(() => {
    console.log('FileExplorer: fileList updated:', fileList);
    console.log('FileExplorer: fileList length:', fileList?.length || 0);
    console.log('FileExplorer: fileList type:', typeof fileList);
    console.log('FileExplorer: fileList isArray:', Array.isArray(fileList));
    if (fileList && fileList.length > 0) {
      console.log('FileExplorer: First few files:', fileList.slice(0, 3));
    }
  }, [fileList]);

  // Fetch file list when device changes
  useEffect(() => {
    if (!currentDevice) {
      console.log('FileExplorer: No current device, skipping file list request');
      return;
    }

    clearFileListChunks();
    clearDirectoryData();

    const deviceId = currentDevice.device_id || currentDevice.id;
    console.log('FileExplorer: Fetching file list for device:', deviceId);
    console.log('FileExplorer: Current device object:', currentDevice);

    const messageData = {
      device_id: deviceId,
      action: 'list',
      path: '/',
    };

    console.log('FileExplorer: Sending FILE_LIST_REQUEST with data:', messageData);
    send(MessageType.FILE_LIST_REQUEST, messageData);
  }, [currentDevice, send]);

  const handleFileSelect = (file: FileInfo) => {
    console.log('=== File select START ===');
    console.log('Selected file:', file.name, 'path:', file.path, 'isDirectory:', file.isDirectory);

    setSelectedFile(file);

    if (!file.isDirectory) {
      setFileContent(null);
      const deviceId = currentDevice?.device_id || currentDevice?.id;
      console.log('Requesting file content for:', file.path, 'device:', deviceId);
      send(MessageType.FILE_REQUEST, {
        device_id: deviceId,
        action: 'read',
        filepath: file.path,
        offset: 0,
        length: 0,
      });
    }
    console.log('=== File select END ===');
  };

  const handleRefresh = () => {
    if (!currentDevice) return;

    clearFileListChunks();
    clearDirectoryData();

    const deviceId = currentDevice.device_id || currentDevice.id;
    send(MessageType.FILE_LIST_REQUEST, {
      device_id: deviceId,
      action: 'list',
      path: '/',
    });
  };

  const handleDirectoryExpand = (path: string, onDataReceived: (files: FileInfo[]) => void) => {
    console.log('=== Directory expand START ===');
    console.log('Path:', path);
    console.log('Current callbacks:', useAppStore.getState().directoryCallbacks);
    console.log('Current directoryData:', useAppStore.getState().directoryData);

    if (!currentDevice) {
      console.warn('No current device');
      onDataReceived([]);
      return;
    }

    const cachedData = directoryData.get(path);
    if (cachedData && cachedData.length > 0) {
      console.log('Using cached data for:', path, 'files:', cachedData.length);
      onDataReceived(cachedData);
      return;
    }

    console.log('Setting callback for path:', path);
    setDirectoryCallback(path, (chunk, total, files) => {
      console.log(`>>> Chunk received for ${path}: ${chunk + 1}/${total}, files: ${files.length}`);
      
      const existing = useAppStore.getState().directoryData.get(path) || [];
      const allFiles = [...existing, ...files];
      useAppStore.getState().setDirectoryData(path, allFiles);

      if (chunk + 1 >= total) {
        const finalData = useAppStore.getState().directoryData.get(path) || [];
        console.log(`>>> All chunks complete for ${path}, total files: ${finalData.length}`);
        console.log(`>>> Files:`, finalData.map(f => f.path));
        onDataReceived(finalData);
        removeDirectoryCallback(path);
      }
    });

    const deviceId = currentDevice.device_id || currentDevice.id;
    send(MessageType.FILE_LIST_REQUEST, {
      device_id: deviceId,
      action: 'list',
      path: path,
    });
    console.log('=== Directory expand END (sent request) ===');
  };

  return (
    <div className="h-full grid grid-cols-[320px_1fr] border border-border rounded-lg overflow-hidden">
      <div className="flex flex-col h-full overflow-hidden">
        {/* Debug info */}
        <div className="text-xs text-muted-foreground p-2 border-b">
          Debug: fileList.length = {fileList?.length || 0}, currentDevice = {currentDevice?.device_id || 'none'}
        </div>
        <FileTree
          files={fileList}
          selectedFile={selectedFile}
          onFileSelect={handleFileSelect}
          onRefresh={handleRefresh}
          onDirectoryExpand={(path, callback) => handleDirectoryExpand(path, callback)}
        />
      </div>
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
