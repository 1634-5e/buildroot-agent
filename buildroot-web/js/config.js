// ============================================
// Configuration Constants
// ============================================

const MSG_TYPES = {
    HEARTBEAT: 0x01,
    LOG_UPLOAD: 0x03,
    SCRIPT_RECV: 0x04,
    SCRIPT_RESULT: 0x05,
    PTY_CREATE: 0x10,
    PTY_DATA: 0x11,
    PTY_RESIZE: 0x12,
    PTY_CLOSE: 0x13,
    FILE_REQUEST: 0x20,
    FILE_DATA: 0x21,
    FILE_LIST_REQUEST: 0x22,
    FILE_LIST_RESPONSE: 0x23,
    DOWNLOAD_PACKAGE: 0x24,
    CMD_REQUEST: 0x30,
    CMD_RESPONSE: 0x31,
    DEVICE_LIST: 0x50,
    DEVICE_DISCONNECT: 0x51,
    // Update messages
    UPDATE_CHECK: 0x60,
    UPDATE_INFO: 0x61,
    UPDATE_DOWNLOAD: 0x62,
    UPDATE_PROGRESS: 0x63,
    UPDATE_COMPLETE: 0x65,
    UPDATE_ERROR: 0x66,
    UPDATE_ROLLBACK: 0x67,
    UPDATE_REQUEST_APPROVAL: 0x68,
    UPDATE_DOWNLOAD_READY: 0x69,
    UPDATE_APPROVE_INSTALL: 0x6A,
    UPDATE_DENY: 0x6B,
    UPDATE_APPROVE_DOWNLOAD: 0x6C,
    // Ping messages
    PING_STATUS: 0x70
};

const MONITOR_REFRESH_INTERVAL = 5000; // 5 seconds - balance between performance and real-time

const STATE_LABELS = {
    'R': '运行',
    'S': '睡眠',
    'D': '等待',
    'Z': '僵尸',
    'T': '停止',
    'I': '空闲',
    't': '跟踪',
    'X': '死亡'
};

const FILE_ICONS = {
    js: '📜', py: '🐍', sh: '⚡', txt: '📝',
    json: '📋', xml: '📄', html: '🌐', css: '🎨',
    jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️',
    bmp: '🖼️', webp: '🖼️', pdf: '📕',
    zip: '📦', tar: '📦', gz: '📦', rar: '📦',
    log: '📋', md: '📝', conf: '⚙️', cfg: '⚙️',
    ini: '⚙️', yaml: '⚙️', yml: '⚙️'
};

const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'];

const BINARY_EXTS = ['gz', 'zip', 'tar', 'bz2', 'xz', 'rar', '7z', 'exe', 'dll', 'so', 'bin', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'mp3', 'mp4', 'wav', 'avi', 'mkv'];

const BINARY_TYPE_LABELS = {
    'gz': 'GZIP', 'zip': 'ZIP', 'tar': 'TAR', 'bz2': 'BZ2', 'xz': 'XZ',
    'rar': 'RAR', '7z': '7Z', 'exe': 'Executable', 'dll': 'DLL',
    'so': 'Shared Object', 'bin': 'Binary', 'pdf': 'PDF',
    'doc': 'Document', 'docx': 'Document', 'xls': 'Spreadsheet',
    'xlsx': 'Spreadsheet', 'ppt': 'Presentation', 'pptx': 'Presentation',
    'mp3': 'Audio', 'mp4': 'Video', 'wav': 'Audio', 'avi': 'Video', 'mkv': 'Video',
    'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image', 'gif': 'Image',
    'bmp': 'Image', 'webp': 'Image', 'svg': 'Image'
};
