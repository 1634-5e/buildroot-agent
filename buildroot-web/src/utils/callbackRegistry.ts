import { FileInfo } from '@/types';

type DirectoryCallback = (chunk: number, total: number, files: FileInfo[]) => void;

const directoryCallbackRegistry = new Map<string, DirectoryCallback>();

function normalizePath(path: string): string {
  return path.replace(/\/+$/, '') || '/';
}

export function setDirectoryCallback(path: string, callback: DirectoryCallback): void {
  const normalizedPath = normalizePath(path);
  console.log('[CallbackRegistry] Setting callback for path:', path, '(normalized:', normalizedPath, ')');
  directoryCallbackRegistry.set(normalizedPath, callback);
}

export function getDirectoryCallback(path: string): DirectoryCallback | undefined {
  const normalizedPath = normalizePath(path);
  const callback = directoryCallbackRegistry.get(normalizedPath);
  console.log('[CallbackRegistry] Looking up callback for path:', path, '(normalized:', normalizedPath, ')', 'Found:', !!callback);
  return callback;
}

export function removeDirectoryCallback(path: string): void {
  const normalizedPath = normalizePath(path);
  console.log('[CallbackRegistry] Removing callback for path:', path, '(normalized:', normalizedPath, ')');
  directoryCallbackRegistry.delete(normalizedPath);
}

export function clearDirectoryCallbacks(): void {
  console.log('[CallbackRegistry] Clearing all callbacks');
  directoryCallbackRegistry.clear();
}

export function getRegisteredPaths(): string[] {
  return Array.from(directoryCallbackRegistry.keys());
}