// ============================================
// Utility Functions - Testable Version
// ============================================

// File icons mapping (normally defined elsewhere)
const FILE_ICONS = {
    'txt': '📄',
    'js': '📜',
    'json': '📋',
    'html': '🌐',
    'css': '🎨',
    'py': '🐍',
    'c': '🔧',
    'cpp': '🔧',
    'h': '📦',
    'md': '📝',
    'log': '📋',
    'cfg': '⚙️',
    'sh': '⌨️',
    'zip': '📦',
    'tar': '📦',
    'gz': '📦',
    'jpg': '🖼️',
    'jpeg': '🖼️',
    'png': '🖼️',
    'gif': '🖼️',
    'pdf': '📕',
    'mp4': '🎬',
    'mp3': '🎵',
    'wav': '🎵',
};

function safeGetElement(id) {
    if (typeof document === 'undefined') return null;
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
    if (!bytes || bytes < 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    if (!seconds || seconds < 0) return '0分钟';
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

function getFileIcon(filename) {
    if (!filename) return '📄';
    const parts = filename.split('.');
    const ext = parts.length > 1 ? parts.pop().toLowerCase() : '';
    return FILE_ICONS[ext] || '📄';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = typeof document !== 'undefined' ? document.createElement('div') : null;
    if (!div) return text;
    div.textContent = text;
    return div.innerHTML;
}

function isBinaryFile(bytes) {
    if (!bytes || bytes.length === 0) return false;

    const checkLength = Math.min(32, bytes.length);
    let binaryCount = 0;

    for (let i = 0; i < checkLength; i++) {
        const byte = bytes[i];
        // Count null bytes and control characters (except tab, LF, CR)
        if (byte === 0 || (byte < 32 && byte !== 9 && byte !== 10 && byte !== 13)) {
            binaryCount++;
        }
    }

    // If more than 10% binary characters, consider it binary
    return binaryCount / checkLength > 0.1;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatBytes,
        formatUptime,
        formatDate,
        getFileIcon,
        escapeHtml,
        isBinaryFile,
        debounce,
        throttle,
        safeGetElement,
        safeSetElementHTML,
        FILE_ICONS
    };
}
