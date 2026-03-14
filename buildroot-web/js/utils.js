// ============================================
// Utility Functions
// ============================================

function safeGetElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`Element with id '${id}' not found`);
        return null;
    }
    return element;
}

function safeSetElementHTML(id, html) {
    const element = safeGetElement(id);
    if (element) {
        element.innerHTML = html;
        return true;
    }
    return false;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}天 ${hours}小时`;
    if (hours > 0) return `${hours}小时 ${minutes}分钟`;
    return `${minutes}分钟`;
}

function formatDate(timestamp) {
    if (!timestamp) return '--';
    return new Date(timestamp * 1000).toLocaleString();
}

function showToast(message, type = 'info') {
    const container = safeGetElement('toastContainer');
    if (!container) {
        console.warn('toastContainer element not found, cannot show toast:', message);
        return;
    }

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span style="font-size: 20px;">${icons[type]}</span>
        <span>${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    return FILE_ICONS[ext] || '📄';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function isBinaryFile(bytes) {
    if (!bytes || bytes.length === 0) return false;

    const checkLength = Math.min(32, bytes.length);
    let binaryCount = 0;

    for (let i = 0; i < checkLength; i++) {
        const byte = bytes[i];
        const isPrintable = (byte >= 32 && byte <= 126) || (byte >= 9 && byte <= 13);
        if (!isPrintable) {
            binaryCount++;
        }
    }

    return (binaryCount / checkLength) > 0.15;
}

function isTextFile(content) {
    if (!content || content.length === 0) return true;

    const sample = content.substring(0, 1000);
    const length = sample.length;
    let binaryCount = 0;

    for (let i = 0; i < length; i++) {
        const code = sample.charCodeAt(i);
        if (code < 9 || (code > 13 && code < 32) || code > 65535) {
            binaryCount++;
        }
    }

    return (binaryCount / length) < 0.3;
}

function isFileEditable(filename, content) {
    if (!isTextFile(content)) {
        return false;
    }

    try {
        const modeList = ace.require('ace/ext/modelist');
        const mode = modeList.getModeForPath(filename);
        return mode && mode.mode && mode.mode !== 'ace/mode/text';
    } catch (e) {
        console.warn('Ace modelist 检测失败:', e);
        return isTextFile(content);
    }
}

function getAceLanguageMode(filename) {
    try {
        const modeList = ace.require('ace/ext/modelist');
        const mode = modeList.getModeForPath(filename);
        return mode?.mode || 'ace/mode/text';
    } catch (e) {
        console.warn('获取 Ace 模式失败:', e);
        return 'ace/mode/text';
    }
}

function getFileTypeLabel(filename) {
    try {
        const modeList = ace.require('ace/ext/modelist');
        const mode = modeList.getModeForPath(filename);
        return mode?.caption || 'Text';
    } catch (e) {
        return 'Text';
    }
}

function getFileExtension(filename) {
    if (!filename) return '';
    const parts = filename.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
}

function getFileType(filename) {
    if (!filename) return 'plaintext';
    const ext = filename.split('.').pop().toLowerCase();
    const typeMap = {
        'js': 'JavaScript', 'ts': 'TypeScript', 'py': 'Python', 'sh': 'Shell',
        'bash': 'Shell', 'zsh': 'Shell', 'json': 'JSON', 'xml': 'XML',
        'html': 'HTML', 'htm': 'HTML', 'css': 'CSS', 'md': 'Markdown',
        'yaml': 'YAML', 'yml': 'YAML', 'toml': 'TOML', 'ini': 'INI',
        'conf': 'Config', 'cfg': 'Config', 'c': 'C', 'cpp': 'C++',
        'h': 'C Header', 'hpp': 'C++ Header', 'java': 'Java', 'go': 'Go', 'rs': 'Rust',
        'rb': 'Ruby', 'php': 'PHP', 'lua': 'Lua', 'sql': 'SQL',
        'log': 'Log', 'txt': 'Plain Text'
    };
    return typeMap[ext] || 'Plain Text';
}

function loadSettings() {
    try {
        const saved = localStorage.getItem('buildroot-agent-settings');
        return saved ? JSON.parse(saved) : {};
    } catch (e) {
        return {};
    }
}

function saveSettingsData(settings) {
    try {
        localStorage.setItem('buildroot-agent-settings', JSON.stringify(settings));
    } catch (e) {
        console.warn('无法保存设置到 localStorage:', e);
    }
}

function applySettings(settings) {
    if (!settings) settings = loadSettings();

    maxReconnectAttempts = settings.maxReconnectAttempts || 10;

    const newInterval = settings.monitorRefreshInterval || 5000;
    if (newInterval !== MONITOR_REFRESH_INTERVAL) {
        if (monitorRefreshInterval) {
            clearInterval(monitorRefreshInterval);
            monitorRefreshInterval = setInterval(() => {
                if (currentTab === 'monitor' && currentDevice && isMonitorAutoRefreshEnabled) {
                    refreshSystemStatus();
                }
            }, newInterval);
        }
    }
}

function resetSettings() {
    try {
        localStorage.removeItem('buildroot-agent-settings');
    } catch (e) {}
    loadSettingsToForm();
    showToast('已恢复默认设置', 'info');
}

function debugFileListChunks() {
    for (const [request_id, chunkData] of Object.entries(fileListChunks)) {
    }
}
