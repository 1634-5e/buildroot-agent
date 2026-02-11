export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}天`);
  if (hours > 0) parts.push(`${hours}小时`);
  if (minutes > 0) parts.push(`${minutes}分钟`);
  if (parts.length === 0) parts.push('< 1分钟');

  return parts.join(' ');
}

export function getFileIcon(filename: string, isDirectory: boolean): string {
  if (isDirectory) return '📁';

  const ext = filename.split('.').pop()?.toLowerCase() || '';

  const iconMap: Record<string, string> = {
    js: '📜',
    ts: '📘',
    jsx: '⚛️',
    tsx: '⚛️',
    py: '🐍',
    sh: '📜',
    json: '📋',
    xml: '📋',
    html: '🌐',
    css: '🎨',
    scss: '🎨',
    md: '📝',
    txt: '📄',
    pdf: '📕',
    zip: '📦',
    tar: '📦',
    gz: '📦',
    png: '🖼️',
    jpg: '🖼️',
    jpeg: '🖼️',
    gif: '🖼️',
    svg: '🎨',
    mp3: '🎵',
    mp4: '🎬',
    mov: '🎬',
    avi: '🎬',
  };

  return iconMap[ext] || '📄';
}

export function getFileType(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';

  const typeMap: Record<string, string> = {
    js: 'javascript',
    ts: 'typescript',
    jsx: 'jsx',
    tsx: 'tsx',
    py: 'python',
    sh: 'shell',
    json: 'json',
    xml: 'xml',
    html: 'html',
    css: 'css',
    scss: 'scss',
    md: 'markdown',
    txt: 'plaintext',
    pdf: 'pdf',
    png: 'image',
    jpg: 'image',
    jpeg: 'image',
    gif: 'image',
    svg: 'svg',
  };

  return typeMap[ext] || 'plaintext';
}

export function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
