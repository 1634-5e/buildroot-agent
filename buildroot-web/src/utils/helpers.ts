export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function formatDuration(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  if (days > 0) return `${days}天 ${hours}小时`;
  if (hours > 0) return `${hours}小时 ${minutes}分钟`;
  return `${minutes}分钟`;
}

export function getFileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  
  const iconMap: Record<string, string> = {
    // Images
    jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', bmp: '🖼️', svg: '🖼️', webp: '🖼️',
    // Documents
    pdf: '📄', doc: '📝', docx: '📝', txt: '📄', rtf: '📄',
    // Code
    js: '📜', ts: '📜', jsx: '📜', tsx: '📜', py: '🐍', 
    html: '🌐', css: '🎨', json: '📋', xml: '📋', yml: '⚙️', yaml: '⚙️',
    sh: '⚡', bash: '⚡', zsh: '⚡', fish: '⚡',
    c: '🔧', cpp: '🔧', h: '🔧', hpp: '🔧', rs: '🔧', go: '🔧',
    java: '☕', class: '☕', jar: '☕',
    // Archives
    zip: '📦', tar: '📦', gz: '📦', bz2: '📦', xz: '📦', '7z': '📦', rar: '📦',
    // Media
    mp3: '🎵', mp4: '🎬', avi: '🎬', mkv: '🎬', mov: '🎬', wav: '🎵', flac: '🎵',
    // Config
    conf: '⚙️', config: '⚙️', ini: '⚙️', cfg: '⚙️',
    // Database
    db: '🗄️', sqlite: '🗄️', sql: '🗄️',
    // Binary
    bin: '⚙️', exe: '⚙️', dll: '⚙️', so: '⚙️',
    // Log
    log: '📋',
    // Markdown
    md: '📝', markdown: '📝',
  };
  
  return iconMap[ext] || '📄';
}

export function getFileLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  
  const langMap: Record<string, string> = {
    js: 'javascript', ts: 'typescript', jsx: 'jsx', tsx: 'tsx',
    py: 'python', rb: 'ruby', go: 'go', rs: 'rust',
    c: 'c', cpp: 'cpp', h: 'c', hpp: 'cpp',
    java: 'java', kt: 'kotlin', scala: 'scala',
    html: 'html', htm: 'html', xml: 'xml',
    css: 'css', scss: 'scss', sass: 'sass', less: 'less',
    json: 'json', yaml: 'yaml', yml: 'yaml', toml: 'toml',
    sh: 'bash', bash: 'bash', zsh: 'bash', fish: 'fish',
    ps1: 'powershell', ps: 'powershell',
    md: 'markdown', markdown: 'markdown',
    sql: 'sql', dockerfile: 'dockerfile',
    conf: 'ini', ini: 'ini', cfg: 'ini',
    log: 'log',
  };
  
  return langMap[ext] || 'text';
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + '...';
}
