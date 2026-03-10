# Postmortem: 前端问题

**严重程度**: 🟢 P2 - 中等
**发现时间**: 2026-02-13 ~ 2026-02-23
**修复提交**: `77527af`, `a9bea10`, `69bfbc5`, `7ff02a5`
**影响组件**: Web 前端 (Vanilla JS + Vue)

---

## 问题概述

前端存在多处用户体验问题，包括异步加载竞态、UI 闪烁、数据显示延迟。

---

## 1. ace.js 异步加载竞态

### 根因分析

用户快速点击目录时，ace.js 编辑器未加载完成，导致错误：

```javascript
// 问题代码
document.addEventListener('DOMContentLoaded', function() {
    initAceEditor();  // ace.js 可能还没加载！
});

function initAceEditor() {
    var editor = ace.edit("editor");  // ace 可能未定义
    // ...
}
```

**错误日志**：
```
Global error: null
Uncaught TypeError: ace is not defined
```

### 修复方案

```javascript
// 轮询等待 ace 加载
document.addEventListener('DOMContentLoaded', function() {
    var attempts = 0;
    var maxAttempts = 50;  // 5 秒
    
    function tryInit() {
        if (window.ace) {
            initAceEditor();
        } else if (attempts < maxAttempts) {
            attempts++;
            setTimeout(tryInit, 100);
        } else {
            console.error('ace.js failed to load');
        }
    }
    tryInit();
});

// 在所有使用 ace 的地方添加检查
function isEditorDirty() {
    if (!window.ace || !window.editor) {
        return false;  // 安全返回
    }
    return !window.editor.session.getUndoManager().isClean();
}
```

### 教训

1. **异步资源等待** - 第三方脚本加载是异步的
2. **防御性检查** - 使用全局变量前检查是否定义
3. **降级处理** - 资源加载失败时优雅降级

---

## 2. "已修改"徽章闪烁问题

### 根因分析

选择文件时，未修改的文件也会短暂显示"已修改"徽章：

```javascript
// 问题代码
function selectFile(file) {
    showModifiedBadge();  // 立即显示
    loadFile(file, function() {
        updateModifiedState();  // 加载完成后更新
    });
}
```

**问题**：异步加载期间状态不正确。

### 修复方案

```javascript
function selectFile(file) {
    // 1. 先隐藏徽章
    hideModifiedBadge();
    
    // 2. 加载文件
    loadFile(file, function() {
        // 3. 根据实际状态更新
        updateModifiedState();
    });
}
```

### 教训

1. **状态初始化** - 异步操作前设置正确的初始状态
2. **避免中间状态** - 加载中应显示加载指示，而非错误状态
3. **状态机思维** - 文件状态：空 → 加载中 → 已加载/错误

---

## 3. Ping 数据显示延迟

### 根因分析

选择设备后，Ping 数据显示有 2 秒延迟：

```javascript
// 问题代码
function refreshPing() {
    // ...
    setTimeout(refreshPing, 2000);  // 刷新间隔 2 秒
}
```

**问题**：
- 初次选择设备时，要等 2 秒才显示数据
- 用户感觉卡顿

### 修复方案

```javascript
function selectDevice(deviceId) {
    currentDevice = deviceId;
    refreshPing();  // 立即刷新一次
}

function refreshPing() {
    if (!currentDevice) return;
    
    fetchPingData(currentDevice).then(function(data) {
        updatePingDisplay(data);
        setTimeout(refreshPing, 500);  // 降低到 500ms
    });
}
```

### 教训

1. **立即响应** - 用户操作后立即显示反馈
2. **后台刷新** - 刷新间隔 ≠ 响应延迟
3. **感知性能** - 500ms 内响应感觉"即时"

---

## 4. Web 控制台数据路由问题

### 根因分析

消息广播到所有 Web 控制台，而非目标设备：

```javascript
// 问题代码
function broadcastToWebConsoles(message) {
    webConsoles.forEach(function(ws) {
        ws.send(message);  // 广播给所有人
    });
}
```

**问题**：
- 设备 A 的终端输出显示在设备 B 的控制台
- 多设备环境下混乱

### 修复方案

```javascript
function sendToConsole(deviceId, message) {
    var consoles = getConsolesByDevice(deviceId);
    consoles.forEach(function(ws) {
        ws.send(message);
    });
}

// 或使用 request_id 精准路由
function unicastByRequestId(requestId, message) {
    var ws = getConsoleByRequestId(requestId);
    if (ws) {
        ws.send(message);
    }
}
```

### 教训

1. **明确路由策略** - 单播、组播、广播的使用场景
2. **设备隔离** - 不同设备的数据要隔离
3. **request_id 追踪** - 请求-响应模式需要追踪

---

## 前端最佳实践

### 异步资源加载

```javascript
// ✅ 正确模式
function waitForGlobal(name, timeout = 5000) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        
        function check() {
            if (window[name]) {
                resolve(window[name]);
            } else if (Date.now() - start > timeout) {
                reject(new Error(`${name} not loaded within ${timeout}ms`));
            } else {
                setTimeout(check, 100);
            }
        }
        check();
    });
}

// 使用
await waitForGlobal('ace');
initAceEditor();
```

### 状态管理

```javascript
// ✅ 状态机模式
const FileState = {
    EMPTY: 'empty',
    LOADING: 'loading',
    LOADED: 'loaded',
    ERROR: 'error',
    MODIFIED: 'modified'
};

class FileManager {
    constructor() {
        this.state = FileState.EMPTY;
    }
    
    async loadFile(path) {
        this.setState(FileState.LOADING);
        try {
            const content = await fetchFile(path);
            this.content = content;
            this.setState(FileState.LOADED);
        } catch (err) {
            this.setState(FileState.ERROR);
        }
    }
    
    setState(newState) {
        this.state = newState;
        this.updateUI();
    }
    
    updateUI() {
        switch (this.state) {
            case FileState.LOADING:
                showSpinner();
                hideBadge();
                break;
            case FileState.LOADED:
                hideSpinner();
                hideBadge();
                break;
            case FileState.MODIFIED:
                showBadge();
                break;
        }
    }
}
```

---

## 相关提交

- `77527af` - ace.js 异步加载修复
- `a9bea10` - 徽章闪烁修复
- `69bfbc5` - Ping 显示延迟修复
- `7ff02a5` - Ping 刷新间隔优化